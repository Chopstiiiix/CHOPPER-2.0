# Ask-Chopper Production Deployment Guide

**Last Updated:** 2025-12-08
**Status:** Ready for Production Deployment

---

## Overview

This guide walks you through deploying Ask-Chopper to Vercel for production testing with 10 concurrent users.

---

## Pre-Deployment Checklist

### ✅ Completed
- [x] Database migrated to Neon PostgreSQL
- [x] Connection pooling configured
- [x] Database indexes created
- [x] File storage migrated to Vercel Blob
- [x] Code updated for Blob storage
- [x] Strong SECRET_KEY generated
- [x] Dependencies updated (requirements.txt)

### ⏳ To Complete
- [ ] Create Vercel Blob storage
- [ ] Set all environment variables in Vercel
- [ ] Deploy to Vercel production
- [ ] Test all functionality
- [ ] Monitor for 24 hours

---

## Step-by-Step Deployment

### Step 1: Login to Vercel CLI

```bash
vercel login
```

Follow the authentication prompts.

---

### Step 2: Link Your Project

If this is your first deployment:

```bash
vercel link
```

Follow the prompts:
- Set up and deploy? **Yes**
- Which scope? Select your account
- Link to existing project? **No** (if new) or **Yes** (if existing)
- Project name? **ask-chopper** (or your preferred name)

---

### Step 3: Create Vercel Blob Storage

#### Option A: Via Vercel Dashboard

1. Go to https://vercel.com/dashboard
2. Select your project
3. Click **Storage** tab
4. Click **Create Database** → **Blob**
5. Name it (e.g., "ask-chopper-storage")
6. Click **Create**
7. **Copy the BLOB_READ_WRITE_TOKEN** that appears

#### Option B: Via CLI

```bash
vercel storage blob create ask-chopper-storage
```

Copy the token that's displayed.

---

### Step 4: Set All Environment Variables

Run each command one by one:

```bash
# 1. Database URL (Neon PostgreSQL)
echo "postgresql://user:password@host-pooler.region.aws.neon.tech/dbname?sslmode=require" | vercel env add DATABASE_URL production

# 2. Blob Storage Token (from Step 3)
echo "YOUR_BLOB_TOKEN_HERE" | vercel env add BLOB_READ_WRITE_TOKEN production

# 3. Anthropic API Key
echo "YOUR_ANTHROPIC_API_KEY_HERE" | vercel env add ANTHROPIC_API_KEY production

# 4. Anthropic Assistant ID
echo "YOUR_ASSISTANT_ID_HERE" | vercel env add OPENAI_ASSISTANT_ID production

# 5. Anthropic Vector Store ID
echo "YOUR_VECTOR_STORE_ID_HERE" | vercel env add OPENAI_VECTOR_STORE_ID production

# 6. Secret Key (generate with: python -c "import secrets; print(secrets.token_hex(32))")
echo "YOUR_SECRET_KEY_HERE" | vercel env add SECRET_KEY production

# 7. Vercel flag
echo "true" | vercel env add VERCEL production
```

**⚠️ IMPORTANT:** Replace `YOUR_BLOB_TOKEN_HERE` with the actual Blob token from Step 3!

---

### Step 5: Verify Environment Variables

```bash
vercel env ls
```

You should see:
- ✅ DATABASE_URL
- ✅ BLOB_READ_WRITE_TOKEN
- ✅ ANTHROPIC_API_KEY
- ✅ OPENAI_ASSISTANT_ID
- ✅ OPENAI_VECTOR_STORE_ID
- ✅ SECRET_KEY
- ✅ VERCEL

---

### Step 6: Deploy to Production

```bash
vercel --prod
```

This will:
1. Build your application
2. Upload to Vercel
3. Deploy to production URL
4. Return production URL (e.g., `https://ask-chopper.vercel.app`)

**Wait for deployment to complete** (usually 1-2 minutes).

---

### Step 7: Verify Deployment

After deployment completes:

#### A. Check Deployment Status
```bash
# View recent logs
vercel logs --prod

# Check deployment URL
vercel ls
```

#### B. Test Basic Functionality
1. **Visit production URL** (shown in terminal)
2. **Homepage loads** ✅
3. **Register new user**
   - Email: test@example.com
   - Password: testpass123
4. **Login works** ✅
5. **Session persists** (refresh page, still logged in) ✅

#### C. Test Database Persistence
1. **Create a chat message**
2. **Refresh the page**
3. **Message still there** ✅ (confirms PostgreSQL working)

#### D. Test File Upload
1. **Go to Sounds/Beat Pax page**
2. **Upload audio pack with cover image**
3. **Upload succeeds** ✅
4. **Files accessible** (click to view/play) ✅
5. **Refresh page**
6. **Files still accessible** ✅ (confirms Blob storage working)

---

## Post-Deployment Monitoring

### First 24 Hours - Critical Monitoring

#### Monitor Vercel Logs
```bash
# Stream production logs
vercel logs --prod --follow
```

Watch for:
- ❌ Database connection errors
- ❌ Blob storage upload errors
- ❌ Anthropic API errors
- ❌ Session errors
- ❌ 5xx server errors

#### Monitor Neon Database
1. Go to https://console.neon.tech/
2. Select your database
3. Check **Metrics**:
   - Connection count (should be < 15)
   - Query performance
   - Storage usage

#### Monitor Vercel Blob Usage
1. Go to Vercel Dashboard → Storage → Blob
2. Check **Usage**:
   - Storage used (< 1GB for free tier)
   - Bandwidth used (< 10GB/month)

---

## Testing with 10 Users

### Test Scenarios

#### Scenario 1: Concurrent Registration (5 users)
- All register at same time
- Expected: All succeed
- Check: No duplicate email errors

#### Scenario 2: Concurrent Chat (5 users)
- All send messages simultaneously
- Expected: All get responses within 5 seconds
- Check: No timeout errors

#### Scenario 3: Concurrent File Upload (3 users)
- All upload audio packs with covers
- Expected: All uploads succeed
- Check: Files accessible, no corruption

#### Scenario 4: Session Persistence (10 users)
- All login
- Refresh pages multiple times
- Expected: Stay logged in
- Check: No unexpected logouts

#### Scenario 5: Database Stress (10 users)
- Browse packs, downloads, profiles
- Expected: Fast page loads (< 1s)
- Check: No database connection errors

---

## Troubleshooting

### Issue: "Database connection failed"

**Symptoms:**
- 500 errors on page load
- "Could not connect to database" in logs

**Solutions:**
1. Check DATABASE_URL is set correctly:
   ```bash
   vercel env ls
   ```
2. Verify Neon database is not suspended (free tier may suspend after inactivity)
3. Check connection pool settings in app.py
4. Restart deployment:
   ```bash
   vercel --prod
   ```

---

### Issue: "File upload failed"

**Symptoms:**
- Upload button doesn't work
- "Failed to upload file to Blob storage" error

**Solutions:**
1. Check BLOB_READ_WRITE_TOKEN is set:
   ```bash
   vercel env ls | grep BLOB
   ```
2. Verify token is correct (copy from Vercel Dashboard)
3. Check Blob storage quota not exceeded
4. Test locally with token:
   ```bash
   export BLOB_READ_WRITE_TOKEN=your_token
   python3 test_blob_storage.py
   ```

---

### Issue: "Session not persisting"

**Symptoms:**
- Logged out after page refresh
- "Not authenticated" errors

**Solutions:**
1. Check SECRET_KEY is set and strong
2. Verify cookies are enabled in browser
3. Check session cookie settings in app.py
4. May need to add `SESSION_COOKIE_SECURE=True`

---

### Issue: "Anthropic API errors"

**Symptoms:**
- Chat doesn't respond
- "Anthropic API error" messages

**Solutions:**
1. Check ANTHROPIC_API_KEY is valid
2. Check API quota/billing: https://console.anthropic.com/usage
3. Verify OPENAI_ASSISTANT_ID and OPENAI_VECTOR_STORE_ID are correct
4. Test API key locally:
   ```python
   from anthropic import Anthropic
   client = Anthropic(api_key="your_key")
   response = client.chat.completions.create(
       model="claude-3-5-haiku-latest",
       messages=[{"role": "user", "content": "test"}]
   )
   print(response)
   ```

---

### Issue: "Slow performance"

**Symptoms:**
- Pages load slowly (> 3s)
- Chat responses timeout

**Solutions:**
1. Check Neon database connection pool
2. Verify indexes are created:
   ```bash
   python3 create_indexes.py
   ```
3. Monitor database query performance in Neon console
4. Check Vercel function execution time (may hit timeout)
5. Consider upgrading to Vercel Pro for 60s timeout (Hobby is 10s)

---

## Rollback Procedure

If critical issues occur:

### Quick Rollback (< 1 minute)
```bash
# List recent deployments
vercel ls

# Find previous working deployment URL
# Promote it to production
vercel promote <deployment-url>
```

### Manual Rollback via Dashboard
1. Go to Vercel Dashboard → Your Project
2. Click **Deployments** tab
3. Find last working deployment
4. Click ⋮ → **Promote to Production**

### Notify Users
If you have test users' contact info:
- Send email/message about temporary issue
- Provide estimated time to fix
- Apologize for inconvenience

---

## Success Metrics

Track these for 10-user test period:

### Must-Have (Deployment Success)
- ✅ Zero data loss incidents
- ✅ 99% uptime
- ✅ All file uploads succeed
- ✅ No session issues
- ✅ Database queries < 100ms (p95)

### Should-Have (User Experience)
- ✅ Page load < 2s (p95)
- ✅ Chat response < 3s (p95)
- ✅ File upload < 5s for 10MB
- ✅ Error rate < 1%
- ✅ User satisfaction > 4/5

### Nice-to-Have (Performance)
- ✅ Zero timeout errors
- ✅ Concurrent users handled smoothly
- ✅ No rate limiting issues
- ✅ Search/queries fast

---

## Next Steps After Successful Deployment

### Phase 1: Monitor & Stabilize (Week 1)
- [ ] Monitor logs daily
- [ ] Fix any bugs reported by test users
- [ ] Optimize slow queries
- [ ] Adjust resource limits if needed

### Phase 2: Security Hardening (Week 2)
- [ ] Add rate limiting (Flask-Limiter)
- [ ] Restrict CORS origins
- [ ] Add CSRF protection
- [ ] Set up Sentry error tracking
- [ ] Add health check endpoints

### Phase 3: Scale Up (Week 3-4)
- [ ] Expand to 50 users
- [ ] Monitor costs (Blob, Neon, Anthropic)
- [ ] Optimize file sizes
- [ ] Add caching if needed
- [ ] Consider CDN for static assets

---

## Support Contacts

### Vercel
- Dashboard: https://vercel.com/dashboard
- Docs: https://vercel.com/docs
- Support: https://vercel.com/support

### Neon
- Console: https://console.neon.tech/
- Docs: https://neon.tech/docs
- Support: https://neon.tech/docs/introduction/support

### Anthropic
- Dashboard: https://console.anthropic.com/
- API Status: https://status.anthropic.com/
- Support: https://support.anthropic.com/

---

## Emergency Contacts

Add your contacts here:
- Developer: [Your Name/Email]
- Project Owner: [Owner Name/Email]
- Test User Coordinator: [Coordinator Email]

---

## Deployment Summary

### Infrastructure
- **Hosting:** Vercel (Serverless)
- **Database:** Neon PostgreSQL (us-east-1)
- **File Storage:** Vercel Blob
- **AI:** Anthropic GPT-4 + Assistants API

### Configuration
- **Region:** us-east-1 (AWS)
- **Python:** 3.9+
- **Framework:** Flask 3.1.0
- **Connection Pool:** 5 connections, 10 max overflow

### Costs (Estimated for 10 users)
- Vercel: $0 (Hobby plan)
- Neon: $0 (Free tier, < 0.5GB)
- Vercel Blob: $0 (< 1GB storage, < 10GB bandwidth)
- Anthropic: ~$5-20/month (depends on usage)

**Total:** ~$5-20/month

---

## Final Checklist Before Going Live

- [ ] All environment variables set in Vercel
- [ ] Database tables created and indexed
- [ ] Blob storage created and tested
- [ ] Application deployed successfully
- [ ] Basic functionality tested (register, login, chat)
- [ ] File uploads tested and working
- [ ] Database persistence verified
- [ ] Logs show no errors
- [ ] Test users invited
- [ ] Monitoring set up
- [ ] Rollback plan documented
- [ ] Emergency contacts updated

---

## You're Ready! 🚀

Once all items are checked:

```bash
# Deploy to production
vercel --prod

# Share the URL with your 10 test users
# Monitor closely for first 24 hours
# Gather feedback
# Iterate and improve
```

Good luck with your production deployment!

---

**Questions or issues?** Check the troubleshooting section above or review:
- `DATABASE_MIGRATION_COMPLETE.md` - Database setup
- `VERCEL_BLOB_STORAGE_SETUP.md` - Blob storage details
- `VERCEL_SETUP_GUIDE.md` - Environment variables
- `PRODUCTION_READINESS_CHECKLIST.md` - Full checklist
