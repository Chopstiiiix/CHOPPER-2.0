# Document RAG Testing Plan

## Phase 1: Document Upload and Query Testing

### Test Environment
- URL: http://localhost:8000
- Backend: Flask with Anthropic Assistants API
- Vector Store ID: vs_692eef58ffb48191801aa6b8eece21c1
- Assistant ID: asst_kxFVifKEzOsV2cAYwSupMkyx

---

## Test Cases

### Test 1: Basic Document Upload and Query
**Objective**: Verify document can be uploaded and queried successfully

**Steps**:
1. Navigate to http://localhost:8000 and log in
2. Toggle "Document RAG" mode to ON (switch should turn blue)
3. Click the attachment button (+) and select `test_document.txt`
4. Type message: "What is Ask Chopper?"
5. Click Send

**Expected Result**:
- User message appears with attachment indicator
- Assistant response includes information from the document
- Blue "📄 Document Context" indicator appears above response
- "Sources" section shows test_document.txt as citation
- Response mentions key features: Beat Pax, token system, music assistant

---

### Test 2: Multiple Document Upload
**Objective**: Test handling of multiple documents in one query

**Steps**:
1. Ensure Document RAG mode is ON
2. Upload 2-3 different documents (PDFs, TXT files)
3. Ask: "Summarize the key points from all uploaded documents"
4. Click Send

**Expected Result**:
- All documents shown in attachment preview before sending
- Assistant synthesizes information from multiple sources
- Citations list all uploaded documents
- No errors during upload process

---

### Test 3: Document-Specific Questions
**Objective**: Verify assistant uses document context to answer specific questions

**Steps**:
1. Upload test_document.txt
2. Ask specific questions:
   - "How many tokens does it cost to download a track?"
   - "What genres are supported?"
   - "What is the recommended export format?"

**Expected Result**:
- Answers should cite specific information from document:
  - "3 tokens to download a track"
  - Lists: Hip Hop, Afrobeats, Electronic, Jazz, R&B, Pop
  - "WAV 24-bit recommended"
- Each response shows document citation

---

### Test 4: Regular Chat vs Document RAG Mode
**Objective**: Verify mode toggle works correctly

**Steps**:
1. Turn Document RAG OFF
2. Upload a file and send message
3. Turn Document RAG ON
4. Upload same file and send similar message

**Expected Result**:
- OFF mode: Uses /chat endpoint, treats files as attachments
- ON mode: Uses /chat-with-document endpoint, enables RAG
- Different response quality and context awareness
- Citations only appear in document mode

---

### Test 5: Conversation History with Documents
**Objective**: Test thread persistence across multiple queries

**Steps**:
1. Upload document and ask first question
2. Ask follow-up question WITHOUT re-uploading: "Tell me more about that"
3. Ask another follow-up question

**Expected Result**:
- Assistant maintains context from previous messages
- Can reference earlier parts of conversation
- Thread ID remains consistent across messages
- Citations still appear in follow-up responses

---

### Test 6: Unsupported File Types
**Objective**: Verify error handling for invalid files

**Steps**:
1. Try to upload unsupported file type (.exe, .zip, etc.)
2. Observe behavior

**Expected Result**:
- File should be rejected or filtered out
- Clear error message displayed
- Application doesn't crash

---

### Test 7: Large Document Handling
**Objective**: Test performance with large documents

**Steps**:
1. Upload a large document (5-10 pages PDF or long text file)
2. Ask comprehensive question requiring deep document analysis
3. Monitor response time

**Expected Result**:
- Document uploads successfully
- Assistant processes entire document
- Response includes relevant information from throughout document
- Response time within acceptable range (< 30 seconds)

---

### Test 8: Citation Formatting
**Objective**: Verify citations are displayed correctly

**Steps**:
1. Upload document with specific filename
2. Ask question that requires citing the document
3. Check citation display

**Expected Result**:
- Citation section appears below response
- Filename displayed correctly
- Blue highlight on citation box
- Document icon (📄) shown
- Clickable/readable format

---

### Test 9: Error Handling - Missing Message
**Objective**: Test validation when no message provided

**Steps**:
1. Turn Document RAG mode ON
2. Upload document but leave message field empty
3. Try to send

**Expected Result**:
- Error message: "No message provided"
- Request not sent to server
- User can correct and resend

---

### Test 10: Database Persistence
**Objective**: Verify documents are saved to database

**Steps**:
1. Upload and query document
2. Open Prisma Studio (http://localhost:5555)
3. Navigate to document_uploads table
4. Check chat_messages table

**Expected Result**:
- New record in document_uploads with:
  - Correct filename
  - Anthropic file_id
  - Vector store ID
  - Upload timestamp
- Chat messages include:
  - thread_id
  - run_id
  - has_document_context = true

---

## Performance Metrics

Track the following for each test:
- **Upload Time**: Time to upload document to Anthropic
- **Response Time**: Time from send to response
- **Accuracy**: Correctness of information from document
- **Citation Accuracy**: Correct source attribution

**Acceptable Thresholds**:
- Upload: < 5 seconds per document
- Response: < 30 seconds
- Accuracy: 95%+ information correctness
- Citations: 100% correct attribution

---

## Known Limitations

1. **Document Expiry**: Vector Store expires after 30 days of inactivity
2. **File Size**: Anthropic has limits on file size (check current limits)
3. **Supported Formats**: Limited to allowed_document_file() types
4. **Concurrent Uploads**: Multiple simultaneous uploads may impact performance

---

## Troubleshooting

### Issue: Citations not appearing
- Check: Is documentMode toggle ON?
- Check: Does response include data.citations in network tab?
- Check: Is process_assistant_response() extracting annotations?

### Issue: "Document RAG not configured" error
- Verify: OPENAI_ASSISTANT_ID in .env
- Verify: OPENAI_VECTOR_STORE_ID in .env
- Restart Flask server after .env changes

### Issue: Slow responses
- Check: Anthropic API status
- Check: Document size
- Check: Network connection
- Review: Assistant run polling interval

### Issue: Thread not persisting
- Check: session_id is consistent
- Check: thread_id stored in database
- Check: get_or_create_thread() logic

---

## Test Data Files

Create these test files in project root:

1. **test_document.txt** (Already created)
   - Music production guide
   - Tests text file support

2. **test_code.py**
   ```python
   def hello_world():
       print("Hello from Ask Chopper!")
       return "Testing code file upload"
   ```

3. **test_data.json**
   ```json
   {
     "app": "Ask Chopper",
     "features": ["Beat Pax", "Chat", "Tokens"],
     "version": "1.0.0"
   }
   ```

4. **test_readme.md**
   ```markdown
   # Ask Chopper Test Document

   This is a test markdown file to verify document upload functionality.

   ## Features
   - Document RAG
   - Citation extraction
   - Thread management
   ```

---

## Success Criteria

Phase 1 testing is successful if:
- ✅ All 10 test cases pass
- ✅ No critical bugs found
- ✅ Performance within acceptable thresholds
- ✅ Database persistence verified
- ✅ Citations display correctly
- ✅ Error handling works as expected
- ✅ User experience is smooth and intuitive

---

## Next Steps After Testing

1. Fix any bugs discovered during testing
2. Optimize performance bottlenecks
3. Add additional error messages for edge cases
4. Consider implementing:
   - Document preview before upload
   - Document management page (view/delete uploaded docs)
   - Advanced citation display (show quote from document)
   - Multi-language document support
5. Update user documentation
6. Proceed to Phase 2 (if planned)
