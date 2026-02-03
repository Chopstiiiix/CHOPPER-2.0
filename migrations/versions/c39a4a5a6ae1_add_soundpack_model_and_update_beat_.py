"""Add SoundPack model and update Beat model

Revision ID: c39a4a5a6ae1
Revises:
Create Date: 2026-02-03 01:54:16.084383

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c39a4a5a6ae1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create sound_packs table if it doesn't exist
    op.execute("""
        CREATE TABLE IF NOT EXISTS sound_packs (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            creator_id INTEGER NOT NULL REFERENCES users(id),
            cover_url VARCHAR(500),
            genre VARCHAR(50) NOT NULL,
            description TEXT,
            tags VARCHAR(500),
            token_cost INTEGER NOT NULL DEFAULT 10,
            play_count INTEGER DEFAULT 0,
            download_count INTEGER DEFAULT 0,
            track_count INTEGER DEFAULT 0,
            is_featured BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add sound_pack_id column to beats if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'beats' AND column_name = 'sound_pack_id'
            ) THEN
                ALTER TABLE beats ADD COLUMN sound_pack_id INTEGER REFERENCES sound_packs(id);
            END IF;
        END $$;
    """)

    # Add track_number column to beats if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'beats' AND column_name = 'track_number'
            ) THEN
                ALTER TABLE beats ADD COLUMN track_number INTEGER;
            END IF;
        END $$;
    """)


def downgrade():
    # Remove columns from beats
    op.execute("ALTER TABLE beats DROP COLUMN IF EXISTS track_number")
    op.execute("ALTER TABLE beats DROP COLUMN IF EXISTS sound_pack_id")

    # Drop sound_packs table
    op.execute("DROP TABLE IF EXISTS sound_packs")
