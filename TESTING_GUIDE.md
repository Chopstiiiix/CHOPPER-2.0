# Production Testing Guide

**Your App:** https://ask-chopper-ctuk31ve2-choppers-projects-b98532fa.vercel.app
**Deployed:** 2025-12-08
**Status:** ✅ Live in Production

---

## Quick Test Checklist

Copy this URL and test each item:
**https://ask-chopper-ctuk31ve2-choppers-projects-b98532fa.vercel.app**

### Critical Tests (Must Pass)

- [ ] **Homepage loads** - No errors, pages renders
- [ ] **User Registration** - Create new account
- [ ] **User Login** - Login with account
- [ ] **Session Persists** - Refresh page, still logged in
- [ ] **Database Works** - Data saves and persists
- [ ] **File Upload** - Upload audio/image succeeds
- [ ] **Files Accessible** - Can view/download uploaded files
- [ ] **Chat Works** - Send message, get AI response

---

## Detailed Testing Steps

### Test 1: Homepage & Landing Page ✅

1. Open: https://ask-chopper-ctuk31ve2-choppers-projects-b98532fa.vercel.app
2. **Expected:** Landing page loads successfully
3. **Check:** No 500 errors, page looks normal

---

### Test 2: User Registration 🔐

1. Click **Register** or go to `/register`
2. Fill in the form:
   - First Name: Test
   - Surname: User
   - Email: test@example.com (use your real email)
   - Phone: +1234567890
   - Age: 25
   - Password: TestPassword123!
3. Click **Register**
4. **Expected:**
   - Registration succeeds
   - Redirected to main app
   - Logged in automatically

**✅ PASS if:** You're logged in and see the main app
**❌ FAIL if:** Error message or redirect fails

---

### Test 3: User Login 🔐

1. Logout (if logged in)
2. Click **Login** or go to `/login`
3. Enter credentials from Test 2
4. Click **Login**
5. **Expected:** Login succeeds, redirected to app

**✅ PASS if:** You're logged in
**❌ FAIL if:** "Invalid email or password" error

---

### Test 4: Session Persistence 🔄

1. While logged in, **refresh the page** (F5 or Cmd+R)
2. **Expected:** Still logged in, don't get logged out
3. Close tab and reopen
4. **Expected:** Still logged in (if "Remember me" works)

**✅ PASS if:** Session persists across refreshes
**❌ FAIL if:** Logged out after refresh

---

### Test 5: Database Persistence 💾

**Testing PostgreSQL:**

1. Go to **Sounds** or **Beat Pax** page
2. Note: How many packs are shown
3. **Refresh the page**
4. **Expected:** Same packs still there (data persisted)

5. Go to **Profile** page
6. **Expected:** Your user info displays correctly

**✅ PASS if:** Data persists after refresh
**❌ FAIL if:** Data disappears

---

### Test 6: File Upload - Audio Pack 🎵

**Testing Vercel Blob Storage:**

1. Go to **Sounds** page
2. Click **Upload** or similar
3. Fill in pack details:
   - Title: "Test Beat Pack"
   - Genre: "Hip Hop"
   - BPM: 120
4. **Upload cover image** (any JPG/PNG)
5. **Upload audio files** (MP3 files if you have them)
6. Click **Submit** or **Upload**

**Expected:**
- Upload progress shows
- Success message appears
- Pack appears in your list

**✅ PASS if:**
- Upload succeeds
- Cover image displays
- Audio files accessible

**❌ FAIL if:**
- "Failed to upload" error
- Files don't appear
- 500 server error

---

### Test 7: File Accessibility 📁

1. Find the pack you just uploaded
2. **Click on cover image**
   - **Expected:** Image loads from Blob URL (check URL starts with `https://`)
3. **Click on audio file** (if player exists)
   - **Expected:** Audio plays or downloads
4. **Copy audio file URL** from browser
   - **Expected:** URL starts with `https://` (Blob URL)

**✅ PASS if:** All files load from `https://` URLs
**❌ FAIL if:** 404 errors or files don't load

---

### Test 8: Chat Functionality 💬

1. Go to main chat page (`/app`)
2. Send a message: "Hello, are you working?"
3. **Expected:**
   - Message sends
   - AI responds within 3-5 seconds
   - Response appears in chat

**✅ PASS if:** Chat works, AI responds
**❌ FAIL if:**
- Timeout error
- "OpenAI API error"
- No response after 10 seconds

---

### Test 9: Chat with File Attachment 📎

1. In chat, click **Attach File** (if available)
2. Upload an image or document
3. Send message with attachment
4. **Expected:**
   - File uploads successfully
   - Can view/download attachment
   - AI acknowledges the file

**✅ PASS if:** Attachment uploads and is accessible
**❌ FAIL if:** Upload fails

---

### Test 10: Document RAG (if implemented) 📄

1. Find document upload feature
2. Upload a PDF or text file
3. Ask question about the document
4. **Expected:**
   - Document uploads
   - AI can reference the document in responses

**✅ PASS if:** RAG works with uploaded documents
**❌ FAIL if:** Upload fails or AI can't access doc

---

## Load Testing (Optional)

### Test with Multiple Users

If you have multiple devices or friends:

1. **5 users** - Register simultaneously
2. **5 users** - Send chat messages at same time
3. **3 users** - Upload files simultaneously

**Expected:**
- All succeed without errors
- Response times < 5 seconds
- No database conflicts

---

## Monitoring & Logs

### Check Logs for Errors

From your terminal:
```bash
vercel logs https://ask-chopper-ctuk31ve2-choppers-projects-b98532fa.vercel.app
```

**Look for:**
- ❌ `Error:` messages
- ❌ `500` status codes
- ❌ Database connection errors
- ❌ Blob storage errors

### Check Vercel Dashboard

1. Go to: https://vercel.com/choppers-projects-b98532fa/ask-chopper
2. Click **Deployments** → Latest deployment
3. Click **Logs** tab
4. **Look for errors**

---

## What to Do If Tests Fail

### If Registration/Login Fails
**Check:**
- DATABASE_URL is set correctly
- Database connection pool settings
- Neon database not suspended

**Solution:**
```bash
vercel env ls  # Verify DATABASE_URL exists
```

---

### If File Upload Fails
**Check:**
- BLOB_READ_WRITE_TOKEN is set
- Blob storage exists
- File size < 16MB

**Solution:**
```bash
vercel env ls | grep BLOB  # Verify token exists
```

Visit Vercel Dashboard → Storage → Verify Blob store exists

---

### If Chat Doesn't Work
**Check:**
- OPENAI_API_KEY is valid
- API has credit/quota
- Not hitting rate limits

**Solution:**
- Check OpenAI dashboard: https://platform.openai.com/usage
- Verify API key: https://platform.openai.com/api-keys

---

### If Sessions Don't Persist
**Check:**
- SECRET_KEY is set
- Cookies enabled in browser
- HTTPS connection (Vercel should handle this)

**Solution:**
```bash
vercel env ls | grep SECRET  # Verify SECRET_KEY exists
```

---

## Success Criteria

### Minimum for 10-User Test
- ✅ Registration works
- ✅ Login works
- ✅ Sessions persist
- ✅ Database persists data
- ✅ File uploads work
- ✅ Files are accessible
- ✅ Chat responds (basic)

### Ideal Success
- All of the above, plus:
- ✅ Fast response times (< 2s page load)
- ✅ No errors in logs
- ✅ 5+ concurrent users work smoothly
- ✅ Document RAG works

---

## Rollback Instructions

If critical issues found:

```bash
# List deployments
vercel ls

# Promote previous deployment
vercel promote <previous-deployment-url>
```

Or via dashboard:
1. Go to Vercel → Deployments
2. Find previous working deployment
3. Click ⋮ → Promote to Production

---

## Share with Test Users

Send them:

**Test URL:**
https://ask-chopper-ctuk31ve2-choppers-projects-b98532fa.vercel.app

**Instructions:**
1. Register with your email
2. Explore the app
3. Try uploading audio/files
4. Send chat messages
5. Report any issues to: [your email]

**Feedback Form:**
- What worked well?
- What didn't work?
- Any errors you encountered?
- Performance issues?

---

## Next Steps After Testing

### If All Tests Pass ✅
1. Invite 10 test users
2. Monitor for 24-48 hours
3. Gather feedback
4. Plan Phase 1 features

### If Tests Fail ❌
1. Check logs for specific errors
2. Review troubleshooting section
3. Fix issues
4. Redeploy: `vercel --prod`
5. Re-test

---

## Support

- **Deployment URL:** https://ask-chopper-ctuk31ve2-choppers-projects-b98532fa.vercel.app
- **Vercel Dashboard:** https://vercel.com/choppers-projects-b98532fa/ask-chopper
- **Logs:** `vercel logs <url>`
- **Docs:** See PRODUCTION_DEPLOYMENT_GUIDE.md

---

**Good luck with testing! 🚀**
