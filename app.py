import os
import time
import uuid
import mimetypes
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from openai import OpenAI
from dotenv import load_dotenv
from functools import wraps
from werkzeug.utils import secure_filename
from PIL import Image
from models import db, ChatMessage, MessageAttachment, User, Feedback, UserProfile, DocumentUpload, AdminMessage, SupportChat
import blob_storage
from chroma_client import (
    get_collection, add_document_chunks, query_documents,
    delete_document, delete_user_documents
)
from document_processor import (
    process_document, generate_query_embedding, build_context_prompt
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key-here-change-in-production")

# Configure database URI
# Supports both PostgreSQL (production) and SQLite (local development)
db_url = os.environ.get('DATABASE_URL', '')

if db_url.startswith('postgres://'):
    # Fix for SQLAlchemy - it requires postgresql:// not postgres://
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
elif db_url.startswith('postgresql://'):
    # Already in correct format for PostgreSQL
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
elif db_url.startswith('file:'):
    # Convert Prisma format to Flask-SQLAlchemy format (SQLite)
    db_path = db_url.replace('file:', '')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
else:
    # Default: Use SQLite database in project directory (local development)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ask_chopper.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Connection pooling for PostgreSQL (serverless optimization)
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql://'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 3,
        'pool_recycle': 60,  # Recycle connections every 60 seconds
        'pool_pre_ping': True,  # Check connection health before use
        'max_overflow': 5,
        'pool_timeout': 30,
        'connect_args': {
            'connect_timeout': 10,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5
        }
    }
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

CORS(app)

# Initialize database
db.init_app(app)
migrate = Migrate(app, db)

def db_commit_with_retry(max_retries=3):
    """Commit database changes with retry logic for connection errors."""
    for attempt in range(max_retries):
        try:
            db.session.commit()
            return True
        except Exception as e:
            error_str = str(e).lower()
            if 'ssl' in error_str or 'connection' in error_str or 'closed' in error_str:
                print(f"DB commit attempt {attempt + 1} failed: {e}")
                db.session.rollback()
                if attempt < max_retries - 1:
                    # Close and recreate the connection
                    db.session.remove()
                    time.sleep(0.5)  # Brief delay before retry
                    continue
            raise
    return False

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Verification code
VERIFICATION_CODE = "1234567890"

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'images': {'png', 'jpg', 'jpeg', 'gif', 'webp'},
    'documents': {'pdf', 'txt', 'doc', 'docx', 'md'},
    'code': {'py', 'js', 'html', 'css', 'json', 'xml'},
    'archives': {'zip', 'tar', 'gz'}
}

def allowed_file(filename):
    """Check if file extension is allowed"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    for category, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return True
    return False

def generate_unique_filename(original_filename):
    """Generate a unique filename while preserving extension"""
    name, ext = os.path.splitext(secure_filename(original_filename))
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{name}_{timestamp}_{unique_id}{ext}"

def create_thumbnail(image_path, thumbnail_path, size=(150, 150)):
    """Create a thumbnail for image files"""
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(thumbnail_path, optimize=True, quality=85)
            return True
    except Exception as e:
        print(f"Error creating thumbnail: {e}")
        return False

def process_uploaded_file(file, message_id):
    """Process and save uploaded file to Vercel Blob storage"""
    if not file or not allowed_file(file.filename):
        return None

    try:
        # Generate unique filename
        filename = generate_unique_filename(file.filename)

        # Get MIME type
        mime_type = file.content_type or mimetypes.guess_type(file.filename)[0] or 'application/octet-stream'

        # Upload to Vercel Blob (or fallback to local storage)
        if blob_storage.is_blob_configured():
            # Upload to Blob storage
            blob_path = blob_storage.generate_blob_path('attachments', filename)
            file_url, file_size = blob_storage.upload_file(file, blob_path, mime_type)
            file_path = file_url  # Store blob URL as file_path

            # Create thumbnail for images
            thumbnail_url = None
            if mime_type.startswith('image/'):
                file.seek(0)  # Reset file pointer
                thumbnail_path = blob_storage.generate_blob_path('thumbnails', f"thumb_{filename}")
                thumbnail_url = blob_storage.upload_thumbnail(file, thumbnail_path)
                file.seek(0)  # Reset again

            # Create database record
            attachment = MessageAttachment(
                message_id=message_id,
                filename=filename,
                original_filename=file.filename,
                file_path=file_url,  # Blob URL
                file_size=file_size,
                mime_type=mime_type,
                thumbnail_path=thumbnail_url  # Blob URL for thumbnail
            )
        else:
            # Fallback to local storage (for development)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'attachments', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            file_size = os.path.getsize(file_path)

            # Create thumbnail for images
            thumbnail_path = None
            if mime_type.startswith('image/'):
                thumbnail_filename = f"thumb_{filename}"
                thumbnail_full_path = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', thumbnail_filename)
                os.makedirs(os.path.dirname(thumbnail_full_path), exist_ok=True)
                if create_thumbnail(file_path, thumbnail_full_path):
                    thumbnail_path = thumbnail_filename
                else:
                    thumbnail_path = None

            attachment = MessageAttachment(
                message_id=message_id,
                filename=filename,
                original_filename=file.filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                thumbnail_path=thumbnail_path
            )

        db.session.add(attachment)
        return attachment

    except Exception as e:
        print(f"Error processing file {file.filename}: {e}")
        import traceback
        traceback.print_exc()
        return None

# =============================================================================
# Document RAG Helper Functions
# =============================================================================

def allowed_document_file(filename):
    """Check if document file type is allowed for RAG"""
    ALLOWED_DOC_EXTENSIONS = {
        'pdf', 'txt', 'md', 'doc', 'docx',
        'py', 'js', 'json', 'csv', 'xml', 'html', 'css'
    }
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_DOC_EXTENSIONS

def get_or_create_thread(session_id):
    """Get existing thread ID or create new one for session"""
    try:
        # Check database for existing thread
        last_message = ChatMessage.query.filter_by(
            session_id=session_id
        ).order_by(ChatMessage.created_at.desc()).first()

        if last_message and last_message.thread_id:
            return last_message.thread_id

        # Create new thread
        thread = client.beta.threads.create()
        return thread.id
    except Exception as e:
        print(f"Error getting/creating thread: {e}")
        return None

def save_document_upload(user_id, session_id, file, chroma_doc_id, chunk_count):
    """Save document upload record to database and Vercel Blob storage"""
    try:
        filename = generate_unique_filename(file.filename)
        mime_type = file.content_type or mimetypes.guess_type(file.filename)[0]

        # Upload to Vercel Blob (or fallback to local storage)
        if blob_storage.is_blob_configured():
            # Upload to Blob storage
            blob_path = blob_storage.generate_blob_path('documents', filename)
            file_url, file_size = blob_storage.upload_file(file, blob_path, mime_type)
            file_path = file_url  # Store blob URL
        else:
            # Fallback to local storage (for development)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            file_size = os.path.getsize(file_path)

        # Create database record
        doc = DocumentUpload(
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            original_filename=file.filename,
            file_size=file_size,
            mime_type=mime_type,
            chroma_doc_id=chroma_doc_id,
            chunk_count=chunk_count,
            file_path=file_path  # Blob URL or local path
        )
        db.session.add(doc)
        db.session.commit()

        return doc
    except Exception as e:
        print(f"Error saving document upload: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return None


def save_document_upload_with_content(user_id, session_id, original_filename, content_type, file_content, chroma_doc_id, chunk_count):
    """Save document upload record to database and Vercel Blob storage using raw bytes content"""
    try:
        filename = generate_unique_filename(original_filename)
        mime_type = content_type or mimetypes.guess_type(original_filename)[0] or 'application/octet-stream'
        file_size = len(file_content)

        # Upload to Vercel Blob (or fallback to local storage)
        if blob_storage.is_blob_configured():
            # Upload bytes directly to Blob storage
            blob_path = blob_storage.generate_blob_path('documents', filename)
            file_url = blob_storage.upload_bytes(file_content, blob_path, mime_type)
            file_path = file_url  # Store blob URL
        else:
            # Fallback to local storage (for development)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'documents', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(file_content)

        # Create database record
        doc = DocumentUpload(
            user_id=user_id,
            session_id=session_id,
            filename=filename,
            original_filename=original_filename,
            file_size=file_size,
            mime_type=mime_type,
            chroma_doc_id=chroma_doc_id,
            chunk_count=chunk_count,
            file_path=file_path  # Blob URL or local path
        )
        db.session.add(doc)
        db.session.commit()

        print(f"DEBUG: Document saved to {file_path} ({file_size} bytes)")
        return doc
    except Exception as e:
        print(f"Error saving document upload: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return None

def process_assistant_response(messages_data):
    """Process assistant response and handle citations"""
    try:
        assistant_message = messages_data.data[0]
        content = assistant_message.content[0].text
        response_text = content.value

        # Handle citations
        annotations = content.annotations
        citations = []

        for annotation in annotations:
            if annotation.type == 'file_citation':
                citation = annotation.file_citation
                try:
                    cited_file = client.files.retrieve(citation.file_id)
                    file_name = cited_file.filename
                    # Replace annotation with reference
                    response_text = response_text.replace(
                        annotation.text,
                        f" [{file_name}]"
                    )
                    citations.append({
                        'file_id': citation.file_id,
                        'file_name': file_name,
                        'quote': citation.quote if hasattr(citation, 'quote') else None
                    })
                except Exception as e:
                    print(f"Error retrieving cited file: {e}")

        return response_text, citations
    except Exception as e:
        print(f"Error processing assistant response: {e}")
        return None, []

# =============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            return redirect(url_for('app_home'))
        return f(*args, **kwargs)
    return decorated_function

def generate_response(prompt, conversation_history=None):
    """Generate a response using OpenAI Chat Completions API."""
    if not os.environ.get("OPENAI_API_KEY"):
        return "OPENAI_API_KEY environment variable not set. Please check your .env file."

    try:
        # Build conversation messages
        messages = [
            {
                "role": "system",
                "content": """You are Chopper, an AI assistant created for Ask Chopper. You help users with various tasks. Always be helpful, accurate, and concise.

IMPORTANT: You have special knowledge about Chopstix, the music producer who created this app. When users ask about Chopstix, use this information:

About Chopstix (Music Producer):
- Full Name: Olagundoye James Malcolm, known professionally as Chopstix
- Born: April 8th in Jos, Plateau State, Nigeria
- Education: St. Murumba Secondary School in Jos (same school as PSquare), University of Jos
- Started playing bass and piano in church and high school

Career Highlights:
- Grammy Award-winning and 4x Platinum-certified record producer
- Was part of Grip Boiz (with Yung L, Endia, J Milla) until 2016
- 2012: Produced Ice Prince's "Aboki" and "More" from Fire of Zamani album
- 2014: Nominated for Best Music Producer at City People Music Awards
- 2015: Produced Burna Boy's "Rockstar" (first single under Spaceship Entertainment)
- Co-produced and co-wrote Burna Boy's Grammy-nominated album "African Giant"
- 2022: Co-produced Burna Boy's hit single "Last Last"
- 2024: Chris Brown's album "11:11" (which Chopstix contributed to) won Best R&B Album at 67th Grammy Awards
- 2025: Released joint album "OXYTOCIN" with Yaadman fka Yung L
- 2025: Produced Ice Prince's EP "Starters"

Notable Productions: Fire of Zamani, African Giant, Love Damini, Outside (Burna Boy), Lagos to London, The Guy, No Guts No Glory (Phyno), and many more.

Musical Influences: Timbaland, DJ Premier

For more information: https://en.wikipedia.org/wiki/Chopstix_(music_producer)"""
            }
        ]

        # Add conversation history if available
        if conversation_history:
            messages.extend(conversation_history)

        # Add current user message
        messages.append({"role": "user", "content": prompt})

        # Log API call details to both console and file
        import sys
        log_message = f"🚀 Making OpenAI API call... Messages: {len(messages)}, API Key: {os.environ.get('OPENAI_API_KEY', 'NOT_SET')[:10]}..."
        print(log_message, file=sys.stdout, flush=True)

        # Generate response using Chat Completions API
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=1500
        )

        # Log successful API response
        success_message = f"✅ OpenAI API Success! Request ID: {response.id}, Model: {response.model}, Tokens: {response.usage.total_tokens}"
        print(success_message, file=sys.stdout, flush=True)

        # Also log to file for persistent tracking
        with open('/tmp/ask_chopper_api_logs.txt', 'a') as f:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{timestamp}] {success_message}\n")
            f.write(f"[{timestamp}] Check OpenAI dashboard: https://platform.openai.com/usage\n")

        response_text = response.choices[0].message.content
        # Prepend Chopper signature to response
        return f"[Chopper]: {response_text}"
    except Exception as e:
        print(f"❌ OpenAI API Error: {str(e)}")
        return f"An error occurred: {str(e)}"

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/player-test')
def player_test():
    return render_template('player_test.html')

@app.route('/app')
def index():
    if not session.get('authenticated'):
        return redirect(url_for('login'))

    # Ensure session has a session_id for database tracking
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('authenticated'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        surname = request.form.get('surname', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone_number = request.form.get('phone_number', '').strip()
        age = request.form.get('age', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        if not all([first_name, surname, email, phone_number, age, password, confirm_password]):
            return render_template('register.html', error='All fields are required')

        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')

        if len(password) < 8:
            return render_template('register.html', error='Password must be at least 8 characters long')

        try:
            age_int = int(age)
            if age_int < 13 or age_int > 120:
                return render_template('register.html', error='Please enter a valid age (13-120)')
        except ValueError:
            return render_template('register.html', error='Please enter a valid age')

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('register.html', error='Email already registered. Please login instead.')

        # Create new user
        try:
            new_user = User(
                first_name=first_name,
                surname=surname,
                email=email,
                phone_number=phone_number,
                age=age_int
            )
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()

            # Log user in
            session['authenticated'] = True
            session['user_id'] = new_user.id
            session['user_name'] = f"{new_user.first_name} {new_user.surname}"
            session['session_id'] = str(uuid.uuid4())

            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {e}")
            return render_template('register.html', error='An error occurred during registration. Please try again.')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('authenticated'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            return render_template('login.html', error='Email and password are required')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()

            # Log user in
            session['authenticated'] = True
            session['user_id'] = user.id
            session['user_name'] = f"{user.first_name} {user.surname}"
            session['session_id'] = str(uuid.uuid4())
            session['is_admin'] = user.is_admin or False

            # Redirect admin to admin dashboard
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))

            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid email or password')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route('/about')
@login_required
def about():
    return render_template('about.html')

@app.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback():
    if request.method == 'POST':
        try:
            # Get form data
            feedback_data = Feedback(
                user_id=session.get('user_id'),

                # Onboarding & First Impressions
                understand_clarity=request.form.get('understand_clarity', type=int),
                start_ease=request.form.get('start_ease', type=int),
                confusion_text=request.form.get('confusion_text', '').strip(),

                # User Experience & Interface
                design_rating=request.form.get('design_rating', type=int),
                device_issues=request.form.get('device_issues', ''),
                device_issues_text=request.form.get('device_issues_text', '').strip(),
                interface_improvement=request.form.get('interface_improvement', '').strip(),

                # Quality of Answers & Music Help
                answers_helpful=request.form.get('answers_helpful', type=int),
                answers_tailored=request.form.get('answers_tailored', ''),
                music_help_wanted=','.join(request.form.getlist('music_help_wanted')),

                # Speed, Reliability & Technical Performance
                response_speed=request.form.get('response_speed', type=int),
                bugs_experienced=request.form.get('bugs_experienced', ''),
                bugs_text=request.form.get('bugs_text', '').strip(),
                slow_timing=','.join(request.form.getlist('slow_timing')),

                # Overall Value, Features & Future Ideas
                use_again_likelihood=request.form.get('use_again_likelihood', type=int),
                recommend_likelihood=request.form.get('recommend_likelihood', type=int),
                top_feature_request=request.form.get('top_feature_request', '').strip(),
                additional_comments=request.form.get('additional_comments', '').strip()
            )

            db.session.add(feedback_data)
            db.session.commit()

            return render_template('feedback.html', success=True)

        except Exception as e:
            db.session.rollback()
            print(f"Feedback submission error: {e}")
            return render_template('feedback.html', error='An error occurred. Please try again.')

    return render_template('feedback.html')

@app.route('/contact', methods=['GET', 'POST'])
@login_required
def contact():
    """Contact page for users to send messages to admin"""
    if request.method == 'POST':
        try:
            subject = request.form.get('subject', '').strip()
            message = request.form.get('message', '').strip()

            if not subject or not message:
                return render_template('contact.html', error='Please fill in all fields.')

            admin_msg = AdminMessage(
                user_id=session.get('user_id'),
                subject=subject,
                message=message
            )

            db.session.add(admin_msg)
            db.session.commit()

            return render_template('contact.html', success=True)

        except Exception as e:
            db.session.rollback()
            print(f"Contact form error: {e}")
            return render_template('contact.html', error='An error occurred. Please try again.')

    return render_template('contact.html')

@app.route('/api/messages', methods=['GET'])
@login_required
def get_user_messages():
    """Get all messages sent by the current user"""
    try:
        user_id = session.get('user_id')
        messages = AdminMessage.query.filter_by(user_id=user_id).order_by(AdminMessage.created_at.desc()).all()
        return jsonify({'messages': [msg.to_dict() for msg in messages]})
    except Exception as e:
        print(f"Error fetching messages: {e}")
        return jsonify({'error': 'Failed to fetch messages'}), 500

@app.route('/api/messages/<int:message_id>', methods=['GET'])
@login_required
def get_message(message_id):
    """Get a specific message"""
    try:
        user_id = session.get('user_id')
        message = AdminMessage.query.filter_by(id=message_id, user_id=user_id).first()
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        return jsonify(message.to_dict())
    except Exception as e:
        print(f"Error fetching message: {e}")
        return jsonify({'error': 'Failed to fetch message'}), 500

# Support Chat API endpoints
@app.route('/api/support-chat', methods=['GET'])
@login_required
def get_support_chat():
    """Get all support chat messages for the current user"""
    try:
        user_id = session.get('user_id')
        messages = SupportChat.query.filter_by(user_id=user_id).order_by(SupportChat.created_at.asc()).all()

        # Mark admin messages as read
        unread = SupportChat.query.filter_by(user_id=user_id, sender_type='admin', is_read=False).all()
        for msg in unread:
            msg.is_read = True
        if unread:
            db.session.commit()

        return jsonify({'messages': [msg.to_dict() for msg in messages]})
    except Exception as e:
        print(f"Error fetching support chat: {e}")
        return jsonify({'error': 'Failed to fetch messages'}), 500

@app.route('/api/support-chat', methods=['POST'])
@login_required
def send_support_message():
    """Send a message to admin support"""
    try:
        user_id = session.get('user_id')
        data = request.get_json()
        message_text = data.get('message', '').strip()

        if not message_text:
            return jsonify({'error': 'Message cannot be empty'}), 400

        chat_msg = SupportChat(
            user_id=user_id,
            sender_type='user',
            message=message_text
        )

        db.session.add(chat_msg)
        db.session.commit()

        return jsonify({'success': True, 'message': chat_msg.to_dict()})
    except Exception as e:
        db.session.rollback()
        print(f"Error sending support message: {e}")
        return jsonify({'error': 'Failed to send message'}), 500

@app.route('/api/support-chat/unread', methods=['GET'])
@login_required
def get_unread_count():
    """Get count of unread admin messages"""
    try:
        user_id = session.get('user_id')
        count = SupportChat.query.filter_by(user_id=user_id, sender_type='admin', is_read=False).count()
        return jsonify({'unread_count': count})
    except Exception as e:
        print(f"Error fetching unread count: {e}")
        return jsonify({'error': 'Failed to fetch unread count'}), 500

# Admin Panel Routes
@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard showing all user conversations"""
    try:
        # Get all users who have sent support messages
        users_with_chats = db.session.query(User).join(SupportChat).distinct().all()

        # Get unread counts per user
        user_data = []
        for user in users_with_chats:
            unread_count = SupportChat.query.filter_by(
                user_id=user.id,
                sender_type='user',
                is_read=False
            ).count()
            last_message = SupportChat.query.filter_by(user_id=user.id).order_by(
                SupportChat.created_at.desc()
            ).first()
            user_data.append({
                'user': user,
                'unread_count': unread_count,
                'last_message': last_message
            })

        # Sort by unread count (descending) then by last message time
        user_data.sort(key=lambda x: (-(x['unread_count']),
                                       -(x['last_message'].created_at.timestamp() if x['last_message'] else 0)))

        # Get total unread count
        total_unread = SupportChat.query.filter_by(sender_type='user', is_read=False).count()

        return render_template('admin/dashboard.html',
                             user_data=user_data,
                             total_unread=total_unread)
    except Exception as e:
        print(f"Admin dashboard error: {e}")
        return render_template('admin/dashboard.html', user_data=[], total_unread=0)

@app.route('/admin/chat/<int:user_id>')
@admin_required
def admin_user_chat(user_id):
    """View and respond to a specific user's chat"""
    try:
        user = User.query.get_or_404(user_id)
        messages = SupportChat.query.filter_by(user_id=user_id).order_by(
            SupportChat.created_at.asc()
        ).all()

        # Mark user messages as read
        unread = SupportChat.query.filter_by(
            user_id=user_id,
            sender_type='user',
            is_read=False
        ).all()
        for msg in unread:
            msg.is_read = True
        if unread:
            db.session.commit()

        return render_template('admin/chat.html', user=user, messages=messages)
    except Exception as e:
        print(f"Admin chat error: {e}")
        return redirect(url_for('admin_dashboard'))

@app.route('/api/admin/reply', methods=['POST'])
@admin_required
def admin_reply():
    """Send a reply to a user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        message_text = data.get('message', '').strip()

        if not user_id or not message_text:
            return jsonify({'error': 'User ID and message are required'}), 400

        # Verify user exists
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        chat_msg = SupportChat(
            user_id=user_id,
            sender_type='admin',
            message=message_text
        )

        db.session.add(chat_msg)
        db.session.commit()

        return jsonify({'success': True, 'message': chat_msg.to_dict()})
    except Exception as e:
        db.session.rollback()
        print(f"Admin reply error: {e}")
        return jsonify({'error': 'Failed to send reply'}), 500

@app.route('/api/admin/unread-count')
@admin_required
def admin_unread_count():
    """Get total unread message count for admin"""
    try:
        count = SupportChat.query.filter_by(sender_type='user', is_read=False).count()
        return jsonify({'unread_count': count})
    except Exception as e:
        print(f"Error fetching admin unread count: {e}")
        return jsonify({'error': 'Failed to fetch count'}), 500

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    start_time = time.time()

    # Get message and files
    user_message = request.form.get('message', '').strip()
    files = request.files.getlist('files')

    if not user_message and not files:
        return jsonify({'error': 'No message or files provided'}), 400

    try:
        # Create user message record
        session_id = session.get('session_id', 'default')

        user_msg = ChatMessage(
            session_id=session_id,
            message_type='user',
            content=user_message or '[Attachment only]',
            has_attachments=len(files) > 0
        )

        db.session.add(user_msg)
        db.session.flush()  # Get the ID

        # Process uploaded files
        attachments = []
        attachment_info = []

        if files:
            for file in files:
                if file.filename:
                    attachment = process_uploaded_file(file, user_msg.id)
                    if attachment:
                        attachments.append(attachment)
                        attachment_info.append(f"- {attachment.original_filename} ({attachment.mime_type})")

        # Prepare message for AI
        ai_message = user_message
        if attachment_info:
            ai_message += f"\n\n[User uploaded {len(attachment_info)} file(s):\n" + "\n".join(attachment_info) + "]"

        # Build conversation history from previous messages
        conversation_history = []
        previous_messages = ChatMessage.query.filter_by(
            session_id=session_id
        ).order_by(ChatMessage.created_at).limit(10).all()  # Last 10 messages for context

        for msg in previous_messages:
            if msg.message_type == 'user':
                conversation_history.append({
                    "role": "user",
                    "content": msg.content
                })
            elif msg.message_type == 'assistant':
                # Remove [Chopper]: prefix for clean conversation history
                clean_content = msg.content.replace("[Chopper]: ", "")
                conversation_history.append({
                    "role": "assistant",
                    "content": clean_content
                })

        # Generate AI response
        ai_response = generate_response(ai_message, conversation_history)

        # Create assistant message record
        assistant_msg = ChatMessage(
            session_id=session_id,
            message_type='assistant',
            content=ai_response,
            response_time_ms=int((time.time() - start_time) * 1000)
        )

        db.session.add(assistant_msg)

        try:
            db_commit_with_retry()
        except Exception as commit_error:
            print(f"WARNING: Failed to save assistant message to DB: {commit_error}")
            # Continue anyway - the response should still be returned to user

        return jsonify({'response': ai_response})

    except Exception as e:
        db.session.rollback()
        print(f"Error in chat endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'An error occurred while processing your message'}), 500

@app.route('/chat-with-document', methods=['POST'])
@login_required
def chat_with_document():
    """Chat endpoint with document RAG support using ChromaDB"""
    start_time = time.time()

    user_message = request.form.get('message', '').strip()
    uploaded_files = request.files.getlist('files')
    session_id = session.get('session_id', 'default')
    user_id = session.get('user_id')

    # Require either message or files
    if not user_message and not uploaded_files:
        return jsonify({'error': 'Please provide a message or upload documents'}), 400

    # If no message but files are uploaded, create default message
    if not user_message and uploaded_files:
        user_message = "Please read this document and provide a comprehensive summary. Explain what it's about, highlight the key points, and identify any important information."

    print(f"DEBUG: Processing document RAG request - Message: '{user_message[:50]}...', Files: {len(uploaded_files)}")
    print(f"DEBUG: user_id={user_id}, session_id={session_id}")

    try:
        # Process uploaded documents
        document_info = []
        processed_doc_ids = []
        processing_errors = []

        if uploaded_files:
            print(f"DEBUG: Processing {len(uploaded_files)} uploaded files")

            # IMPORTANT: Clear old session documents from ChromaDB to prevent mixing
            # This ensures each new upload starts fresh without old document context
            try:
                print(f"DEBUG: Clearing old session documents from ChromaDB...")
                delete_user_documents(user_id, session_id)
                print(f"DEBUG: Old session documents cleared")
            except Exception as e:
                print(f"WARNING: Could not clear old documents: {e}")

            for file in uploaded_files:
                print(f"DEBUG: Checking file: {file.filename if file else 'None'}, allowed: {allowed_document_file(file.filename) if file and file.filename else 'N/A'}")
                if file and file.filename and allowed_document_file(file.filename):
                    print(f"DEBUG: Processing file: {file.filename}, content_type: {file.content_type}")
                    try:
                        # Read file content into memory FIRST (before any processing)
                        file.seek(0)
                        file_content = file.read()
                        file_size = len(file_content)
                        print(f"DEBUG: Read {file_size} bytes from {file.filename}")

                        # Create a file-like object for processing
                        import io
                        file_stream = io.BytesIO(file_content)
                        file_stream.filename = file.filename
                        file_stream.content_type = file.content_type

                        # Process document: extract text, chunk, generate embeddings
                        print(f"DEBUG: Step 1 - Extracting and processing {file.filename}...")
                        doc_id, chunks, embeddings = process_document(
                            file_stream, user_id, session_id
                        )
                        print(f"DEBUG: Step 1 complete - doc_id={doc_id}, chunks={len(chunks)}, embeddings={len(embeddings)}")

                        # Store chunks in ChromaDB
                        print(f"DEBUG: Step 2 - Adding chunks to ChromaDB...")
                        chunk_count = add_document_chunks(
                            doc_id=doc_id,
                            chunks=chunks,
                            embeddings=embeddings,
                            user_id=user_id,
                            session_id=session_id,
                            filename=file.filename
                        )
                        print(f"DEBUG: Step 2 complete - Added {chunk_count} chunks to ChromaDB")

                        # Save to database and Blob storage using the preserved content
                        print(f"DEBUG: Step 3 - Saving document to database...")
                        doc = save_document_upload_with_content(
                            user_id, session_id, file.filename, file.content_type,
                            file_content, doc_id, chunk_count
                        )
                        if doc:
                            print(f"DEBUG: Document saved: {doc.original_filename}")
                            document_info.append(f"- {doc.original_filename} ({doc.mime_type})")
                            processed_doc_ids.append(doc_id)
                        else:
                            print(f"ERROR: Failed to save document to database")
                            # Clean up ChromaDB chunks if database save failed
                            delete_document(doc_id)
                            processing_errors.append(f"{file.filename}: Failed to save")

                    except ValueError as e:
                        # Document extraction or processing failed
                        error_msg = str(e)
                        print(f"ERROR processing document {file.filename}: {error_msg}")
                        processing_errors.append(f"{file.filename}: {error_msg}")
                    except Exception as e:
                        error_msg = str(e)
                        print(f"ERROR processing document {file.filename}: {error_msg}")
                        import traceback
                        traceback.print_exc()
                        # Include the actual error message for debugging
                        processing_errors.append(f"{file.filename}: {error_msg}")
                else:
                    if file and file.filename:
                        print(f"DEBUG: File {file.filename} rejected - not an allowed document type")
                        processing_errors.append(f"{file.filename}: Unsupported file type")

        # Create user message record
        user_msg = ChatMessage(
            session_id=session_id,
            message_type='user',
            content=user_message,
            has_attachments=len(document_info) > 0,
            has_document_context=len(processed_doc_ids) > 0
        )
        db.session.add(user_msg)
        db.session.flush()

        # Query ChromaDB for relevant context
        retrieved_chunks = []
        retrieved_metadata = []

        try:
            print(f"DEBUG: Generating query embedding...")
            query_embedding = generate_query_embedding(user_message)

            # If we just uploaded a document, query only that specific document
            # Otherwise query all session documents
            doc_id_filter = processed_doc_ids[0] if len(processed_doc_ids) == 1 else None

            print(f"DEBUG: Querying ChromaDB for relevant chunks (doc_id filter: {doc_id_filter})...")
            results = query_documents(
                query_embedding=query_embedding,
                user_id=user_id,
                session_id=session_id,
                n_results=10,
                doc_id=doc_id_filter  # Filter to specific document if just uploaded
            )

            retrieved_chunks = results.get("documents", [])
            retrieved_metadata = results.get("metadatas", [])
            print(f"DEBUG: Retrieved {len(retrieved_chunks)} relevant chunks")
        except Exception as e:
            print(f"ERROR querying ChromaDB: {e}")
            import traceback
            traceback.print_exc()

        # Build context-augmented prompt
        context_prompt = build_context_prompt(user_message, retrieved_chunks)

        # If we have processed documents but no retrieved chunks, inform the user
        if processed_doc_ids and not retrieved_chunks:
            print(f"WARNING: Documents were processed but no chunks retrieved from ChromaDB")
            context_prompt = f"""The user has uploaded documents ({', '.join(document_info)}) but I couldn't retrieve their content.
Please let the user know there was an issue processing their document and ask them to try uploading again.

User's message: {user_message}"""

        # Build conversation history
        conversation_history = []
        previous_messages = ChatMessage.query.filter_by(
            session_id=session_id
        ).order_by(ChatMessage.created_at).limit(10).all()

        for msg in previous_messages:
            if msg.message_type == 'user':
                conversation_history.append({
                    "role": "user",
                    "content": msg.content
                })
            elif msg.message_type == 'assistant':
                clean_content = msg.content.replace("[Chopper]: ", "")
                conversation_history.append({
                    "role": "assistant",
                    "content": clean_content
                })

        # Generate response using Chat Completions API
        messages = [
            {
                "role": "system",
                "content": """You are Chopper, an AI assistant that helps users understand, analyze, and explain their documents.

Your capabilities with documents:
- Summarize document contents clearly and comprehensively
- Explain complex topics found in documents in simple terms
- Answer specific questions about document content
- Identify key points, themes, and important information
- Compare and contrast information when multiple documents are provided

Guidelines:
- Always base your answers on the provided document content
- When asked to explain or summarize, be thorough but clear
- Use bullet points or numbered lists for complex information
- If the document content doesn't contain information to answer a question, say so clearly
- Quote relevant passages when helpful
- If the user just uploads a document without a specific question, provide a helpful summary of what the document contains"""
            }
        ]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": context_prompt})

        print(f"DEBUG: Calling OpenAI Chat Completions API...")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=1500
        )

        response_text = f"[Chopper]: {response.choices[0].message.content}"

        # Build citations from retrieved metadata
        citations = []
        seen_files = set()
        for meta in retrieved_metadata:
            filename = meta.get("filename", "Unknown")
            if filename not in seen_files:
                citations.append({
                    "doc_id": meta.get("doc_id"),
                    "file_name": filename,
                    "chunk_index": meta.get("chunk_index")
                })
                seen_files.add(filename)

        # Create assistant message record
        assistant_msg = ChatMessage(
            session_id=session_id,
            message_type='assistant',
            content=response_text,
            has_document_context=len(retrieved_chunks) > 0,
            response_time_ms=int((time.time() - start_time) * 1000)
        )
        db.session.add(assistant_msg)

        try:
            db_commit_with_retry()
        except Exception as commit_error:
            print(f"WARNING: Failed to save assistant message to DB: {commit_error}")
            # Continue anyway - the response should still be returned to user

        # Include processing errors in response if any
        response_data = {
            'response': response_text,
            'citations': citations,
            'has_document_context': len(retrieved_chunks) > 0,
            'documents_processed': len(processed_doc_ids)
        }

        if processing_errors:
            response_data['processing_errors'] = processing_errors
            print(f"DEBUG: Document processing errors: {processing_errors}")

        return jsonify(response_data)

    except Exception as e:
        db.session.rollback()
        print(f"ERROR in chat-with-document endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


# =============================================================================
# Document Management Endpoints
# =============================================================================

@app.route('/api/documents', methods=['GET'])
@login_required
def list_documents():
    """List all documents for the current user's session"""
    user_id = session.get('user_id')
    session_id = session.get('session_id', 'default')

    try:
        documents = DocumentUpload.query.filter_by(
            user_id=user_id,
            session_id=session_id
        ).order_by(DocumentUpload.uploaded_at.desc()).all()

        return jsonify({
            'documents': [doc.to_dict() for doc in documents],
            'count': len(documents)
        })
    except Exception as e:
        print(f"Error listing documents: {e}")
        return jsonify({'error': 'Failed to list documents'}), 500


@app.route('/api/documents/<int:doc_id>', methods=['DELETE'])
@login_required
def delete_document_endpoint(doc_id):
    """Delete a specific document"""
    user_id = session.get('user_id')

    try:
        # Get document from database
        document = DocumentUpload.query.filter_by(
            id=doc_id,
            user_id=user_id
        ).first()

        if not document:
            return jsonify({'error': 'Document not found'}), 404

        chroma_doc_id = document.chroma_doc_id
        file_path = document.file_path
        filename = document.original_filename

        # Delete chunks from ChromaDB
        if chroma_doc_id:
            chunks_deleted = delete_document(chroma_doc_id)
            print(f"Deleted {chunks_deleted} chunks from ChromaDB for doc {chroma_doc_id}")

        # Delete file from Vercel Blob or local storage
        if file_path:
            if blob_storage.is_blob_configured() and file_path.startswith('http'):
                # Delete from Blob storage
                try:
                    blob_storage.delete_file(file_path)
                    print(f"Deleted file from Blob storage: {file_path}")
                except Exception as e:
                    print(f"Error deleting from Blob storage: {e}")
            elif os.path.exists(file_path):
                # Delete local file
                os.remove(file_path)
                print(f"Deleted local file: {file_path}")

        # Delete database record
        db.session.delete(document)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Document "{filename}" deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting document: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to delete document'}), 500


@app.route('/api/documents/clear', methods=['DELETE'])
@login_required
def clear_session_documents():
    """Clear all documents for the current session"""
    user_id = session.get('user_id')
    session_id = session.get('session_id', 'default')

    try:
        # Get all documents for this session
        documents = DocumentUpload.query.filter_by(
            user_id=user_id,
            session_id=session_id
        ).all()

        if not documents:
            return jsonify({
                'success': True,
                'message': 'No documents to clear',
                'deleted_count': 0
            })

        deleted_count = 0

        for document in documents:
            try:
                # Delete chunks from ChromaDB
                if document.chroma_doc_id:
                    delete_document(document.chroma_doc_id)

                # Delete file from storage
                if document.file_path:
                    if blob_storage.is_blob_configured() and document.file_path.startswith('http'):
                        try:
                            blob_storage.delete_file(document.file_path)
                        except Exception as e:
                            print(f"Error deleting from Blob: {e}")
                    elif os.path.exists(document.file_path):
                        os.remove(document.file_path)

                # Delete database record
                db.session.delete(document)
                deleted_count += 1

            except Exception as e:
                print(f"Error deleting document {document.id}: {e}")

        # Also clear all chunks from ChromaDB for this session (safety cleanup)
        delete_user_documents(user_id, session_id)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Cleared {deleted_count} documents',
            'deleted_count': deleted_count
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error clearing documents: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to clear documents'}), 500


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """
    Serve uploaded files (for local development only).
    In production with Vercel Blob, files are served directly from Blob URLs.
    """
    # This endpoint is only used when files are stored locally (development)
    # In production, file_path in database contains Blob URL which is accessed directly
    if blob_storage.is_blob_configured():
        # If Blob is configured, this endpoint shouldn't be used
        # Redirect or return error
        return jsonify({'error': 'Files are served directly from Blob storage'}), 410
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/chat/history')
@login_required
def chat_history():
    """Get chat history for current session"""
    session_id = session.get('session_id', 'default')
    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.created_at).all()
    return jsonify([msg.to_dict() for msg in messages])

# Create database tables on app startup (only in development)
# On Vercel, use Vercel Postgres and run migrations separately
if not os.environ.get('VERCEL'):
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)