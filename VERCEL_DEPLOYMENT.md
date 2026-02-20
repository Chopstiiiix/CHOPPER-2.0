# Vercel Deployment Guide for Ask Chopper

## Problem: SQLite doesn't work on Vercel

Vercel uses serverless functions with **read-only filesystems**. SQLite requires write access, so it **cannot be used on Vercel**.

**Error**: `sqlite3.OperationalError: attempt to write a readonly database`

---

## Solution: Use Vercel Postgres

### Step 1: Create Vercel Postgres Database

1. Go to your Vercel project dashboard
2. Navigate to **Storage** tab
3. Click **Create Database**
4. Select **Postgres**
5. Choose a region (closest to your users)
6. Click **Create**

### Step 2: Connect Database to Project

Vercel will automatically add these environment variables:
```
POSTGRES_URL
POSTGRES_PRISMA_URL
POSTGRES_URL_NON_POOLING
POSTGRES_USER
POSTGRES_HOST
POSTGRES_PASSWORD
POSTGRES_DATABASE
```

### Step 3: Update Environment Variables

In your Vercel project settings, add:

```bash
# Use Postgres URL instead of SQLite
DATABASE_URL=<POSTGRES_PRISMA_URL from Vercel>

# Your existing variables
ANTHROPIC_API_KEY=sk-proj-...
OPENAI_ASSISTANT_ID=asst_kxFVifKEzOsV2cAYwSupMkyx
OPENAI_VECTOR_STORE_ID=vs_692eef58ffb48191801aa6b8eece21c1
SECRET_KEY=your_production_secret_key_here
```

### Step 4: Update Database Configuration

The app now detects the Vercel environment and skips `db.create_all()` to avoid the read-only error.

Update `app.py` database configuration:

```python
# Configure database URI
db_url = os.environ.get('DATABASE_URL', '')

if 'postgres' in db_url:
    # PostgreSQL (Vercel production)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
elif db_url.startswith('file:'):
    # SQLite (local development - Prisma format)
    db_path = db_url.replace('file:', '')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
else:
    # Default SQLite (local development)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ask_chopper.db'
```

### Step 5: Initialize Database on Vercel

After deploying, initialize the database:

**Option A**: Use Prisma (Recommended)
```bash
# Install dependencies
npm install

# Push schema to Vercel Postgres
npx prisma db push --accept-data-loss

# Seed data (optional)
node seed.js
```

**Option B**: Use Flask-Migrate
```bash
# Create migrations
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

**Option C**: Manual SQL
Connect to Vercel Postgres and run:
```sql
-- Copy SQL from your local SQLite dump
-- Or use Prisma Studio to inspect schema
```

### Step 6: Redeploy

```bash
git add .
git commit -m "Fix Vercel deployment - use Postgres instead of SQLite"
git push origin master
```

Vercel will automatically redeploy.

---

## Alternative: Use Supabase (Free Postgres)

If you want a free PostgreSQL database:

1. **Sign up**: https://supabase.com
2. **Create project**
3. **Get connection string** from Settings → Database
4. **Add to Vercel** environment variables:
   ```
   DATABASE_URL=postgresql://user:pass@db.xxx.supabase.co:5432/postgres
   ```

---

## Alternative: Use PlanetScale (MySQL)

1. **Sign up**: https://planetscale.com
2. **Create database**
3. **Get connection string**
4. **Update** app.py to support MySQL:
   ```python
   # Install: pip install pymysql
   app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://...'
   ```

---

## Testing Locally with Postgres

To test PostgreSQL locally before deploying:

```bash
# Install PostgreSQL
brew install postgresql  # macOS
# or
sudo apt install postgresql  # Ubuntu

# Start PostgreSQL
brew services start postgresql  # macOS

# Create database
createdb ask_chopper

# Update .env
DATABASE_URL=postgresql://localhost/ask_chopper

# Run migrations
npx prisma db push

# Test app
python3 app.py
```

---

## Troubleshooting

### Error: "relation 'users' does not exist"
**Solution**: Database tables not created. Run `npx prisma db push`

### Error: "SSL required"
**Solution**: Add `?sslmode=require` to DATABASE_URL

### Error: "Connection refused"
**Solution**: Check Vercel Postgres is running and credentials are correct

### Error: "Too many connections"
**Solution**: Use Vercel's pooling URL (`POSTGRES_PRISMA_URL`)

---

## Production Checklist

Before going live:

- ✅ Vercel Postgres database created
- ✅ Environment variables configured
- ✅ Database schema pushed (`prisma db push`)
- ✅ Sample data seeded (if needed)
- ✅ `VERCEL=true` environment variable set
- ✅ `db.create_all()` skipped on Vercel
- ✅ Database connection tested
- ✅ All endpoints working

---

## Cost Considerations

**Vercel Postgres Pricing**:
- Hobby: Free (60 hours compute/month)
- Pro: $20/month (100 hours)

**Supabase**:
- Free: 500MB database, 2GB bandwidth
- Pro: $25/month (8GB database, 250GB bandwidth)

**PlanetScale**:
- Hobby: Free (5GB storage, 1 billion row reads)
- Scaler: $29/month (10GB storage, 10 billion row reads)

---

## Current Status

✅ **Fixed**: Code updated to skip `db.create_all()` on Vercel
✅ **Ready**: vercel.json configuration added
⏳ **Pending**: Vercel Postgres setup (follow Step 1 above)

---

## Support

**Vercel Docs**: https://vercel.com/docs/storage/vercel-postgres
**Prisma with Postgres**: https://www.prisma.io/docs/concepts/database-connectors/postgresql
**Flask-SQLAlchemy**: https://flask-sqlalchemy.palletsprojects.com/

---

*Last Updated: 2025-12-02*
