# Document RAG Troubleshooting Guide

## Issues Fixed (Latest Update)

### 1. ✅ File Pointer Issue
**Problem**: File stream exhausted after OpenAI upload
**Solution**: Added `file.seek(0)` to reset pointer before local save

### 2. ✅ Validation Error
**Problem**: 400 error when uploading documents without message text
**Solution**: Allow document-only uploads with default message

### 3. ✅ Error Visibility
**Problem**: Generic error messages with no details
**Solution**: Added comprehensive debug logging throughout

---

## Current Configuration Status

✅ **OPENAI_ASSISTANT_ID**: `asst_kxFVifKEzOsV2cAYwSupMkyx`
✅ **OPENAI_VECTOR_STORE_ID**: `vs_692eef58ffb48191801aa6b8eece21c1`
✅ **OPENAI_API_KEY**: Loaded correctly
✅ **Flask Server**: Running on port 8000
✅ **Debug Mode**: Enabled with auto-reload

---

## How to Test Document RAG (Step by Step)

### Step 1: Access the Application
1. Open browser: `http://localhost:8000` or `http://192.168.100.216:8000`
2. Log in with your credentials

### Step 2: Enable Document RAG Mode
1. Look for "Document RAG" toggle at the bottom of chat
2. Click the toggle switch - it should turn **blue**
3. Label should change from "Off" to "On"
4. Placeholder text changes to "Ask questions about your documents..."

### Step 3: Upload a Document
1. Click the **+** button (attachment button)
2. Select a document file:
   - ✅ Supported: PDF, TXT, MD, DOC, DOCX, PY, JS, JSON, CSV, XML, HTML, CSS
   - ❌ Not supported: Images, ZIP, EXE, etc.
3. File appears in preview area above text input

### Step 4: Send Your Question
**Option A**: With a message
- Type: "What is this document about?"
- Click Send

**Option B**: Without a message (just upload)
- Click Send with no text
- System automatically asks assistant to "Please analyze the uploaded documents."

### Step 5: Check the Response
You should see:
- ✅ Assistant's response based on document content
- ✅ Blue badge: "📄 Document Context"
- ✅ "Sources" section showing filename
- ✅ No error messages

---

## Debug Logs to Monitor

When you upload a document, watch your terminal for these logs:

```
DEBUG: Processing document RAG request - Message: '...', Files: 1
DEBUG: Processing 1 uploaded files
DEBUG: Processing file: test_document.txt
DEBUG: Uploading test_document.txt to OpenAI...
DEBUG: OpenAI file created with ID: file-xxx
DEBUG: Adding file to vector store vs_692eef58...
DEBUG: File added to vector store successfully
DEBUG: Saving document to database...
DEBUG: Document saved: test_document.txt
```

---

## Common Errors and Solutions

### Error: "No message provided"
**Cause**: You're trying to send without text or files
**Solution**: Either type a message OR upload a file

### Error: "Document RAG not configured"
**Cause**: Environment variables not loaded
**Check**:
```bash
grep OPENAI_ASSISTANT_ID .env
grep OPENAI_VECTOR_STORE_ID .env
```
**Solution**: Restart Flask server to reload .env

### Error: "Failed to create conversation thread"
**Cause**: OpenAI API error or network issue
**Check**: Terminal logs for OpenAI error details
**Solution**: Verify API key and check OpenAI status

### Error: "File rejected - not an allowed document type"
**Cause**: Uploaded file type not supported
**Solution**: Use supported formats (PDF, TXT, MD, code files)

### Error: OpenAI API errors
**Check terminal for**:
- Rate limit errors → Wait and retry
- Invalid API key → Check .env file
- Invalid assistant ID → Verify in OpenAI dashboard
- Vector store not found → Verify vector store ID

---

## Verify OpenAI Configuration

### Check Assistant Configuration
1. Go to: https://platform.openai.com/assistants
2. Find assistant: `asst_kxFVifKEzOsV2cAYwSupMkyx`
3. Verify:
   - ✅ Tools include: `file_search`
   - ✅ Vector Store attached: `vs_692eef58ffb48191801aa6b8eece21c1`

### Check Vector Store
1. Go to: https://platform.openai.com/storage
2. Find store: `vs_692eef58ffb48191801aa6b8eece21c1`
3. After successful upload, you should see your files listed

---

## Database Verification

### Check Document Upload Records
```bash
# Start Prisma Studio
npx prisma studio

# Navigate to: http://localhost:5555
# Check tables:
# - document_uploads: Should show uploaded files
# - chat_messages: Should have thread_id and has_document_context = true
```

### Query Database Directly
```bash
sqlite3 instance/ask_chopper.db

# Check uploaded documents
SELECT id, original_filename, openai_file_id, uploaded_at
FROM document_uploads
ORDER BY uploaded_at DESC
LIMIT 5;

# Check messages with document context
SELECT id, content, thread_id, has_document_context, created_at
FROM chat_messages
WHERE has_document_context = 1
ORDER BY created_at DESC
LIMIT 5;
```

---

## Test Scenarios

### Test 1: Basic Upload
```
1. Enable Document RAG mode
2. Upload test_document.txt
3. Type: "What is Ask Chopper?"
4. Expected: Response about music assistant with Beat Pax feature
5. Should show citation: test_document.txt
```

### Test 2: Document-Specific Question
```
1. Upload test_document.txt
2. Type: "How many tokens does it cost to download?"
3. Expected: "3 tokens to download a track"
4. Should cite the document
```

### Test 3: Multiple Documents
```
1. Upload 2-3 different files
2. Type: "Summarize all documents"
3. Expected: Combined summary from all files
4. Should show multiple citations
```

### Test 4: Follow-up Questions
```
1. Upload document and ask question
2. Without re-uploading, ask follow-up: "Tell me more"
3. Expected: Maintains context, uses same thread
4. Should still show citations
```

---

## Performance Expectations

- **File Upload**: 2-5 seconds per document
- **Vector Store Processing**: 1-3 seconds
- **Assistant Response**: 5-30 seconds depending on:
  - Document size
  - Question complexity
  - OpenAI API load

---

## Emergency Reset

If things are completely broken:

```bash
# 1. Stop Flask server
# Press CTRL+C in terminal running Flask

# 2. Kill any stuck processes
lsof -ti:8000 | xargs kill -9

# 3. Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# 4. Restart Flask
python3 app.py
```

---

## Contact Information

**OpenAI Configuration**:
- Assistant ID: `asst_kxFVifKEzOsV2cAYwSupMkyx`
- Vector Store ID: `vs_692eef58ffb48191801aa6b8eece21c1`
- Endpoint: `/chat-with-document`

**Repository**: https://github.com/Chopstiiiix/Ask-Chopper

**Latest Fixes**:
- Commit: `6efc63c` - Validation fix and debug logging
- Commit: `b46579e` - File pointer fix
- Date: 2025-12-02

---

## Success Checklist

Before reporting issues, verify:
- ✅ Flask server running on port 8000
- ✅ Document RAG toggle turns blue when enabled
- ✅ Environment variables loaded (check terminal output)
- ✅ Test document exists in project root
- ✅ Browser console shows no JavaScript errors
- ✅ Network tab shows request to `/chat-with-document`
- ✅ Terminal shows debug logs during upload

---

*Last Updated: 2025-12-02*
