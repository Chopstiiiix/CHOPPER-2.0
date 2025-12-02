# Database Review and Fixes Summary

## Issues Found and Fixed

### 1. Incomplete Prisma Schema
**Problem:** The Prisma schema was missing 6 tables that the Flask app expected:
- `user_profiles`
- `user_tokens`
- `audio_packs`
- `audio_files`
- `user_activity`
- `user_downloads`

**Fix:** Updated `prisma/schema.prisma` to include all 10 tables with proper relationships.

### 2. Database Location Issue
**Problem:** Database was stored in `/tmp/ask_chopper.db` which gets cleared on system restart, causing data loss.

**Fix:**
- Moved database to project root: `./ask_chopper.db`
- Updated `.env` to use `DATABASE_URL="file:./ask_chopper.db"`
- Updated `app.py` to use project directory for database and uploads

### 3. Database URL Format Mismatch
**Problem:** Prisma uses `file:` prefix while Flask-SQLAlchemy uses `sqlite:///` prefix.

**Fix:** Modified `app.py` to automatically convert Prisma format to Flask format:
```python
db_url = os.environ.get('DATABASE_URL', '')
if db_url.startswith('file:'):
    db_path = db_url.replace('file:', '')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
```

### 4. Upload Folder Location
**Problem:** Upload folder was in `/tmp/uploads` which gets cleared on restart.

**Fix:** Changed to project directory: `./uploads`

## Database Structure (After Fixes)

The database now contains **10 tables**:

1. **users** - User accounts (id, email, password, profile info)
2. **chat_messages** - Chat conversation history
3. **message_attachments** - File attachments for chat messages
4. **feedback** - User feedback submissions
5. **user_profiles** - Extended user profile information
6. **user_tokens** - Token balance for marketplace
7. **audio_packs** - Audio pack listings
8. **audio_files** - Individual audio files in packs
9. **user_activity** - Activity log (listens, downloads, uploads)
10. **user_downloads** - Track downloaded packs by category

## Files Modified

1. **prisma/schema.prisma** - Added 6 missing models with relationships
2. **.env** - Updated DATABASE_URL to use project directory
3. **app.py** - Fixed database URI handling and upload folder location

## Verification Results

✓ All tables exist in database
✓ Foreign key constraints valid
✓ Database integrity check passed
✓ Prisma schema valid
✓ Flask-SQLAlchemy models load correctly
✓ Database URI correctly configured

## Recommendations

### 1. Set up Migrations
Consider using Flask-Migrate or Prisma Migrate for future schema changes:
```bash
# For Flask-Migrate
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# For Prisma Migrate
npx prisma migrate dev --name init
```

### 2. Update Prisma Version
Prisma has a new major version available (7.0.1):
```bash
npm i --save-dev prisma@latest
npm i @prisma/client@latest
```

### 3. Add Database to .gitignore
Make sure `ask_chopper.db` is in `.gitignore` to avoid committing local data:
```
ask_chopper.db
uploads/
```

### 4. Backup Strategy
Implement regular database backups since SQLite uses a single file:
```bash
# Simple backup script
sqlite3 ask_chopper.db ".backup 'backups/ask_chopper_$(date +%Y%m%d_%H%M%S).db'"
```

### 5. Environment Variables
Update the SECRET_KEY in production - currently using a default value.

## Testing the Database

To verify everything works:
```bash
# Test Prisma connection
npx prisma studio

# Test Flask connection
python3 -c "from app import app, db; print('Database connected:', app.config['SQLALCHEMY_DATABASE_URI'])"

# Check database tables
sqlite3 ask_chopper.db ".tables"
```

## Database Location
- **New location:** `./ask_chopper.db` (project root)
- **Old location:** `/tmp/ask_chopper.db` (deprecated, data lost on restart)
- **Backup location:** `./instance/ask_chopper.db` (old Flask default, has incomplete schema)
