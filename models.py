from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'surname': self.surname,
            'email': self.email,
            'phone_number': self.phone_number,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False, default='default')
    message_type = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    formatted_content = db.Column(db.Text)
    has_attachments = db.Column(db.Boolean, default=False)
    openai_thread_id = db.Column(db.String(100))
    openai_message_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    response_time_ms = db.Column(db.Integer)

    # RAG/Document support fields
    thread_id = db.Column(db.String(100))
    run_id = db.Column(db.String(100))
    has_document_context = db.Column(db.Boolean, default=False)

    # Relationship to attachments
    attachments = db.relationship('MessageAttachment', backref='message', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'message_type': self.message_type,
            'content': self.content,
            'formatted_content': self.formatted_content,
            'has_attachments': self.has_attachments,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'attachments': [att.to_dict() for att in self.attachments]
        }

class MessageAttachment(db.Model):
    __tablename__ = 'message_attachments'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('chat_messages.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100))
    thumbnail_path = db.Column(db.String(500))
    is_processed = db.Column(db.Boolean, default=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'thumbnail_path': self.thumbnail_path,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }

    @property
    def file_url(self):
        return f'/uploads/{self.filename}'

    @property
    def thumbnail_url(self):
        return f'/uploads/thumbnails/{self.thumbnail_path}' if self.thumbnail_path else None

    def delete_files(self):
        """Delete the actual files from filesystem"""
        try:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
            if self.thumbnail_path and os.path.exists(self.thumbnail_path):
                os.remove(self.thumbnail_path)
        except Exception as e:
            print(f"Error deleting files: {e}")

class Feedback(db.Model):
    __tablename__ = 'feedback'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Onboarding & First Impressions
    understand_clarity = db.Column(db.Integer)  # 1-5 scale
    start_ease = db.Column(db.Integer)  # 1-5 scale
    confusion_text = db.Column(db.Text)

    # User Experience & Interface
    design_rating = db.Column(db.Integer)  # 1-5 scale
    device_issues = db.Column(db.String(10))  # 'yes' or 'no'
    device_issues_text = db.Column(db.Text)
    interface_improvement = db.Column(db.Text)

    # Quality of Answers & Music Help
    answers_helpful = db.Column(db.Integer)  # 1-5 scale
    answers_tailored = db.Column(db.String(20))  # never/sometimes/often/always
    music_help_wanted = db.Column(db.Text)  # comma-separated or text

    # Speed, Reliability & Technical Performance
    response_speed = db.Column(db.Integer)  # 1-5 scale
    bugs_experienced = db.Column(db.String(10))  # 'yes' or 'no'
    bugs_text = db.Column(db.Text)
    slow_timing = db.Column(db.Text)  # comma-separated options

    # Overall Value, Features & Future Ideas
    use_again_likelihood = db.Column(db.Integer)  # 0-10 scale
    recommend_likelihood = db.Column(db.Integer)  # 0-10 scale
    top_feature_request = db.Column(db.Text)
    additional_comments = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'understand_clarity': self.understand_clarity,
            'start_ease': self.start_ease,
            'confusion_text': self.confusion_text,
            'design_rating': self.design_rating,
            'device_issues': self.device_issues,
            'device_issues_text': self.device_issues_text,
            'interface_improvement': self.interface_improvement,
            'answers_helpful': self.answers_helpful,
            'answers_tailored': self.answers_tailored,
            'music_help_wanted': self.music_help_wanted,
            'response_speed': self.response_speed,
            'bugs_experienced': self.bugs_experienced,
            'bugs_text': self.bugs_text,
            'slow_timing': self.slow_timing,
            'use_again_likelihood': self.use_again_likelihood,
            'recommend_likelihood': self.recommend_likelihood,
            'top_feature_request': self.top_feature_request,
            'additional_comments': self.additional_comments,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class UserProfile(db.Model):
    __tablename__ = 'user_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    avatar_url = db.Column(db.String(500))
    role = db.Column(db.String(50))
    bio = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='profile')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'display_name': self.display_name,
            'avatar_url': self.avatar_url,
            'role': self.role,
            'bio': self.bio,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class DocumentUpload(db.Model):
    __tablename__ = 'document_uploads'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100))
    chroma_doc_id = db.Column(db.String(100), unique=True)
    chunk_count = db.Column(db.Integer, default=0)
    file_path = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    is_processed = db.Column(db.Boolean, default=False)

    # Relationships
    user = db.relationship('User', backref='document_uploads')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'chroma_doc_id': self.chroma_doc_id,
            'chunk_count': self.chunk_count,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_processed': self.is_processed
        }

    def delete_file(self):
        """Delete the actual file from filesystem"""
        try:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
        except Exception as e:
            print(f"Error deleting document file: {e}")


class AdminMessage(db.Model):
    """Messages sent by users to the admin/Ask Chopper team"""
    __tablename__ = 'admin_messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    is_replied = db.Column(db.Boolean, default=False)
    admin_reply = db.Column(db.Text)
    replied_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to user
    user = db.relationship('User', backref='admin_messages')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': f"{self.user.first_name} {self.user.surname}" if self.user else None,
            'user_email': self.user.email if self.user else None,
            'subject': self.subject,
            'message': self.message,
            'is_read': self.is_read,
            'is_replied': self.is_replied,
            'admin_reply': self.admin_reply,
            'replied_at': self.replied_at.isoformat() if self.replied_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class SupportChat(db.Model):
    """Chat messages between users and admin support"""
    __tablename__ = 'support_chats'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sender_type = db.Column(db.String(20), nullable=False)  # 'user' or 'admin'
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to user
    user = db.relationship('User', backref='support_chats')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'sender_type': self.sender_type,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# =============================================================================
# Beatpax Models
# =============================================================================

class Beat(db.Model):
    """Beat content for the Beatpax marketplace"""
    __tablename__ = 'beats'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    audio_url = db.Column(db.String(500), nullable=False)
    cover_url = db.Column(db.String(500))
    genre = db.Column(db.String(50), nullable=False)
    bpm = db.Column(db.Integer)
    key = db.Column(db.String(10))
    tags = db.Column(db.String(500))  # Comma-separated tags
    token_cost = db.Column(db.Integer, nullable=False, default=5)
    play_count = db.Column(db.Integer, default=0)
    download_count = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', backref='beats')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'creator_id': self.creator_id,
            'creator_name': f"{self.creator.first_name} {self.creator.surname}" if self.creator else None,
            'audio_url': self.audio_url,
            'cover_url': self.cover_url,
            'genre': self.genre,
            'bpm': self.bpm,
            'key': self.key,
            'tags': self.tags.split(',') if self.tags else [],
            'token_cost': self.token_cost,
            'play_count': self.play_count,
            'download_count': self.download_count,
            'is_featured': self.is_featured,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Wallet(db.Model):
    """User token wallet for Beatpax"""
    __tablename__ = 'wallets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    balance = db.Column(db.Integer, nullable=False, default=50)  # New user bonus
    total_spent = db.Column(db.Integer, nullable=False, default=0)
    total_earned = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = db.relationship('User', backref='wallet')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'balance': self.balance,
            'total_spent': self.total_spent,
            'total_earned': self.total_earned,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Transaction(db.Model):
    """Token transaction history for Beatpax"""
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # 'purchase', 'spend', 'earn', 'bonus'
    amount = db.Column(db.Integer, nullable=False)  # Positive for credits, negative for debits
    balance_after = db.Column(db.Integer, nullable=False)
    reference_type = db.Column(db.String(50))  # 'beat_download', 'beat_sale', 'token_purchase', 'signup_bonus'
    reference_id = db.Column(db.Integer)  # ID of related beat or package
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    user = db.relationship('User', backref='transactions')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'transaction_type': self.transaction_type,
            'amount': self.amount,
            'balance_after': self.balance_after,
            'reference_type': self.reference_type,
            'reference_id': self.reference_id,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class UserBeatLibrary(db.Model):
    """User's purchased/downloaded beats"""
    __tablename__ = 'user_beat_library'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    beat_id = db.Column(db.Integer, db.ForeignKey('beats.id'), nullable=False)
    tokens_spent = db.Column(db.Integer, nullable=False)
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)
    downloaded_at = db.Column(db.DateTime)
    download_count = db.Column(db.Integer, default=0)

    # Relationships
    user = db.relationship('User', backref='beat_library')
    beat = db.relationship('Beat', backref='purchases')

    # Unique constraint to prevent duplicate purchases
    __table_args__ = (db.UniqueConstraint('user_id', 'beat_id', name='unique_user_beat'),)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'beat_id': self.beat_id,
            'beat': self.beat.to_dict() if self.beat else None,
            'tokens_spent': self.tokens_spent,
            'purchased_at': self.purchased_at.isoformat() if self.purchased_at else None,
            'downloaded_at': self.downloaded_at.isoformat() if self.downloaded_at else None,
            'download_count': self.download_count
        }