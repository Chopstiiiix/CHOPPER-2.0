# Vercel Blob Storage Setup Guide

**Status:** ✅ Code Migration Complete - Ready for Production

---

## Overview

Your Ask-Chopper application has been migrated from local file storage to Vercel Blob storage for production deployment. This guide explains how to set up and use Blob storage.

---

## Why Vercel Blob?

### Problem with Local Storage on Vercel
- Vercel runs **serverless functions** - each request creates a new instance
- Local file system is **ephemeral** (temporary)
- Files uploaded to `/uploads` directory are **lost after function execution**
- **No persistent storage** across deployments

### Solution: Vercel Blob
- **Cloud object storage** - files persist permanently
- **Direct CDN URLs** - fast global access
- **Automatic scaling** - handles any number of files
- **Built for serverless** - perfect for Vercel deployments

---

## What Was Migrated

### File Types Handled
1. **Chat Attachments** - Files uploaded in chat messages
2. **Audio Files** - Music/beat packs uploaded by users
3. **Cover Images** - Pack cover artwork
4. **Document Uploads** - Files for RAG (Retrieval Augmented Generation)
5. **Thumbnails** - Auto-generated image thumbnails

### Code Changes
All file upload functions now:
- Upload to Vercel Blob storage (production)
- Fall back to local storage (development)
- Store Blob URLs in database instead of local paths
- Handle thumbnails in cloud storage

---

## Setup Instructions

### Step 1: Create Vercel Blob Storage

#### Option A: Via Vercel Dashboard (Recommended)
1. Go to https://vercel.com/dashboard
2. Select your project
3. Navigate to **Storage** tab
4. Click **Create Database** → Select **Blob**
5. Click **Create Store**
6. Copy the `BLOB_READ_WRITE_TOKEN` that appears

#### Option B: Via Vercel CLI
```bash
# In your project directory
vercel storage blob create
```

---

### Step 2: Set Environment Variable

#### For Vercel (Production)
```bash
# Set the token in Vercel
echo "your_blob_token_here" | vercel env add BLOB_READ_WRITE_TOKEN production
```

#### For Local Development
Add to your `.env` file:
```bash
BLOB_READ_WRITE_TOKEN=your_blob_token_here
```

**Note:** Without this token set, the app will fall back to local file storage (development mode).

---

### Step 3: Verify Setup

Run the test script:
```bash
python3 test_blob_storage.py
```

Expected output:
```
✅ Blob storage configured
✅ Test file upload successful
✅ File accessible via URL
```

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────────┐
│          User Uploads File                  │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│      Flask App (app.py)                     │
│  ┌───────────────────────────────────────┐ │
│  │  Check: blob_storage.is_configured()  │ │
│  └───────────┬───────────────────────────┘ │
│              │                              │
│    ┌─────────┴─────────┐                   │
│    │ Yes (Production)  │ No (Development) │
│    ▼                   ▼                   │
│  ┌─────────────────┐ ┌──────────────────┐│
│  │ Upload to Blob  │ │ Save to /uploads ││
│  │ Get Blob URL    │ │ Get local path   ││
│  └────────┬────────┘ └────────┬─────────┘│
│           │                   │           │
│           └───────────┬───────┘           │
│                       ▼                   │
│           Store URL/path in Database     │
└─────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│  PostgreSQL Database (Neon)                 │
│  - file_path: Blob URL or local path        │
│  - file_size, mime_type, metadata          │
└─────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│  User Accesses File                         │
│  - Direct Blob URL (production)             │
│  - /uploads/<file> (development)            │
└─────────────────────────────────────────────┘
```

### File Upload Flow

1. **User uploads file** → Flask endpoint receives file
2. **Check Blob configured** → `blob_storage.is_blob_configured()`
3. **If YES (Production):**
   - Upload file to Vercel Blob
   - Get public Blob URL (e.g., `https://abc123.public.blob.vercel-storage.com/audio/file.mp3`)
   - Store Blob URL in database `file_path` column
4. **If NO (Development):**
   - Save file to local `/uploads` directory
   - Store local path in database `file_path` column
5. **User accesses file** → Direct URL (Blob) or `/uploads/<file>` (local)

---

## Blob Storage Limits

### Free Tier (Hobby Plan)
- **Storage:** 1 GB
- **Bandwidth:** 10 GB/month
- **Read Operations:** Unlimited
- **Write Operations:** Unlimited

### Pro Plan ($20/month)
- **Storage:** 100 GB
- **Bandwidth:** 1 TB/month
- Everything else unlimited

### Monitoring Usage
```bash
# Check current usage
vercel storage ls
```

Or check Vercel Dashboard → Storage → Blob → Usage

---

## File Organization

Files are organized in Blob storage by category:

```
blob-storage/
├── audio/              # Audio/music files
│   ├── track1_20251208_a1b2c3d4.mp3
│   └── beat2_20251208_e5f6g7h8.wav
├── covers/             # Pack cover images
│   ├── cover1_20251208_i9j0k1l2.jpg
│   └── cover2_20251208_m3n4o5p6.png
├── documents/          # RAG documents
│   ├── doc1_20251208_q7r8s9t0.pdf
│   └── guide_20251208_u1v2w3x4.txt
├── attachments/        # Chat attachments
│   ├── file1_20251208_y5z6a7b8.png
│   └── data_20251208_c9d0e1f2.csv
└── thumbnails/         # Auto-generated thumbnails
    ├── thumb_cover1_20251208_g3h4i5j6.jpg
    └── thumb_file1_20251208_k7l8m9n0.jpg
```

**Note:** Filenames include timestamp and unique ID to prevent collisions.

---

## Code Reference

### blob_storage.py Module

Main functions:

```python
# Upload a file from Flask request
blob_url, file_size = blob_storage.upload_file(
    file=request.files['file'],
    path='audio/myfile.mp3',
    content_type='audio/mpeg'
)

# Upload raw bytes
blob_url = blob_storage.upload_bytes(
    data=b'file content',
    path='documents/doc.pdf',
    content_type='application/pdf'
)

# Upload thumbnail (auto-resize)
blob_url = blob_storage.upload_thumbnail(
    image_path_or_file=image_file,
    thumbnail_path='thumbnails/thumb.jpg',
    size=(150, 150)
)

# Delete a file
success = blob_storage.delete_file(blob_url)

# Get file info/metadata
info = blob_storage.get_file_info(blob_url)
```

### Updated Endpoints

All these endpoints now use Blob storage:

- `POST /chat` - Chat attachments
- `POST /chat-with-document` - Document uploads
- `POST /api/packs/upload` - Audio files and covers

---

## Testing

### Test File Upload (Development)
```bash
# Start app locally
python3 app.py

# Upload a test file via curl
curl -X POST http://localhost:8000/api/packs/upload \
  -F "title=Test Pack" \
  -F "genre=Test" \
  -F "cover=@test-image.jpg" \
  -F "audioFiles=@test-audio.mp3" \
  -H "Cookie: session=your_session"
```

### Test in Production
1. Deploy to Vercel: `vercel --prod`
2. Visit your production URL
3. Register/login
4. Try uploading:
   - Audio pack with cover
   - Chat attachment
   - Document for RAG

---

## Troubleshooting

### Error: "Vercel Blob storage not configured"
**Cause:** `BLOB_READ_WRITE_TOKEN` not set
**Solution:**
```bash
# Set the token
echo "your_token" | vercel env add BLOB_READ_WRITE_TOKEN production
# Redeploy
vercel --prod
```

### Error: "Failed to upload file to Blob storage"
**Possible causes:**
1. Invalid token
2. Network issue
3. File too large (>500MB single file limit)
4. Rate limiting (unlikely)

**Solution:**
- Check token is correct
- Check file size
- Check Vercel logs: `vercel logs --prod`

### Files not accessible after upload
**Cause:** URLs might be stored as local paths
**Solution:**
- Verify `BLOB_READ_WRITE_TOKEN` is set correctly
- Check database `file_path` column - should contain `https://` URLs
- Redeploy with correct token

### Development mode keeps using local storage
**This is correct!** Without `BLOB_READ_WRITE_TOKEN` set in `.env`, the app uses local storage for development.

To test Blob storage locally:
1. Add `BLOB_READ_WRITE_TOKEN` to `.env`
2. Restart the app
3. Upload files - they'll go to Blob

---

## Migration from Local Storage

If you have existing files in `/uploads`:

### Option 1: Manual Migration Script
```bash
python3 migrate_files_to_blob.py
```

This script will:
1. Find all files in `/uploads`
2. Upload each to Vercel Blob
3. Update database records with Blob URLs

### Option 2: Let users re-upload
For a small number of files, it might be easier to have users re-upload.

---

## Security Considerations

### Access Control
- All Blob files are **publicly accessible** via URL
- URLs are hard to guess (random suffixes)
- For sensitive files, consider:
  - Token-based access URLs
  - Signed URLs with expiration
  - Private blob stores (requires authentication)

### Best Practices
1. **Don't store secrets** in uploaded files
2. **Validate file types** before upload (already implemented)
3. **Limit file sizes** (already implemented: 16MB max)
4. **Rotate Blob tokens** periodically
5. **Monitor usage** to detect abuse

---

## Cost Optimization

### Tips to Stay Within Free Tier
1. **Compress images** before upload (consider adding)
2. **Limit file sizes** (already done: 16MB max)
3. **Delete unused files** periodically
4. **Use thumbnails** for previews (already implemented)
5. **Monitor usage** regularly

### When to Upgrade
Upgrade to Pro plan if:
- Storage > 1 GB
- Bandwidth > 10 GB/month
- You have paying users
- You need SLA guarantees

---

## Environment Variables Summary

| Variable | Required | Purpose | Where to Set |
|----------|----------|---------|--------------|
| `BLOB_READ_WRITE_TOKEN` | Yes (prod) | Vercel Blob access token | Vercel dashboard |
| `DATABASE_URL` | Yes | PostgreSQL connection | Already set |
| `OPENAI_API_KEY` | Yes | OpenAI API access | Already set |
| `SECRET_KEY` | Yes | Session encryption | Already set |

---

## Next Steps

1. ✅ **Code migration complete** - All upload functions use Blob storage
2. **Set BLOB_READ_WRITE_TOKEN** in Vercel (do this now)
3. **Deploy to production** - `vercel --prod`
4. **Test file uploads** in production
5. **Monitor usage** via Vercel dashboard

---

## Support & Resources

- Vercel Blob Docs: https://vercel.com/docs/storage/vercel-blob
- Python SDK Docs: https://github.com/vercel/storage/tree/main/packages/blob#python
- Vercel Support: https://vercel.com/support
- Pricing: https://vercel.com/docs/storage/vercel-blob/usage-and-pricing

---

## Rollback Plan

If Blob storage causes issues:

1. **Remove BLOB_READ_WRITE_TOKEN** from Vercel env
2. **Redeploy** - app will use local storage
3. **Note:** This won't work on Vercel serverless!
4. **Better:** Fix the Blob issue, as local storage won't work in production

---

## Summary

✅ **Completed:**
- Installed `vercel-blob` Python SDK
- Created `blob_storage.py` helper module
- Updated all file upload functions
- Updated file serving logic
- Added fallback to local storage for development
- Maintained backward compatibility

⏳ **TODO:**
- Set `BLOB_READ_WRITE_TOKEN` in Vercel
- Deploy to production
- Test file uploads in production

---

**Last Updated:** 2025-12-08
**Status:** Ready for Production
**Next Critical Step:** Set BLOB_READ_WRITE_TOKEN in Vercel
