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
from models import db, ChatMessage, MessageAttachment, User, Feedback, UserProfile, UserTokens, AudioPack, AudioFile, UserActivity, UserDownload, DocumentUpload
import blob_storage

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
        'pool_size': 5,
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'max_overflow': 10
    }
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size (supports WAV files)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

CORS(app)

# Initialize database
db.init_app(app)
migrate = Migrate(app, db)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Assistant and Vector Store configuration
ASSISTANT_ID = os.environ.get("OPENAI_ASSISTANT_ID")
VECTOR_STORE_ID = os.environ.get("OPENAI_VECTOR_STORE_ID")

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

def save_document_upload(user_id, session_id, file, openai_file_id):
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
            openai_file_id=openai_file_id,
            vector_store_id=VECTOR_STORE_ID,
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

def generate_response(prompt, conversation_history=None):
    """Generate a response using OpenAI Chat Completions API."""
    if not os.environ.get("OPENAI_API_KEY"):
        return "OPENAI_API_KEY environment variable not set. Please check your .env file."

    try:
        # Build conversation messages
        messages = [
            {
                "role": "system",
                "content": "You are Chopper, an AI assistant that helps users with various tasks. Always be helpful, accurate, and concise."
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

# ============ SOUNDS MARKETPLACE ROUTES ============

@app.route('/sounds')
@login_required
def sounds():
    """Main sounds marketplace page"""
    return render_template('sounds.html')

# API: Get token balance
@app.route('/api/tokens/balance', methods=['GET'])
@login_required
def get_token_balance():
    user_id = session.get('user_id')
    wallet = UserTokens.query.filter_by(user_id=user_id).first()

    if not wallet:
        # Create wallet with initial balance
        wallet = UserTokens(user_id=user_id, balance=100)
        db.session.add(wallet)
        db.session.commit()

    return jsonify({'balance': wallet.balance})

# API: Purchase tokens
@app.route('/api/tokens/purchase', methods=['POST'])
@login_required
def purchase_tokens():
    user_id = session.get('user_id')
    data = request.get_json()
    amount = data.get('amount', 0)

    if amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400

    wallet = UserTokens.query.filter_by(user_id=user_id).first()
    if not wallet:
        wallet = UserTokens(user_id=user_id, balance=amount)
        db.session.add(wallet)
    else:
        wallet.balance += amount

    # Log activity
    activity = UserActivity(
        user_id=user_id,
        type='TOKEN_PURCHASE',
        activity_metadata=f'{{"amount": {amount}}}'
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify({'balance': wallet.balance})

# API: Spend tokens
@app.route('/api/tokens/spend', methods=['POST'])
@login_required
def spend_tokens():
    user_id = session.get('user_id')
    data = request.get_json()
    amount = data.get('amount', 0)
    reason = data.get('reason', 'LISTEN')
    pack_id = data.get('packId')
    file_id = data.get('fileId')

    if amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400

    wallet = UserTokens.query.filter_by(user_id=user_id).first()
    if not wallet or wallet.balance < amount:
        return jsonify({'error': 'Insufficient tokens'}), 400

    wallet.balance -= amount

    # Log activity
    activity = UserActivity(
        user_id=user_id,
        type=reason,
        entity_id=file_id if file_id else pack_id,
        entity_type='FILE' if file_id else 'PACK',
        activity_metadata=f'{{"amount": {amount}}}'
    )
    db.session.add(activity)

    # If downloading, save to UserDownload table
    if reason == 'DOWNLOAD' and pack_id:
        # Check if already downloaded
        existing_download = UserDownload.query.filter_by(user_id=user_id, pack_id=pack_id).first()
        if not existing_download:
            # Determine category based on pack metadata
            pack = AudioPack.query.get(pack_id)
            category = 'Sound Pax'  # Default
            if pack and pack.genre:
                # Categorize based on genre
                if pack.genre.lower() in ['hip-hop', 'trap', 'drill']:
                    category = 'Beats'
                elif pack.genre.lower() in ['pop', 'rock', 'jazz', 'r&b', 'afrobeats']:
                    category = 'Music'

            download = UserDownload(
                user_id=user_id,
                pack_id=pack_id,
                category=category
            )
            db.session.add(download)

    db.session.commit()

    return jsonify({'balance': wallet.balance})

# API: Get user activity
@app.route('/api/activity/log', methods=['GET'])
@login_required
def get_activity():
    user_id = session.get('user_id')
    activities = UserActivity.query.filter_by(user_id=user_id).order_by(UserActivity.created_at.desc()).limit(20).all()

    activities_list = []
    for activity in activities:
        label = f"{activity.type}"
        if activity.type == 'TOKEN_PURCHASE':
            label = "Purchased tokens"
        elif activity.type == 'LISTEN':
            label = "Listened to a track"
        elif activity.type == 'DOWNLOAD':
            label = "Downloaded a track"
        elif activity.type == 'UPLOAD':
            label = "Uploaded a pack"

        activities_list.append({
            'id': activity.id,
            'type': activity.type,
            'label': label,
            'createdAt': activity.created_at.isoformat() if activity.created_at else None
        })

    return jsonify({'activities': activities_list})

# API: List audio packs
@app.route('/api/sounds/list', methods=['GET'])
@login_required
def list_packs():
    # Get all packs ordered by creation date
    packs = AudioPack.query.order_by(AudioPack.created_at.desc()).limit(20).all()

    return jsonify({
        'recommended': [p.to_dict() for p in packs[:10]],
        'new': [p.to_dict() for p in packs]
    })

# API: Upload audio pack
@app.route('/api/packs/upload', methods=['POST'])
@login_required
def upload_pack():
    user_id = session.get('user_id')

    try:
        title = request.form.get('title', '').strip()
        genre = request.form.get('genre', '').strip()
        bpm = request.form.get('bpm', type=int)
        musical_key = request.form.get('musicalKey', '').strip()

        print(f"DEBUG: Upload request - Title: {title}, Genre: {genre}, BPM: {bpm}, Key: {musical_key}")

        if not title:
            return jsonify({'error': 'Title is required'}), 400

        # Check if audio files are provided
        audio_files = request.files.getlist('audioFiles')
        print(f"DEBUG: Received {len(audio_files)} audio files")

        if not audio_files or len(audio_files) == 0:
            return jsonify({'error': 'At least one audio file is required'}), 400

        # Check if any of the files have filenames
        has_valid_files = any(f.filename for f in audio_files)
        if not has_valid_files:
            return jsonify({'error': 'No valid audio files provided'}), 400

        # Handle cover upload
        cover_url = None
        if 'cover' in request.files:
            cover_file = request.files['cover']
            if cover_file.filename:
                print(f"DEBUG: Processing cover file: {cover_file.filename}")
                filename = generate_unique_filename(cover_file.filename)

                # Upload to Vercel Blob (or fallback to local storage)
                if blob_storage.is_blob_configured():
                    print("DEBUG: Using Vercel Blob storage for cover")
                    blob_path = blob_storage.generate_blob_path('covers', filename)
                    mime_type = cover_file.content_type or 'image/jpeg'
                    cover_url, _ = blob_storage.upload_file(cover_file, blob_path, mime_type)
                else:
                    # Fallback to local storage (for development)
                    print("DEBUG: Using local storage for cover")
                    cover_path = os.path.join(app.config['UPLOAD_FOLDER'], 'covers', filename)
                    os.makedirs(os.path.dirname(cover_path), exist_ok=True)
                    cover_file.save(cover_path)
                    cover_url = f'/uploads/covers/{filename}'
                print(f"DEBUG: Cover uploaded successfully: {cover_url}")

        # Create pack
        pack = AudioPack(
            user_id=user_id,
            title=title,
            genre=genre,
            bpm=bpm,
            musical_key=musical_key,
            cover_url=cover_url
        )
        db.session.add(pack)
        db.session.flush()
        print(f"DEBUG: Pack created with ID: {pack.id}")

        # Handle audio files
        uploaded_count = 0
        for i, audio_file in enumerate(audio_files):
            if audio_file.filename:
                print(f"DEBUG: Processing audio file {i+1}/{len(audio_files)}: {audio_file.filename}")
                filename = generate_unique_filename(audio_file.filename)

                # Upload to Vercel Blob (or fallback to local storage)
                if blob_storage.is_blob_configured():
                    print("DEBUG: Using Vercel Blob storage for audio")
                    blob_path = blob_storage.generate_blob_path('audio', filename)
                    mime_type = audio_file.content_type or 'audio/mpeg'
                    print(f"DEBUG: Audio MIME type: {mime_type}")
                    file_url, file_size = blob_storage.upload_file(audio_file, blob_path, mime_type)
                    print(f"DEBUG: Audio uploaded to blob: {file_url}, size: {file_size}")
                else:
                    # Fallback to local storage (for development)
                    print("DEBUG: Using local storage for audio")
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'audio', filename)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    audio_file.save(file_path)
                    file_url = f'/uploads/audio/{filename}'
                    print(f"DEBUG: Audio saved locally: {file_url}")

                audio_record = AudioFile(
                    pack_id=pack.id,
                    title=audio_file.filename,
                    file_url=file_url,  # Blob URL or local path
                    tokens_listen=1,
                    tokens_download=3
                )
                db.session.add(audio_record)
                uploaded_count += 1
                print(f"DEBUG: Audio file {i+1} added to database")

        print(f"DEBUG: Total files uploaded: {uploaded_count}")

        # Log activity
        activity = UserActivity(
            user_id=user_id,
            type='UPLOAD',
            entity_id=pack.id,
            entity_type='PACK'
        )
        db.session.add(activity)
        db.session.commit()

        print(f"DEBUG: Upload completed successfully for pack: {pack.title}")
        return jsonify({'success': True, 'pack': pack.to_dict()})

    except Exception as e:
        db.session.rollback()
        import traceback
        error_details = traceback.format_exc()
        print(f"ERROR: Upload failed: {e}")
        print(f"ERROR: Full traceback:\n{error_details}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

# ============ BEAT PAX FEED & PROFILE ROUTES ============

@app.route('/beatpax')
@login_required
def beatpax_feed():
    """Beat Pax marketplace feed - shows all uploaded packs"""
    return render_template('beatpax_feed.html')

@app.route('/profile/<int:user_id>')
@login_required
def user_profile(user_id):
    """User profile page showing their uploaded packs"""
    user = User.query.get_or_404(user_id)
    packs = AudioPack.query.filter_by(user_id=user_id).order_by(AudioPack.created_at.desc()).all()

    # Calculate total files across all packs
    total_files = sum(len(pack.files) for pack in packs)

    return render_template('user_profile.html', user=user, packs=packs, total_files=total_files)

# API: Get all packs for Beat Pax feed
@app.route('/api/beatpax/list', methods=['GET'])
@login_required
def beatpax_list():
    """Get all audio packs for the Beat Pax feed"""
    packs = AudioPack.query.order_by(AudioPack.created_at.desc()).all()
    return jsonify({'packs': [p.to_dict() for p in packs]})

# ============ DOWNLOADS ROUTES ============

@app.route('/downloads')
@login_required
def downloads():
    """Downloads page - shows user's downloaded packs by category"""
    return render_template('downloads.html')

# API: Get user downloads categorized
@app.route('/api/downloads/list', methods=['GET'])
@login_required
def downloads_list():
    """Get all user downloads categorized by Beats, Sound Pax, Music"""
    user_id = session.get('user_id')
    downloads = UserDownload.query.filter_by(user_id=user_id).order_by(UserDownload.downloaded_at.desc()).all()

    # Categorize downloads
    beats = []
    sound_pax = []
    music = []

    for download in downloads:
        download_dict = download.to_dict()
        if download.category == 'Beats':
            beats.append(download_dict)
        elif download.category == 'Music':
            music.append(download_dict)
        else:  # Default to Sound Pax
            sound_pax.append(download_dict)

    return jsonify({
        'beats': beats,
        'soundPax': sound_pax,
        'music': music
    })

# API: Get pack details with all audio files
@app.route('/api/packs/<int:pack_id>', methods=['GET'])
@login_required
def get_pack_details(pack_id):
    """Get detailed information about a pack including all audio files"""
    pack = AudioPack.query.get_or_404(pack_id)

    pack_data = pack.to_dict()
    pack_data['files'] = [file.to_dict() for file in pack.files]

    return jsonify(pack_data)

# API: Stream/Download audio file
@app.route('/api/audio/<int:file_id>', methods=['GET'])
@login_required
def get_audio_file(file_id):
    """Serve audio file for playback or download"""
    audio_file = AudioFile.query.get_or_404(file_id)
    download = request.args.get('download', 'false').lower() == 'true'

    # If using Blob storage, redirect to the blob URL
    if audio_file.file_url.startswith('http'):
        return jsonify({
            'url': audio_file.file_url,
            'title': audio_file.title,
            'download': download
        })

    # For local storage, serve the file directly
    file_path = audio_file.file_url.replace('/uploads/audio/', '')
    directory = os.path.join(app.config['UPLOAD_FOLDER'], 'audio')

    return send_from_directory(
        directory,
        file_path,
        as_attachment=download,
        download_name=audio_file.title if download else None
    )

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
        db.session.commit()

        return jsonify({'response': ai_response})

    except Exception as e:
        db.session.rollback()
        print(f"Error in chat endpoint: {e}")
        return jsonify({'error': 'An error occurred while processing your message'}), 500

@app.route('/chat-with-document', methods=['POST'])
@login_required
def chat_with_document():
    """Chat endpoint with document RAG support using OpenAI Assistants API"""
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
        user_message = "Please analyze the uploaded documents."

    if not ASSISTANT_ID or not VECTOR_STORE_ID:
        print(f"ERROR: Missing configuration - ASSISTANT_ID: {ASSISTANT_ID}, VECTOR_STORE_ID: {VECTOR_STORE_ID}")
        return jsonify({'error': 'Document RAG not configured. Please check environment variables.'}), 500

    print(f"DEBUG: Processing document RAG request - Message: '{user_message[:50]}...', Files: {len(uploaded_files)}")

    try:
        # Get or create thread for this session
        thread_id = get_or_create_thread(session_id)
        if not thread_id:
            return jsonify({'error': 'Failed to create conversation thread'}), 500

        # Process uploaded documents
        file_ids = []
        document_info = []

        if uploaded_files:
            print(f"DEBUG: Processing {len(uploaded_files)} uploaded files")
            for file in uploaded_files:
                if file and file.filename and allowed_document_file(file.filename):
                    print(f"DEBUG: Processing file: {file.filename}")
                    try:
                        # Upload to OpenAI Files API
                        print(f"DEBUG: Uploading {file.filename} to OpenAI...")
                        # OpenAI expects (filename, file_bytes) tuple
                        openai_file = client.files.create(
                            file=(file.filename, file.read(), file.content_type),
                            purpose='assistants'
                        )
                        print(f"DEBUG: OpenAI file created with ID: {openai_file.id}")
                        file_ids.append(openai_file.id)

                        # Reset file pointer for later use
                        file.seek(0)

                        # Add file to vector store
                        print(f"DEBUG: Adding file to vector store {VECTOR_STORE_ID}...")
                        client.vector_stores.files.create(
                            vector_store_id=VECTOR_STORE_ID,
                            file_id=openai_file.id
                        )
                        print(f"DEBUG: File added to vector store successfully")

                        # Reset file pointer before saving to database
                        file.seek(0)

                        # Save to database
                        print(f"DEBUG: Saving document to database...")
                        doc = save_document_upload(user_id, session_id, file, openai_file.id)
                        if doc:
                            print(f"DEBUG: Document saved: {doc.original_filename}")
                            document_info.append(f"- {doc.original_filename} ({doc.mime_type})")
                        else:
                            print(f"ERROR: Failed to save document to database")

                    except Exception as e:
                        print(f"ERROR uploading document {file.filename}: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    if file and file.filename:
                        print(f"DEBUG: File {file.filename} rejected - not an allowed document type")

        # Create user message record
        user_msg = ChatMessage(
            session_id=session_id,
            message_type='user',
            content=user_message,
            has_attachments=len(document_info) > 0,
            thread_id=thread_id,
            has_document_context=len(file_ids) > 0
        )
        db.session.add(user_msg)
        db.session.flush()

        # Build message content
        message_content = user_message
        if document_info:
            message_content += f"\n\n[Uploaded documents:\n" + "\n".join(document_info) + "]"

        # Add message to thread
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message_content,
            attachments=[{"file_id": fid, "tools": [{"type": "file_search"}]} for fid in file_ids]
        )

        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID
        )

        # Wait for completion
        max_wait_time = 30  # seconds
        poll_interval = 0.5  # seconds
        elapsed_time = 0

        while run.status in ['queued', 'in_progress'] and elapsed_time < max_wait_time:
            time.sleep(poll_interval)
            elapsed_time += poll_interval
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

        if run.status != 'completed':
            return jsonify({'error': f'Assistant run did not complete. Status: {run.status}'}), 500

        # Get the assistant's response
        messages = client.beta.threads.messages.list(thread_id=thread_id, limit=1)
        response_text, citations = process_assistant_response(messages)

        if not response_text:
            return jsonify({'error': 'Failed to process assistant response'}), 500

        # Create assistant message record
        assistant_msg = ChatMessage(
            session_id=session_id,
            message_type='assistant',
            content=response_text,
            thread_id=thread_id,
            run_id=run.id,
            has_document_context=len(citations) > 0,
            response_time_ms=int((time.time() - start_time) * 1000)
        )
        db.session.add(assistant_msg)
        db.session.commit()

        return jsonify({
            'response': response_text,
            'citations': citations,
            'thread_id': thread_id,
            'run_id': run.id,
            'has_document_context': len(citations) > 0
        })

    except Exception as e:
        db.session.rollback()
        print(f"ERROR in chat-with-document endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

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