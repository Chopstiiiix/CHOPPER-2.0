#!/usr/bin/env python3
"""
Initialize PostgreSQL database with all tables.
This script creates all tables defined in models.py in the PostgreSQL database.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import app and db
from app import app, db
from models import (
    User, ChatMessage, MessageAttachment, Feedback,
    UserProfile, UserTokens, AudioPack, AudioFile,
    UserActivity, UserDownload, DocumentUpload
)

def init_database():
    """Initialize database with all tables"""
    with app.app_context():
        try:
            # Get database URL
            db_url = app.config['SQLALCHEMY_DATABASE_URI']
            print(f"Database URL: {db_url[:30]}...{db_url[-20:]}")  # Hide credentials

            # Test connection
            print("\n1. Testing database connection...")
            db.engine.connect()
            print("✅ Database connection successful!")

            # Create all tables
            print("\n2. Creating database tables...")
            db.create_all()
            print("✅ All tables created successfully!")

            # List all tables
            print("\n3. Verifying tables...")
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"✅ Found {len(tables)} tables:")
            for table in tables:
                print(f"   - {table}")

            print("\n✅ Database initialization complete!")
            return True

        except Exception as e:
            print(f"\n❌ Error initializing database: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = init_database()
    sys.exit(0 if success else 1)
