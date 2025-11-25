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
from models import db, ChatMessage, MessageAttachment, User, Feedback

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key-here-change-in-production")
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:////tmp/ask_chopper.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'

CORS(app)

# Initialize database
db.init_app(app)
migrate = Migrate(app, db)

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
    """Process and save uploaded file"""
    if not file or not allowed_file(file.filename):
        return None

    try:
        # Generate unique filename
        filename = generate_unique_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'attachments', filename)

        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Save file
        file.save(file_path)

        # Get file info
        file_size = os.path.getsize(file_path)
        mime_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

        # Create thumbnail for images
        thumbnail_path = None
        if mime_type.startswith('image/'):
            thumbnail_filename = f"thumb_{filename}"
            thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbnails', thumbnail_filename)
            os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)

            if create_thumbnail(file_path, thumbnail_path):
                thumbnail_path = thumbnail_filename
            else:
                thumbnail_path = None

        # Create database record
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
        return None

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

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/chat/history')
@login_required
def chat_history():
    """Get chat history for current session"""
    session_id = session.get('session_id', 'default')
    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.created_at).all()
    return jsonify([msg.to_dict() for msg in messages])

# Create database tables on app startup
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)