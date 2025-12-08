#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL.
This script copies all existing data from the old SQLite database to the new PostgreSQL database.
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

from models import (
    User, ChatMessage, MessageAttachment, Feedback,
    UserProfile, UserTokens, AudioPack, AudioFile,
    UserActivity, UserDownload, DocumentUpload
)

def migrate_data():
    """Migrate data from SQLite to PostgreSQL"""
    try:
        # SQLite connection (old database)
        sqlite_path = 'instance/ask_chopper.db'
        if not os.path.exists(sqlite_path):
            print(f"❌ SQLite database not found at: {sqlite_path}")
            return False

        sqlite_uri = f'sqlite:///{sqlite_path}'
        sqlite_engine = create_engine(sqlite_uri)
        SQLiteSession = sessionmaker(bind=sqlite_engine)
        sqlite_session = SQLiteSession()

        # PostgreSQL connection (new database)
        postgres_uri = os.environ.get('DATABASE_URL', '')
        if postgres_uri.startswith('postgres://'):
            postgres_uri = postgres_uri.replace('postgres://', 'postgresql://', 1)

        postgres_engine = create_engine(postgres_uri)
        PostgresSession = sessionmaker(bind=postgres_engine)
        postgres_session = PostgresSession()

        print("🔄 Starting data migration from SQLite to PostgreSQL...\n")

        # Models to migrate in order (respecting foreign keys)
        models_to_migrate = [
            (User, 'users'),
            (ChatMessage, 'chat_messages'),
            (MessageAttachment, 'message_attachments'),
            (Feedback, 'feedback'),
            (UserProfile, 'user_profiles'),
            (UserTokens, 'user_tokens'),
            (AudioPack, 'audio_packs'),
            (AudioFile, 'audio_files'),
            (UserActivity, 'user_activity'),
            (UserDownload, 'user_downloads'),
            (DocumentUpload, 'document_uploads'),
        ]

        total_migrated = 0

        for model, table_name in models_to_migrate:
            try:
                # Get all records from SQLite
                records = sqlite_session.query(model).all()

                if records:
                    print(f"📦 Migrating {len(records)} records from {table_name}...")

                    # Copy each record to PostgreSQL
                    for record in records:
                        # Create a new instance with the same data
                        record_dict = {}
                        for column in model.__table__.columns:
                            value = getattr(record, column.name)
                            record_dict[column.name] = value

                        new_record = model(**record_dict)
                        postgres_session.add(new_record)

                    postgres_session.commit()
                    print(f"✅ Migrated {len(records)} records from {table_name}")
                    total_migrated += len(records)
                else:
                    print(f"⏭️  No records to migrate from {table_name}")

            except Exception as e:
                print(f"⚠️  Error migrating {table_name}: {e}")
                postgres_session.rollback()

        print(f"\n✅ Migration complete! Total records migrated: {total_migrated}")

        # Close sessions
        sqlite_session.close()
        postgres_session.close()

        return True

    except Exception as e:
        print(f"\n❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("SQLite to PostgreSQL Data Migration")
    print("=" * 60)
    print()

    success = migrate_data()
    sys.exit(0 if success else 1)
