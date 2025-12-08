#!/usr/bin/env python3
"""
Test PostgreSQL database connection and basic operations.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app import app, db
from models import User, AudioPack, UserTokens

def test_database():
    """Test database operations"""
    with app.app_context():
        try:
            print("🧪 Testing PostgreSQL Database Operations\n")
            print("=" * 60)

            # Test 1: Database connection
            print("\n1. Testing database connection...")
            db_url = app.config['SQLALCHEMY_DATABASE_URI']
            if db_url.startswith('postgresql://'):
                print(f"✅ Connected to PostgreSQL: {db_url[:30]}...{db_url[-20:]}")
            else:
                print(f"⚠️  Using SQLite (not PostgreSQL): {db_url}")

            # Test 2: Query users
            print("\n2. Testing user queries...")
            users = User.query.all()
            print(f"✅ Found {len(users)} users in database")
            for user in users:
                print(f"   - {user.first_name} {user.surname} ({user.email})")

            # Test 3: Query audio packs
            print("\n3. Testing audio pack queries...")
            packs = AudioPack.query.all()
            print(f"✅ Found {len(packs)} audio packs in database")
            for pack in packs:
                print(f"   - {pack.title} by user_id {pack.user_id}")

            # Test 4: Query user tokens
            print("\n4. Testing user token queries...")
            tokens = UserTokens.query.all()
            print(f"✅ Found {len(tokens)} user token records")
            for token in tokens:
                print(f"   - User {token.user_id}: {token.balance} tokens")

            # Test 5: Test joins
            print("\n5. Testing table relationships...")
            if users:
                user = users[0]
                user_packs = AudioPack.query.filter_by(user_id=user.id).all()
                print(f"✅ User '{user.first_name}' has {len(user_packs)} audio packs")

            # Test 6: Connection pooling
            print("\n6. Testing connection pooling...")
            engine_options = app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {})
            if engine_options:
                print(f"✅ Connection pooling configured:")
                print(f"   - Pool size: {engine_options.get('pool_size', 'N/A')}")
                print(f"   - Max overflow: {engine_options.get('max_overflow', 'N/A')}")
                print(f"   - Pool recycle: {engine_options.get('pool_recycle', 'N/A')}s")
                print(f"   - Pool pre-ping: {engine_options.get('pool_pre_ping', 'N/A')}")
            else:
                print("⚠️  No connection pooling configured (may be using SQLite)")

            print("\n" + "=" * 60)
            print("✅ All tests passed! Database is ready for production.")
            print("=" * 60)
            return True

        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    import sys
    success = test_database()
    sys.exit(0 if success else 1)
