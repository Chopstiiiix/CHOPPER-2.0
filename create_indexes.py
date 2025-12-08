#!/usr/bin/env python3
"""
Create database indexes for optimal query performance.
This script adds indexes to frequently queried columns.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app import app, db

def create_indexes():
    """Create indexes on commonly queried columns"""
    with app.app_context():
        try:
            print("Creating database indexes for optimal performance...\n")

            # List of indexes to create
            indexes = [
                # Users table
                ("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)", "users.email"),

                # Chat messages table
                ("CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id)", "chat_messages.session_id"),
                ("CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_id ON chat_messages(thread_id)", "chat_messages.thread_id"),
                ("CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at DESC)", "chat_messages.created_at"),

                # Message attachments table
                ("CREATE INDEX IF NOT EXISTS idx_message_attachments_message_id ON message_attachments(message_id)", "message_attachments.message_id"),

                # User tokens table
                ("CREATE INDEX IF NOT EXISTS idx_user_tokens_user_id ON user_tokens(user_id)", "user_tokens.user_id"),

                # Audio packs table
                ("CREATE INDEX IF NOT EXISTS idx_audio_packs_user_id ON audio_packs(user_id)", "audio_packs.user_id"),
                ("CREATE INDEX IF NOT EXISTS idx_audio_packs_created_at ON audio_packs(created_at DESC)", "audio_packs.created_at"),

                # Audio files table
                ("CREATE INDEX IF NOT EXISTS idx_audio_files_pack_id ON audio_files(pack_id)", "audio_files.pack_id"),

                # User activity table
                ("CREATE INDEX IF NOT EXISTS idx_user_activity_user_id ON user_activity(user_id)", "user_activity.user_id"),
                ("CREATE INDEX IF NOT EXISTS idx_user_activity_created_at ON user_activity(created_at DESC)", "user_activity.created_at"),

                # User downloads table
                ("CREATE INDEX IF NOT EXISTS idx_user_downloads_user_id ON user_downloads(user_id)", "user_downloads.user_id"),
                ("CREATE INDEX IF NOT EXISTS idx_user_downloads_pack_id ON user_downloads(pack_id)", "user_downloads.pack_id"),

                # Document uploads table
                ("CREATE INDEX IF NOT EXISTS idx_document_uploads_user_id ON document_uploads(user_id)", "document_uploads.user_id"),
                ("CREATE INDEX IF NOT EXISTS idx_document_uploads_session_id ON document_uploads(session_id)", "document_uploads.session_id"),

                # Feedback table
                ("CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback(user_id)", "feedback.user_id"),
            ]

            # Execute each index creation
            for sql, description in indexes:
                try:
                    db.session.execute(db.text(sql))
                    print(f"✅ Created index on {description}")
                except Exception as e:
                    print(f"⚠️  Index on {description} - {str(e)[:50]}")

            db.session.commit()
            print("\n✅ All indexes created successfully!")
            return True

        except Exception as e:
            print(f"\n❌ Error creating indexes: {e}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    import sys
    success = create_indexes()
    sys.exit(0 if success else 1)
