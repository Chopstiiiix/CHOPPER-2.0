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
from models import db, ChatMessage, MessageAttachment, User, Feedback, UserProfile, DocumentUpload, AdminMessage, SupportChat, SoundPack, Beat, Wallet, Transaction, UserBeatLibrary
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
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size for beat uploads
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

CORS(app)

# Error handler for file too large
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 50MB'}), 413

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
            # Return JSON error for API endpoints
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
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
            db.session.flush()  # Get the user ID

            # Create wallet with signup bonus
            wallet = Wallet(user_id=new_user.id, balance=50)
            db.session.add(wallet)

            # Record the signup bonus transaction
            bonus_transaction = Transaction(
                user_id=new_user.id,
                transaction_type='bonus',
                amount=50,
                balance_after=50,
                reference_type='signup_bonus',
                description='Welcome bonus tokens'
            )
            db.session.add(bonus_transaction)

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

# =============================================================================
# Beatpax Routes and API Endpoints
# =============================================================================

ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'flac', 'm4a'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50MB
MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5MB

def allowed_audio_file(filename):
    """Check if audio file extension is allowed"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_AUDIO_EXTENSIONS

def allowed_image_file(filename):
    """Check if image file extension is allowed"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS

def get_or_create_wallet(user_id):
    """Get user's wallet or create one if it doesn't exist"""
    wallet = Wallet.query.filter_by(user_id=user_id).first()
    if not wallet:
        wallet = Wallet(user_id=user_id, balance=50)
        db.session.add(wallet)
        # Record the signup bonus
        bonus = Transaction(
            user_id=user_id,
            transaction_type='bonus',
            amount=50,
            balance_after=50,
            reference_type='signup_bonus',
            description='Welcome bonus tokens'
        )
        db.session.add(bonus)
        db.session.commit()
    return wallet


# Page Routes
@app.route('/beatpax')
@login_required
def beatpax():
    """Main Beatpax catalog page"""
    user_id = session.get('user_id')
    wallet = get_or_create_wallet(user_id)
    return render_template('beatpax.html', wallet_balance=wallet.balance)


@app.route('/beatpax/library')
@login_required
def beatpax_library():
    """User's downloaded beats library"""
    user_id = session.get('user_id')
    wallet = get_or_create_wallet(user_id)
    library = UserBeatLibrary.query.filter_by(user_id=user_id).order_by(
        UserBeatLibrary.purchased_at.desc()
    ).all()
    return render_template('beatpax.html',
                          wallet_balance=wallet.balance,
                          page='library',
                          library=library)


@app.route('/beatpax/wallet')
@login_required
def beatpax_wallet():
    """Token balance and purchase page"""
    user_id = session.get('user_id')
    wallet = get_or_create_wallet(user_id)
    transactions = Transaction.query.filter_by(user_id=user_id).order_by(
        Transaction.created_at.desc()
    ).limit(20).all()
    return render_template('beatpax.html',
                          wallet_balance=wallet.balance,
                          page='wallet',
                          wallet=wallet,
                          transactions=transactions)


# API Endpoints
@app.route('/api/beatpax/explore')
@login_required
def beatpax_explore():
    """Get catalog data for explore page - returns sound packs"""
    user_id = session.get('user_id')

    try:
        from datetime import timedelta

        # Featured sound pack
        hero_pack = SoundPack.query.filter_by(is_featured=True, is_active=True).first()
        if not hero_pack:
            # Fall back to most downloaded pack
            hero_pack = SoundPack.query.filter_by(is_active=True).order_by(
                SoundPack.download_count.desc()
            ).first()

        # New releases - latest sound packs
        new_releases = SoundPack.query.filter_by(is_active=True).order_by(
            SoundPack.created_at.desc()
        ).limit(12).all()

        # Trending - most downloaded packs
        trending = SoundPack.query.filter_by(is_active=True).order_by(
            SoundPack.download_count.desc()
        ).limit(6).all()

        # Fresh - recent packs (last week)
        fresh_cutoff = datetime.utcnow() - timedelta(days=7)
        fresh = SoundPack.query.filter(
            SoundPack.is_active == True,
            SoundPack.created_at >= fresh_cutoff
        ).order_by(SoundPack.created_at.desc()).limit(6).all()

        # Top creators (by pack count and downloads)
        top_creators = db.session.query(
            User.id, User.first_name, User.surname,
            db.func.count(SoundPack.id).label('pack_count'),
            db.func.sum(SoundPack.download_count).label('total_downloads')
        ).join(SoundPack).filter(SoundPack.is_active == True).group_by(
            User.id
        ).order_by(db.desc('total_downloads')).limit(6).all()

        # User's library beat IDs (to show owned status)
        owned_beat_ids = [lib.beat_id for lib in UserBeatLibrary.query.filter_by(
            user_id=user_id
        ).all()]

        # Get owned pack IDs (if user owns any track from a pack, they own the pack)
        owned_pack_ids = list(set([
            beat.sound_pack_id for beat in Beat.query.join(UserBeatLibrary).filter(
                UserBeatLibrary.user_id == user_id,
                Beat.sound_pack_id != None
            ).all()
        ]))

        return jsonify({
            'hero': hero_pack.to_dict(include_tracks=True) if hero_pack else None,
            'new_releases': [p.to_dict(include_tracks=True) for p in new_releases],
            'trending': [p.to_dict(include_tracks=True) for p in trending],
            'fresh': [p.to_dict(include_tracks=True) for p in fresh],
            'top_creators': [{
                'id': c.id,
                'name': f"{c.first_name} {c.surname}",
                'pack_count': c.pack_count,
                'total_downloads': c.total_downloads or 0
            } for c in top_creators],
            'owned_beat_ids': owned_beat_ids,
            'owned_pack_ids': owned_pack_ids
        })
    except Exception as e:
        print(f"Error in beatpax explore: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to load catalog'}), 500


@app.route('/api/beatpax/beats')
@login_required
def beatpax_beats():
    """Get sound packs with optional filtering"""
    genre = request.args.get('genre')
    search = request.args.get('search')
    sort = request.args.get('sort', 'newest')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    try:
        query = SoundPack.query.filter_by(is_active=True)

        if genre and genre != 'all':
            query = query.filter_by(genre=genre)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    SoundPack.name.ilike(search_term),
                    SoundPack.tags.ilike(search_term)
                )
            )

        if sort == 'newest':
            query = query.order_by(SoundPack.created_at.desc())
        elif sort == 'popular':
            query = query.order_by(SoundPack.download_count.desc())
        elif sort == 'trending':
            query = query.order_by(SoundPack.play_count.desc())
        elif sort == 'price_low':
            query = query.order_by(SoundPack.token_cost.asc())
        elif sort == 'price_high':
            query = query.order_by(SoundPack.token_cost.desc())

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'packs': [p.to_dict(include_tracks=True) for p in paginated.items],
            'total': paginated.total,
            'pages': paginated.pages,
            'current_page': page
        })
    except Exception as e:
        print(f"Error fetching packs: {e}")
        return jsonify({'error': 'Failed to fetch packs'}), 500


@app.route('/api/beatpax/upload-config', methods=['GET'])
@login_required
def beatpax_upload_config():
    """Get upload configuration for client-side uploads"""
    is_vercel = os.environ.get('VERCEL') == 'true' or os.environ.get('VERCEL') == '1'
    blob_configured = blob_storage.is_blob_configured()
    blob_token = os.environ.get('BLOB_READ_WRITE_TOKEN', '') if blob_configured else ''

    # Log for debugging
    print(f"Upload config: is_vercel={is_vercel}, blob_configured={blob_configured}, token_present={bool(blob_token)}")

    # Determine max file size
    if is_vercel and blob_configured:
        max_size = 50 * 1024 * 1024  # 50MB with client upload
    elif is_vercel:
        max_size = 4 * 1024 * 1024   # 4MB without blob (server limit)
    else:
        max_size = 50 * 1024 * 1024  # 50MB local

    return jsonify({
        'is_production': is_vercel,
        'blob_configured': blob_configured,
        'blob_token': blob_token if is_vercel else '',
        'max_file_size': max_size,
        'server_upload_available': not is_vercel or not blob_configured,
        'message': 'Blob storage not configured. Large file uploads disabled.' if (is_vercel and not blob_configured) else None
    })


@app.route('/api/beatpax/create-beat', methods=['POST'])
@login_required
def beatpax_create_beat():
    """Create a beat record from already-uploaded files (for client-side uploads)"""
    user_id = session.get('user_id')

    try:
        data = request.get_json()

        title = (data.get('title') or '').strip()
        genre = (data.get('genre') or '').strip()
        audio_url = (data.get('audio_url') or '').strip()
        cover_url = (data.get('cover_url') or '').strip() or None
        bpm = data.get('bpm')
        key = (data.get('key') or '').strip()
        tags = (data.get('tags') or '').strip()
        token_cost = data.get('token_cost', 5)

        # Validate required fields
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        if not genre:
            return jsonify({'error': 'Genre is required'}), 400
        if not audio_url:
            return jsonify({'error': 'Audio URL is required'}), 400

        # Validate URL is from Vercel Blob (allow test URLs in development)
        is_valid_url = (
            audio_url.startswith('https://') and
            ('blob.vercel-storage.com' in audio_url or 'vercel-storage.com' in audio_url)
        )
        if not is_valid_url:
            return jsonify({'error': 'Invalid audio URL. Must be a Vercel Blob URL.'}), 400

        # Validate token cost
        token_cost = max(3, min(20, int(token_cost)))

        # Create beat record
        beat = Beat(
            title=title,
            creator_id=user_id,
            audio_url=audio_url,
            cover_url=cover_url,
            genre=genre,
            bpm=int(bpm) if bpm else None,
            key=key,
            tags=tags,
            token_cost=token_cost
        )

        db.session.add(beat)
        db.session.commit()

        return jsonify({
            'success': True,
            'beat': beat.to_dict(),
            'message': 'Beat created successfully!'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error creating beat: {e}")
        return jsonify({'error': 'Failed to create beat'}), 500


@app.route('/api/beatpax/create-soundpack', methods=['POST'])
@login_required
def beatpax_create_soundpack():
    """Create a sound pack with multiple tracks (for client-side uploads)"""
    user_id = session.get('user_id')

    try:
        data = request.get_json()

        # Sound pack info (shared)
        pack_name = (data.get('pack_name') or '').strip()
        genre = (data.get('genre') or '').strip()
        cover_url = (data.get('cover_url') or '').strip() or None
        description = (data.get('description') or '').strip()
        tags = (data.get('tags') or '').strip()
        tracks_data = data.get('tracks', [])

        # Validate required fields
        if not pack_name:
            return jsonify({'error': 'Pack name is required'}), 400
        if not genre:
            return jsonify({'error': 'Genre is required'}), 400
        if not tracks_data or len(tracks_data) == 0:
            return jsonify({'error': 'At least one track is required'}), 400

        # Validate all tracks have audio URLs
        for i, track in enumerate(tracks_data):
            if not track.get('audio_url'):
                return jsonify({'error': f'Track {i+1} is missing audio URL'}), 400
            if not track.get('title'):
                return jsonify({'error': f'Track {i+1} is missing title'}), 400

        # Token cost = 1 token per track (calculated automatically)
        track_count = len(tracks_data)
        token_cost = track_count  # 1 token per track

        # Create sound pack
        sound_pack = SoundPack(
            name=pack_name,
            creator_id=user_id,
            cover_url=cover_url,
            genre=genre,
            description=description,
            tags=tags,
            token_cost=token_cost,
            track_count=track_count
        )
        db.session.add(sound_pack)
        db.session.flush()  # Get the pack ID

        # Create tracks
        created_tracks = []
        for i, track_data in enumerate(tracks_data):
            track = Beat(
                title=track_data.get('title', f'Track {i+1}'),
                creator_id=user_id,
                sound_pack_id=sound_pack.id,
                audio_url=track_data.get('audio_url'),
                cover_url=cover_url,  # Use pack cover
                genre=genre,
                bpm=track_data.get('bpm'),
                key=track_data.get('key', ''),
                tags=tags,
                token_cost=0,  # Individual tracks in pack are free (pack has cost)
                track_number=i + 1
            )
            db.session.add(track)
            created_tracks.append(track)

        db.session.commit()

        return jsonify({
            'success': True,
            'sound_pack': sound_pack.to_dict(include_tracks=True),
            'message': f'Sound pack "{pack_name}" created with {len(created_tracks)} tracks!'
        })

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        print(f"Error creating sound pack: {e}")
        return jsonify({'error': f'Failed to create sound pack: {str(e)}'}), 500


@app.route('/api/beatpax/soundpacks', methods=['GET'])
@login_required
def get_soundpacks():
    """Get all sound packs"""
    try:
        genre = request.args.get('genre')
        query = SoundPack.query.filter_by(is_active=True)

        if genre and genre != 'all':
            query = query.filter_by(genre=genre)

        packs = query.order_by(SoundPack.created_at.desc()).limit(20).all()
        return jsonify({
            'sound_packs': [pack.to_dict(include_tracks=True) for pack in packs]
        })
    except Exception as e:
        print(f"Error fetching sound packs: {e}")
        return jsonify({'error': 'Failed to fetch sound packs'}), 500


@app.route('/api/beatpax/upload-audio', methods=['POST'])
@login_required
def beatpax_upload_audio():
    """Upload just an audio file and return the URL (for local development)"""
    try:
        audio_file = request.files.get('audio')
        if not audio_file or not audio_file.filename:
            return jsonify({'error': 'Audio file is required'}), 400

        if not allowed_audio_file(audio_file.filename):
            return jsonify({'error': 'Invalid audio format'}), 400

        # Generate unique filename
        audio_filename = generate_unique_filename(audio_file.filename)
        audio_mime = audio_file.content_type or mimetypes.guess_type(audio_file.filename)[0] or 'audio/mpeg'

        # Upload to Blob storage or local
        if blob_storage.is_blob_configured():
            audio_path = blob_storage.generate_blob_path('packs/audio', audio_filename)
            audio_url, _ = blob_storage.upload_file(audio_file, audio_path, audio_mime)
        else:
            audio_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'packs', 'audio')
            os.makedirs(audio_dir, exist_ok=True)
            audio_local_path = os.path.join(audio_dir, audio_filename)
            audio_file.save(audio_local_path)
            audio_url = f'/uploads/packs/audio/{audio_filename}'

        return jsonify({
            'success': True,
            'audio_url': audio_url
        })

    except Exception as e:
        print(f"Error uploading audio: {e}")
        return jsonify({'error': 'Failed to upload audio'}), 500


@app.route('/api/beatpax/upload', methods=['POST'])
@login_required
def beatpax_upload():
    """Upload a new beat"""
    user_id = session.get('user_id')

    try:
        # Get form data
        title = request.form.get('title', '').strip()
        genre = request.form.get('genre', '').strip()
        bpm = request.form.get('bpm', type=int)
        key = request.form.get('key', '').strip()
        tags = request.form.get('tags', '').strip()
        token_cost = request.form.get('token_cost', 5, type=int)

        # Validate required fields
        if not title:
            return jsonify({'error': 'Title is required'}), 400
        if not genre:
            return jsonify({'error': 'Genre is required'}), 400

        # Get audio file
        audio_file = request.files.get('audio')
        if not audio_file or not audio_file.filename:
            return jsonify({'error': 'Audio file is required'}), 400

        if not allowed_audio_file(audio_file.filename):
            return jsonify({'error': 'Invalid audio format. Allowed: MP3, WAV, FLAC, M4A'}), 400

        # Check file size
        audio_file.seek(0, 2)
        audio_size = audio_file.tell()
        audio_file.seek(0)

        if audio_size > MAX_AUDIO_SIZE:
            return jsonify({'error': 'Audio file too large. Maximum 50MB'}), 400

        # Generate unique filename
        audio_filename = generate_unique_filename(audio_file.filename)

        # Get MIME type
        audio_mime = audio_file.content_type or mimetypes.guess_type(audio_file.filename)[0] or 'audio/mpeg'

        # Upload audio to Blob storage
        if blob_storage.is_blob_configured():
            audio_path = blob_storage.generate_blob_path('beats/audio', audio_filename)
            audio_url, _ = blob_storage.upload_file(audio_file, audio_path, audio_mime)
        else:
            # Fallback to local storage
            audio_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'beats', 'audio')
            os.makedirs(audio_dir, exist_ok=True)
            audio_local_path = os.path.join(audio_dir, audio_filename)
            audio_file.save(audio_local_path)
            audio_url = f'/uploads/beats/audio/{audio_filename}'

        # Handle cover image (optional)
        cover_url = None
        cover_file = request.files.get('cover')
        if cover_file and cover_file.filename:
            if allowed_image_file(cover_file.filename):
                cover_file.seek(0, 2)
                cover_size = cover_file.tell()
                cover_file.seek(0)

                if cover_size <= MAX_IMAGE_SIZE:
                    cover_filename = generate_unique_filename(cover_file.filename)
                    cover_mime = cover_file.content_type or mimetypes.guess_type(cover_file.filename)[0] or 'image/jpeg'

                    if blob_storage.is_blob_configured():
                        cover_path = blob_storage.generate_blob_path('beats/covers', cover_filename)
                        cover_url, _ = blob_storage.upload_file(cover_file, cover_path, cover_mime)
                    else:
                        cover_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'beats', 'covers')
                        os.makedirs(cover_dir, exist_ok=True)
                        cover_local_path = os.path.join(cover_dir, cover_filename)
                        cover_file.save(cover_local_path)
                        cover_url = f'/uploads/beats/covers/{cover_filename}'

        # Validate token cost
        token_cost = max(3, min(20, token_cost))  # Between 3 and 20

        # Create beat record
        beat = Beat(
            title=title,
            creator_id=user_id,
            audio_url=audio_url,
            cover_url=cover_url,
            genre=genre,
            bpm=bpm,
            key=key,
            tags=tags,
            token_cost=token_cost
        )

        db.session.add(beat)
        db.session.commit()

        return jsonify({
            'success': True,
            'beat': beat.to_dict(),
            'message': 'Beat uploaded successfully!'
        })

    except Exception as e:
        db.session.rollback()
        import traceback
        error_details = str(e)
        traceback.print_exc()

        # Check for specific error types
        if 'Blob' in error_details or 'BLOB' in error_details:
            return jsonify({'error': 'Storage service error. Please try again or use a smaller file.'}), 500
        elif 'size' in error_details.lower() or 'large' in error_details.lower():
            return jsonify({'error': 'File too large. Please use a file under 4MB for web uploads.'}), 413
        elif 'timeout' in error_details.lower():
            return jsonify({'error': 'Upload timed out. Please try again with a smaller file.'}), 504

        print(f"Error uploading beat: {error_details}")
        return jsonify({'error': f'Upload failed: {error_details[:100]}'}), 500


@app.route('/api/beatpax/beats/<int:beat_id>/play', methods=['POST'])
@login_required
def beatpax_play(beat_id):
    """Record a play (free action)"""
    try:
        beat = Beat.query.get(beat_id)
        if not beat or not beat.is_active:
            return jsonify({'error': 'Beat not found'}), 404

        beat.play_count += 1
        db.session.commit()

        return jsonify({
            'success': True,
            'play_count': beat.play_count
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error recording play: {e}")
        return jsonify({'error': 'Failed to record play'}), 500


@app.route('/api/beatpax/beats/<int:beat_id>/download', methods=['POST'])
@login_required
def beatpax_download(beat_id):
    """Download a beat (spend tokens)"""
    user_id = session.get('user_id')

    try:
        beat = Beat.query.get(beat_id)
        if not beat or not beat.is_active:
            return jsonify({'error': 'Beat not found'}), 404

        # Check if already owned
        existing = UserBeatLibrary.query.filter_by(
            user_id=user_id, beat_id=beat_id
        ).first()

        if existing:
            # Already owned - just increment download count
            existing.download_count += 1
            existing.downloaded_at = datetime.utcnow()
            db.session.commit()
            return jsonify({
                'success': True,
                'already_owned': True,
                'audio_url': beat.audio_url,
                'message': 'You already own this beat!'
            })

        # Fixed cost: 1 token per beat
        token_cost = 1

        # Check wallet balance
        wallet = get_or_create_wallet(user_id)
        if wallet.balance < token_cost:
            return jsonify({
                'error': 'Insufficient tokens',
                'required': token_cost,
                'balance': wallet.balance
            }), 400

        # Deduct tokens from buyer
        wallet.balance -= token_cost
        wallet.total_spent += token_cost

        # Record buyer's transaction
        buyer_transaction = Transaction(
            user_id=user_id,
            transaction_type='spend',
            amount=-token_cost,
            balance_after=wallet.balance,
            reference_type='beat_download',
            reference_id=beat_id,
            description=f'Downloaded: {beat.title}'
        )
        db.session.add(buyer_transaction)

        # Credit creator (80% of token cost)
        creator_earnings = max(1, int(token_cost * 0.8))  # Minimum 1 token for creator
        creator_wallet = get_or_create_wallet(beat.creator_id)
        creator_wallet.balance += creator_earnings
        creator_wallet.total_earned += creator_earnings

        # Record creator's transaction
        creator_transaction = Transaction(
            user_id=beat.creator_id,
            transaction_type='earn',
            amount=creator_earnings,
            balance_after=creator_wallet.balance,
            reference_type='beat_sale',
            reference_id=beat_id,
            description=f'Sale: {beat.title}'
        )
        db.session.add(creator_transaction)

        # Add to user's library
        library_entry = UserBeatLibrary(
            user_id=user_id,
            beat_id=beat_id,
            tokens_spent=token_cost,
            downloaded_at=datetime.utcnow(),
            download_count=1
        )
        db.session.add(library_entry)

        # Increment beat download count
        beat.download_count += 1

        db.session.commit()

        return jsonify({
            'success': True,
            'audio_url': beat.audio_url,
            'tokens_spent': token_cost,
            'new_balance': wallet.balance,
            'message': f'Downloaded! {token_cost} token spent.'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error downloading beat: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to download beat'}), 500


# Token API Endpoints
@app.route('/api/tokens/balance')
@login_required
def get_token_balance():
    """Get user's token balance"""
    user_id = session.get('user_id')
    wallet = get_or_create_wallet(user_id)
    return jsonify({
        'balance': wallet.balance,
        'total_spent': wallet.total_spent,
        'total_earned': wallet.total_earned
    })


@app.route('/api/tokens/purchase', methods=['POST'])
@login_required
def purchase_tokens():
    """Purchase tokens (stub - would integrate payment)"""
    user_id = session.get('user_id')
    data = request.get_json()
    package = data.get('package')

    # Token packages (stub pricing)
    packages = {
        '100': {'tokens': 100, 'price': 4.99},
        '250': {'tokens': 250, 'price': 9.99},
        '500': {'tokens': 500, 'price': 17.99},
        '1000': {'tokens': 1000, 'price': 29.99}
    }

    if package not in packages:
        return jsonify({'error': 'Invalid package'}), 400

    pkg = packages[package]

    try:
        wallet = get_or_create_wallet(user_id)
        wallet.balance += pkg['tokens']

        transaction = Transaction(
            user_id=user_id,
            transaction_type='purchase',
            amount=pkg['tokens'],
            balance_after=wallet.balance,
            reference_type='token_purchase',
            description=f"Purchased {pkg['tokens']} tokens"
        )
        db.session.add(transaction)
        db.session.commit()

        return jsonify({
            'success': True,
            'tokens_added': pkg['tokens'],
            'new_balance': wallet.balance,
            'message': f"Added {pkg['tokens']} tokens!"
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error purchasing tokens: {e}")
        return jsonify({'error': 'Failed to purchase tokens'}), 500


@app.route('/api/tokens/transactions')
@login_required
def get_transactions():
    """Get user's transaction history"""
    user_id = session.get('user_id')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    try:
        paginated = Transaction.query.filter_by(user_id=user_id).order_by(
            Transaction.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'transactions': [t.to_dict() for t in paginated.items],
            'total': paginated.total,
            'pages': paginated.pages,
            'current_page': page
        })
    except Exception as e:
        print(f"Error fetching transactions: {e}")
        return jsonify({'error': 'Failed to fetch transactions'}), 500


@app.route('/api/beatpax/library')
@login_required
def get_user_library():
    """Get user's beat library"""
    user_id = session.get('user_id')

    try:
        library = UserBeatLibrary.query.filter_by(user_id=user_id).order_by(
            UserBeatLibrary.purchased_at.desc()
        ).all()

        return jsonify({
            'library': [entry.to_dict() for entry in library],
            'count': len(library)
        })
    except Exception as e:
        print(f"Error fetching library: {e}")
        return jsonify({'error': 'Failed to fetch library'}), 500


@app.route('/api/beatpax/my-beats')
@login_required
def get_my_beats():
    """Get beats uploaded by the current user"""
    user_id = session.get('user_id')

    try:
        beats = Beat.query.filter_by(creator_id=user_id).order_by(
            Beat.created_at.desc()
        ).all()

        return jsonify({
            'beats': [b.to_dict() for b in beats],
            'count': len(beats)
        })
    except Exception as e:
        print(f"Error fetching my beats: {e}")
        return jsonify({'error': 'Failed to fetch beats'}), 500


@app.route('/api/beatpax/my-uploads')
@login_required
def get_my_uploads():
    """Get all sound packs uploaded by the current user"""
    user_id = session.get('user_id')

    try:
        # Get sound packs
        packs = SoundPack.query.filter_by(creator_id=user_id, is_active=True).order_by(
            SoundPack.created_at.desc()
        ).all()

        # Get standalone beats (not part of a pack)
        standalone_beats = Beat.query.filter_by(
            creator_id=user_id,
            sound_pack_id=None,
            is_active=True
        ).order_by(Beat.created_at.desc()).all()

        return jsonify({
            'sound_packs': [pack.to_dict(include_tracks=True) for pack in packs],
            'standalone_beats': [b.to_dict() for b in standalone_beats],
            'total_packs': len(packs),
            'total_standalone': len(standalone_beats)
        })
    except Exception as e:
        print(f"Error fetching my uploads: {e}")
        return jsonify({'error': 'Failed to fetch uploads'}), 500


@app.route('/api/beatpax/soundpacks/<int:pack_id>', methods=['PUT'])
@login_required
def update_soundpack(pack_id):
    """Update a sound pack"""
    user_id = session.get('user_id')

    try:
        pack = SoundPack.query.get(pack_id)
        if not pack:
            return jsonify({'error': 'Sound pack not found'}), 404

        if pack.creator_id != user_id:
            return jsonify({'error': 'You can only edit your own uploads'}), 403

        data = request.get_json()

        # Update fields
        if 'name' in data:
            pack.name = data['name'].strip()
        if 'genre' in data:
            pack.genre = data['genre'].strip()
        if 'description' in data:
            pack.description = data['description'].strip()
        if 'tags' in data:
            pack.tags = data['tags'].strip()
        if 'cover_url' in data:
            pack.cover_url = data['cover_url']
        # Note: token_cost is automatically calculated as 1 per track

        db.session.commit()

        return jsonify({
            'success': True,
            'sound_pack': pack.to_dict(include_tracks=True),
            'message': 'Sound pack updated successfully!'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error updating sound pack: {e}")
        return jsonify({'error': 'Failed to update sound pack'}), 500


@app.route('/api/beatpax/soundpacks/<int:pack_id>', methods=['DELETE'])
@login_required
def delete_soundpack(pack_id):
    """Delete a sound pack and all its tracks"""
    user_id = session.get('user_id')

    try:
        pack = SoundPack.query.get(pack_id)
        if not pack:
            return jsonify({'error': 'Sound pack not found'}), 404

        if pack.creator_id != user_id:
            return jsonify({'error': 'You can only delete your own uploads'}), 403

        # Soft delete - mark as inactive
        pack.is_active = False
        for track in pack.tracks:
            track.is_active = False

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Sound pack deleted successfully!'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting sound pack: {e}")
        return jsonify({'error': 'Failed to delete sound pack'}), 500


@app.route('/api/beatpax/tracks/<int:track_id>', methods=['PUT'])
@login_required
def update_track(track_id):
    """Update an individual track"""
    user_id = session.get('user_id')

    try:
        track = Beat.query.get(track_id)
        if not track:
            return jsonify({'error': 'Track not found'}), 404

        if track.creator_id != user_id:
            return jsonify({'error': 'You can only edit your own uploads'}), 403

        data = request.get_json()

        # Update fields
        if 'title' in data:
            track.title = data['title'].strip()
        if 'bpm' in data:
            track.bpm = int(data['bpm']) if data['bpm'] else None
        if 'key' in data:
            track.key = data['key'].strip()

        db.session.commit()

        return jsonify({
            'success': True,
            'track': track.to_dict(),
            'message': 'Track updated successfully!'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error updating track: {e}")
        return jsonify({'error': 'Failed to update track'}), 500


@app.route('/api/beatpax/tracks/<int:track_id>', methods=['DELETE'])
@login_required
def delete_track(track_id):
    """Delete an individual track"""
    user_id = session.get('user_id')

    try:
        track = Beat.query.get(track_id)
        if not track:
            return jsonify({'error': 'Track not found'}), 404

        if track.creator_id != user_id:
            return jsonify({'error': 'You can only delete your own uploads'}), 403

        # Soft delete
        track.is_active = False

        # Update pack track count if part of a pack
        if track.sound_pack_id:
            pack = SoundPack.query.get(track.sound_pack_id)
            if pack:
                pack.track_count = Beat.query.filter_by(
                    sound_pack_id=pack.id, is_active=True
                ).count()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Track deleted successfully!'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting track: {e}")
        return jsonify({'error': 'Failed to delete track'}), 500


# =============================================================================
# Public Share Routes for Beatpax
# =============================================================================

@app.route('/beatpax/pack/<int:pack_id>')
def beatpax_share_pack(pack_id):
    """Public page to view a shared sound pack - no login required"""
    try:
        pack = SoundPack.query.get(pack_id)
        if not pack or not pack.is_active:
            return render_template('beatpax_share.html', pack=None, error='Sound pack not found')

        # Get pack data with tracks
        pack_data = pack.to_dict(include_tracks=True)

        # Check if user is logged in for download capability
        is_logged_in = session.get('authenticated', False)
        user_id = session.get('user_id')
        wallet_balance = 0

        if is_logged_in and user_id:
            wallet = Wallet.query.filter_by(user_id=user_id).first()
            wallet_balance = wallet.balance if wallet else 0

        return render_template('beatpax_share.html',
                               pack=pack_data,
                               is_logged_in=is_logged_in,
                               wallet_balance=wallet_balance,
                               error=None)
    except Exception as e:
        print(f"Error loading shared pack: {e}")
        return render_template('beatpax_share.html', pack=None, error='Failed to load sound pack')


@app.route('/api/beatpax/pack/<int:pack_id>/public')
def beatpax_public_pack(pack_id):
    """Public API to get sound pack data - no login required"""
    try:
        pack = SoundPack.query.get(pack_id)
        if not pack or not pack.is_active:
            return jsonify({'error': 'Sound pack not found'}), 404

        return jsonify({
            'pack': pack.to_dict(include_tracks=True)
        })
    except Exception as e:
        print(f"Error fetching public pack: {e}")
        return jsonify({'error': 'Failed to fetch sound pack'}), 500


# Create database tables on app startup (only in development)
# On Vercel, use Vercel Postgres and run migrations separately
if not os.environ.get('VERCEL'):
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)