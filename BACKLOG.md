# Ask Chopper - Product Backlog

## Overview
This backlog tracks planned features and improvements for the Ask Chopper music marketplace platform. Items are organized by priority and implementation phases.

---

## Current Sprint: Production Readiness & Infrastructure

### Goal
Migrate application infrastructure to support production deployment on Vercel with 10 concurrent users. Fix critical blockers preventing data persistence and file storage.

---

## Phase 0: Production Readiness & Infrastructure (CRITICAL PRIORITY)
**Target Timeline:** Week 1 (3-4 days)
**Status:** 🔴 Not Started
**Blocker:** Must complete before any production deployment

### Epic: Production Infrastructure Migration

#### Critical Blockers (Must Fix)

**US-PROD-001: Database Migration to Vercel Postgres**
- **As a** platform operator
- **I want** persistent database storage on Vercel
- **So that** user data and application state survives deployments

**Problem:**
- SQLite file-based database incompatible with Vercel serverless
- Data loss between deployments
- No concurrent user support
- Database at: `/Users/maclcolmolagundoye/Ask-Chopper/instance/ask_chopper.db` (60KB, ephemeral)

**Acceptance Criteria:**
- [ ] Vercel Postgres database provisioned
- [ ] All tables migrated from SQLite schema
- [ ] Connection pooling configured for serverless
- [ ] Environment variables set in Vercel
- [ ] Data persistence verified across deployments
- [ ] No data loss on function cold starts

**Technical Tasks:**
- [ ] Create Vercel Postgres database
- [ ] Install psycopg2-binary for PostgreSQL support
- [ ] Update DATABASE_URL in Vercel environment variables
- [ ] Convert SQLite schema to PostgreSQL (handle dialect differences)
- [ ] Configure SQLAlchemy connection pooling (app.py lines 22-31)
- [ ] Add pool_pre_ping=True for connection health checks
- [ ] Migrate existing data (1 user, 3 messages, 1 pack)
- [ ] Update db.create_all() logic for Vercel (already disabled at line 1014)
- [ ] Test concurrent connections (10 users)
- [ ] Document rollback procedure

**Files to Modify:**
- `app.py` (lines 22-31): Database configuration
- `requirements.txt`: Add psycopg2-binary
- `models.py`: Test PostgreSQL compatibility
- `.env`: Update DATABASE_URL format

**Estimated Effort:** 4-6 hours

---

**US-PROD-002: File Storage Migration to Vercel Blob**
- **As a** user
- **I want** uploaded files to persist after deployment
- **So that** my audio files, images, and documents are always accessible

**Problem:**
- Local filesystem `/uploads` directory is ephemeral on Vercel
- All uploads lost after serverless function execution
- Affects: audio packs, covers, documents, chat attachments

**Acceptance Criteria:**
- [ ] Vercel Blob storage account created
- [ ] All file uploads use Vercel Blob API
- [ ] File serving uses Blob URLs
- [ ] Existing uploads migrated to cloud storage
- [ ] File uploads tested in production
- [ ] Thumbnail generation works with Blob

**Technical Tasks:**
- [ ] Install @vercel/blob Python SDK
- [ ] Create Vercel Blob storage (free tier: 1GB)
- [ ] Update audio file upload (app.py lines 660-677)
- [ ] Update cover image upload (app.py lines 638-646)
- [ ] Update document upload for RAG (app.py lines 171-206)
- [ ] Update chat attachment upload (app.py lines 88-136)
- [ ] Update file serving endpoint (app.py lines 999-1002)
- [ ] Update thumbnail creation for cloud storage (app.py lines 77-86)
- [ ] Migrate existing files from /uploads to Blob
- [ ] Update database file_path references to Blob URLs
- [ ] Test multipart upload for large files
- [ ] Add error handling for upload failures

**Files to Modify:**
- `app.py`: All file upload/download functions
- `requirements.txt`: Add vercel-blob SDK
- `models.py`: Update file_path field documentation

**Estimated Effort:** 4-6 hours

---

**US-PROD-003: Security Hardening**
- **As a** platform operator
- **I want** secure production configuration
- **So that** user data and sessions are protected

**Problem:**
- Default secret key in use (app.py line 20)
- Wide-open CORS policy (app.py line 37)
- Hardcoded verification code (app.py line 50)
- No CSRF protection
- No rate limiting

**Acceptance Criteria:**
- [ ] Strong random secret key generated and set
- [ ] CORS restricted to production domain
- [ ] Verification code moved to environment variable
- [ ] CSRF protection enabled
- [ ] Rate limiting implemented
- [ ] Session cookies secured for HTTPS

**Technical Tasks:**
- [ ] Generate strong SECRET_KEY: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Set SECRET_KEY in Vercel environment variables
- [ ] Remove default fallback in app.py line 20
- [ ] Update CORS configuration (app.py line 37) to restrict origins
- [ ] Move VERIFICATION_CODE to environment variable (app.py line 50)
- [ ] Install Flask-WTF for CSRF protection
- [ ] Install Flask-Limiter for rate limiting
- [ ] Configure secure session cookies (httponly, secure, samesite)
- [ ] Add rate limits to endpoints:
  - [ ] /chat: 10 requests/minute per user
  - [ ] /chat-with-document: 5 requests/minute per user
  - [ ] /api/packs/upload: 5 uploads/hour per user
  - [ ] /register: 3 attempts/hour per IP
  - [ ] /login: 5 attempts/hour per IP
  - [ ] /api/tokens/purchase: 10 requests/hour per user

**Files to Modify:**
- `app.py`: Security configuration
- `requirements.txt`: Add Flask-WTF, Flask-Limiter

**Estimated Effort:** 2-3 hours

---

#### High Priority Production Features

**US-PROD-004: Error Monitoring & Logging**
- **As a** developer
- **I want** to track errors and application behavior in production
- **So that** I can quickly diagnose and fix issues

**Problem:**
- Console-only logging with print statements
- No error tracking service
- Logs to /tmp which is ephemeral (app.py lines 292-296)
- No structured logging

**Acceptance Criteria:**
- [ ] Sentry integration for error tracking
- [ ] Structured logging with context
- [ ] Error alerts configured
- [ ] Performance monitoring enabled
- [ ] User feedback linked to errors

**Technical Tasks:**
- [ ] Create Sentry account (free tier)
- [ ] Install sentry-sdk
- [ ] Configure Sentry DSN in environment
- [ ] Replace print statements with logging
- [ ] Add user context to Sentry events
- [ ] Configure error sampling rates
- [ ] Set up alert rules for critical errors
- [ ] Remove /tmp file logging (app.py lines 292-296)
- [ ] Add structured logging with JSON format
- [ ] Log Anthropic API performance metrics
- [ ] Create logging utility module

**Files to Modify:**
- `app.py`: Replace all print statements
- `requirements.txt`: Add sentry-sdk
- New file: `logging_config.py`

**Estimated Effort:** 2-3 hours

---

**US-PROD-005: Health Checks & Monitoring**
- **As a** platform operator
- **I want** application health monitoring
- **So that** I can detect and respond to issues quickly

**Acceptance Criteria:**
- [ ] /health endpoint returns service status
- [ ] Database connectivity check
- [ ] Anthropic API connectivity check
- [ ] Uptime monitoring configured
- [ ] Response time tracking

**Technical Tasks:**
- [ ] Create /health endpoint
- [ ] Check database connection health
- [ ] Check Anthropic API availability
- [ ] Return JSON status response
- [ ] Set up Vercel Analytics (built-in)
- [ ] Configure external uptime monitor (UptimeRobot)
- [ ] Add response time logging
- [ ] Create /status endpoint for detailed metrics

**Files to Modify:**
- `app.py`: Add health check routes

**Estimated Effort:** 1-2 hours

---

**US-PROD-006: Database Performance Optimization**
- **As a** platform operator
- **I want** optimized database queries
- **So that** the app performs well with multiple concurrent users

**Problem:**
- No database indexes beyond primary keys
- N+1 queries in some endpoints
- No query optimization
- No caching layer

**Acceptance Criteria:**
- [ ] Database indexes created for common queries
- [ ] N+1 queries eliminated
- [ ] Query performance tested with 10 concurrent users
- [ ] Database connection pooling verified

**Technical Tasks:**
- [ ] Add index on users.email (verify exists)
- [ ] Add index on chat_messages.session_id
- [ ] Add index on chat_messages.thread_id
- [ ] Add index on user_tokens.user_id
- [ ] Add index on audio_packs.user_id
- [ ] Add index on user_downloads.user_id
- [ ] Add index on user_activity.user_id
- [ ] Fix N+1 query in user_profile endpoint (app.py line 703)
- [ ] Fix N+1 query in downloads_list endpoint (app.py line 732)
- [ ] Use joinedload for eager loading relationships
- [ ] Configure SQLAlchemy query logging in dev
- [ ] Test query performance

**Files to Modify:**
- New file: `migrations/add_indexes.sql` or Alembic migration
- `app.py`: Optimize query endpoints

**Estimated Effort:** 2-3 hours

---

#### Medium Priority Production Features

**US-PROD-007: Session Management for Serverless**
- **As a** user
- **I want** my session to persist across serverless functions
- **So that** I stay logged in consistently

**Problem:**
- Cookie-based sessions may not persist well on serverless
- No server-side session store

**Acceptance Criteria:**
- [ ] Sessions work reliably on Vercel
- [ ] No unexpected logouts
- [ ] Session tested across multiple deployments

**Technical Tasks:**
- [ ] Test cookie-based sessions on Vercel
- [ ] If issues: Install Flask-Session with Redis backend
- [ ] Configure secure cookie settings
- [ ] Set appropriate session timeout
- [ ] Test session persistence

**Files to Modify:**
- `app.py`: Session configuration

**Estimated Effort:** 2-3 hours

---

**US-PROD-008: Anthropic API Performance Optimization**
- **As a** user
- **I want** faster AI response times
- **So that** I have a smooth chat experience

**Problem:**
- Synchronous Anthropic API calls block request thread (1-3s)
- Document RAG waits up to 30 seconds
- May timeout on Vercel (10s Hobby, 60s Pro)

**Acceptance Criteria:**
- [ ] Chat responses under 3 seconds (p95)
- [ ] Document RAG under 30 seconds
- [ ] No timeouts under normal load
- [ ] Loading states implemented

**Technical Tasks:**
- [ ] Consider async/await for Anthropic calls
- [ ] Add streaming responses for chat
- [ ] Implement timeout handling
- [ ] Add loading indicators in frontend
- [ ] Consider webhook callbacks for long operations
- [ ] Test with 5 concurrent chat requests
- [ ] Monitor Anthropic API latency

**Files to Modify:**
- `app.py`: Chat endpoints (lines 754-997)
- Frontend: Add loading states

**Estimated Effort:** 3-4 hours

---

**US-PROD-009: Environment Configuration Management**
- **As a** developer
- **I want** clean environment variable management
- **So that** deployments are consistent and secure

**Acceptance Criteria:**
- [ ] All secrets in environment variables
- [ ] No secrets in code or .env file
- [ ] Environment variables documented
- [ ] Vercel environment variables configured

**Technical Tasks:**
- [ ] Audit all environment variables
- [ ] Document required variables
- [ ] Set all variables in Vercel dashboard
- [ ] Add .env.example template
- [ ] Remove .env from git (already in .gitignore)
- [ ] Verify ANTHROPIC_API_KEY not exposed
- [ ] Add environment validation at startup

**Files to Modify:**
- New file: `.env.example`
- New file: `DEPLOYMENT.md`
- `app.py`: Add env validation

**Estimated Effort:** 1-2 hours

---

**US-PROD-010: Deployment Documentation**
- **As a** developer
- **I want** clear deployment procedures
- **So that** I can deploy safely and consistently

**Acceptance Criteria:**
- [ ] Deployment guide written
- [ ] Rollback procedure documented
- [ ] Environment variables listed
- [ ] Migration steps documented

**Technical Tasks:**
- [ ] Write deployment checklist
- [ ] Document Vercel setup steps
- [ ] Document database migration process
- [ ] Document file storage migration
- [ ] Create troubleshooting guide
- [ ] Document rollback steps

**Files to Modify:**
- New file: `DEPLOYMENT.md`
- Update: `README.md`

**Estimated Effort:** 2 hours

---

### Testing Plan for 10-User Production Test

**Load Testing:**
- [ ] Test 10 concurrent users browsing
- [ ] Test 5 concurrent chat requests
- [ ] Test 3 concurrent file uploads
- [ ] Test 2 concurrent document RAG requests
- [ ] Monitor response times
- [ ] Monitor error rates
- [ ] Monitor database connections

**Functional Testing:**
- [ ] User registration and login
- [ ] Chat functionality
- [ ] File uploads (all types)
- [ ] Document RAG functionality
- [ ] Audio pack marketplace
- [ ] Token system
- [ ] Downloads page

**Performance Benchmarks:**
- Page load: < 1 second
- Chat response: < 3 seconds (p95)
- File upload: < 5 seconds for 10MB
- API endpoints: < 500ms

---

### Success Metrics for Production Test

**Must Have:**
- Zero data loss incidents
- 99% uptime during test period
- All file uploads succeed
- All critical bugs fixed within 24 hours

**Should Have:**
- < 2s average response time
- < 1% error rate
- User satisfaction > 4/5
- Zero security incidents

---

### Rollback Plan

**If Critical Issues Occur:**
1. Immediately rollback via Vercel dashboard
2. Notify test users via email
3. Investigate root cause
4. Fix and redeploy
5. Monitor for 24 hours

**Rollback Triggers:**
- Data loss detected
- Error rate > 10%
- Multiple user reports of same issue
- Security vulnerability discovered

---

## Phase 1: Memory MCP Integration (HIGH PRIORITY)
**Target Timeline:** Week 1-2
**Status:** 🔴 Not Started

### Epic: Persistent Memory & Personalization

#### User Stories

**US-001: User Preference Tracking**
- **As a** user
- **I want** the AI to remember my music preferences across sessions
- **So that** I get personalized recommendations without repeating myself

**Acceptance Criteria:**
- [ ] AI remembers favorite genres after first conversation
- [ ] User's preferred BPM range is stored and recalled
- [ ] Past downloads influence future recommendations
- [ ] Preferences persist across browser sessions

**Technical Tasks:**
- [ ] Install @modelcontextprotocol/server-memory package
- [ ] Configure MCP server in application
- [ ] Create memory store directory structure
- [ ] Integrate with existing chat_messages table
- [ ] Link memory with user_id from users table
- [ ] Implement preference extraction from conversations
- [ ] Create memory retrieval functions
- [ ] Add memory context to Anthropic chat prompts

**US-002: Conversation History Context**
- **As a** user
- **I want** the AI to remember our previous conversations
- **So that** I can continue discussions from where we left off

**Acceptance Criteria:**
- [ ] AI recalls previous session topics
- [ ] Can reference past conversations ("remember when...")
- [ ] Context maintained across page refreshes
- [ ] History linked to user profile

**Technical Tasks:**
- [ ] Store conversation summaries in memory MCP
- [ ] Create session linking mechanism
- [ ] Implement conversation recall queries
- [ ] Add "conversation history" context window
- [ ] Test with multi-session scenarios

**US-003: Music Taste Profile Building**
- **As a** power user
- **I want** the AI to build a profile of my music taste
- **So that** recommendations become more accurate over time

**Acceptance Criteria:**
- [ ] Profile includes genre preferences
- [ ] Tracks BPM ranges user engages with
- [ ] Notes preferred musical keys
- [ ] Records favorite producers/creators
- [ ] Profile updates automatically from behavior

**Technical Tasks:**
- [ ] Design music taste profile schema
- [ ] Create profile builder from user_activity data
- [ ] Implement profile update triggers
- [ ] Build profile-based recommendation engine
- [ ] Add profile export/import functionality
- [ ] Create admin view for profile inspection

**Configuration:**
```javascript
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "env": {
        "MEMORY_STORE_PATH": "./data/agent-memory"
      }
    }
  }
}
```

**Dependencies:**
- Existing user authentication system
- chat_messages table
- user_activity table
- Anthropic integration

**Success Metrics:**
- 50% reduction in repeated questions
- 30% increase in recommendation acceptance
- User satisfaction score improvement
- Session duration increase

---

## Phase 2: File System MCP Integration (MEDIUM PRIORITY)
**Target Timeline:** Week 3-4
**Status:** 🔴 Not Started

### Epic: Intelligent Audio Analysis

#### User Stories

**US-004: Automatic Pack Metadata**
- **As a** pack creator
- **I want** my audio files to be automatically analyzed
- **So that** pack descriptions are accurate and detailed

**Acceptance Criteria:**
- [ ] Auto-detect BPM from audio files
- [ ] Extract musical key information
- [ ] Calculate pack duration totals
- [ ] Identify audio format and quality
- [ ] Generate description suggestions

**Technical Tasks:**
- [ ] Install @modelcontextprotocol/server-filesystem package
- [ ] Add mutagen library for audio metadata parsing
- [ ] Configure filesystem MCP with uploads directory
- [ ] Create metadata extraction pipeline
- [ ] Update audio_files table schema for metadata
- [ ] Build batch processing for existing files
- [ ] Implement real-time analysis on upload
- [ ] Add metadata validation checks

**US-005: Smart Audio Search**
- **As a** user
- **I want** to search by musical characteristics
- **So that** I can find exactly what I need for my project

**Acceptance Criteria:**
- [ ] Search by BPM range (e.g., "120-140 BPM beats")
- [ ] Search by musical key (e.g., "C Minor trap beats")
- [ ] Filter by duration
- [ ] Find similar-sounding packs
- [ ] Combined characteristic search

**Technical Tasks:**
- [ ] Extend search API with metadata filters
- [ ] Create BPM range query endpoints
- [ ] Add musical key filtering
- [ ] Implement similarity matching algorithm
- [ ] Update frontend search interface
- [ ] Add advanced search filters UI
- [ ] Index metadata for fast queries

**US-006: Quality Assurance Automation**
- **As a** platform administrator
- **I want** uploaded audio to be validated automatically
- **So that** we maintain high quality standards

**Acceptance Criteria:**
- [ ] Check for corrupted audio files
- [ ] Validate metadata completeness
- [ ] Detect audio quality issues
- [ ] Flag incomplete pack information
- [ ] Alert creators about issues

**Technical Tasks:**
- [ ] Create audio validation pipeline
- [ ] Implement file integrity checks
- [ ] Add metadata completeness validator
- [ ] Build quality scoring system
- [ ] Create admin notification system
- [ ] Add creator feedback mechanism
- [ ] Implement automatic rejection for critical issues

**Configuration:**
```javascript
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "./uploads/audio",
        "./uploads/covers"
      ],
      "env": {
        "ALLOWED_PATHS": "./uploads"
      }
    }
  }
}
```

**Dependencies:**
- Python mutagen library (audio metadata)
- music21 library (music theory analysis)
- uploads directory structure
- audio_files table
- audio_packs table

**Required Libraries:**
```bash
pip install mutagen music21 pydub
```

**Success Metrics:**
- 90% metadata completion rate
- 40% improvement in search accuracy
- 25% reduction in support tickets
- Faster pack discovery time

---

## Phase 3: Brave Search MCP Integration (MEDIUM PRIORITY)
**Target Timeline:** Week 5-6
**Status:** 🔴 Not Started

### Epic: Real-Time Music Knowledge

#### User Stories

**US-007: Current Music Trends**
- **As a** user
- **I want** the AI to know about current music trends
- **So that** I can discover what's popular right now

**Acceptance Criteria:**
- [ ] AI can answer "what's trending in [genre]"
- [ ] Provides current production techniques
- [ ] Knows popular artists and producers
- [ ] Understands latest music technology
- [ ] References current music news

**Technical Tasks:**
- [ ] Get Brave Search API key (free tier)
- [ ] Install @modelcontextprotocol/server-brave-search
- [ ] Configure API key in environment
- [ ] Implement search query builder
- [ ] Add response parsing and formatting
- [ ] Create caching layer for frequent queries
- [ ] Implement rate limiting (2000/month limit)
- [ ] Build fallback responses for offline/limit reached

**US-008: Educational Music Assistant**
- **As a** beginner producer
- **I want** to ask questions about music production
- **So that** I can learn while browsing beats

**Acceptance Criteria:**
- [ ] Explains music theory concepts
- [ ] Finds tutorials for techniques
- [ ] Answers "what is" questions about production
- [ ] Provides links to learning resources
- [ ] Explains technical audio terms

**Technical Tasks:**
- [ ] Create educational query classifier
- [ ] Build tutorial search functionality
- [ ] Implement resource recommendation system
- [ ] Add glossary database for terms
- [ ] Create quick reference cards
- [ ] Link external learning platforms

**US-009: Artist & Producer Information**
- **As a** music enthusiast
- **I want** to learn about artists and producers
- **So that** I understand the context of different styles

**Acceptance Criteria:**
- [ ] Provides artist biographies
- [ ] Lists notable works and achievements
- [ ] Explains production styles
- [ ] Links similar artists
- [ ] Recommends relevant packs

**Technical Tasks:**
- [ ] Create artist information retrieval system
- [ ] Build artist-to-pack matching algorithm
- [ ] Implement style analysis
- [ ] Add "similar artists" feature
- [ ] Create artist profile pages
- [ ] Link artist info to pack recommendations

**Configuration:**
```javascript
{
  "mcpServers": {
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

**Environment Variables:**
```bash
BRAVE_API_KEY=your_brave_search_api_key
BRAVE_SEARCH_CACHE_TTL=86400  # 24 hours
BRAVE_SEARCH_RATE_LIMIT=2000  # monthly limit
```

**Dependencies:**
- Brave Search API account
- Redis/cache system (optional, for performance)
- Rate limiting middleware

**Cost Considerations:**
- Free tier: 2,000 requests/month
- Paid tier: $5/month for 15,000 requests
- Implement caching to stay within limits

**Success Metrics:**
- 60% of music questions answered without escalation
- 35% increase in user engagement time
- Positive feedback on educational content
- Reduced "I don't know" responses

---

## Backlog Items (Future Phases)

### Enhancement: Audio Similarity Matching
**Priority:** Medium
**Effort:** Large (3-4 weeks)

Create ML-based audio similarity system to recommend packs based on sound characteristics rather than just metadata.

**Tasks:**
- [ ] Research audio fingerprinting libraries
- [ ] Train similarity model on pack data
- [ ] Implement "sounds like" feature
- [ ] Add "find similar" button to packs
- [ ] Create audio feature extraction pipeline

---

### Enhancement: Social Features
**Priority:** Low
**Effort:** Medium (2-3 weeks)

Add social networking features to connect producers and users.

**Tasks:**
- [ ] User following system
- [ ] Producer profiles with portfolios
- [ ] Comment system on packs
- [ ] Rating and review system
- [ ] Share packs to social media

---

### Enhancement: Token System Gamification
**Priority:** Medium
**Effort:** Small (1 week)

Enhance token system with gamification elements.

**Tasks:**
- [ ] Daily login rewards
- [ ] Achievement badges
- [ ] Referral bonuses
- [ ] Loyalty tier system
- [ ] Token earning challenges

---

### Enhancement: Advanced Analytics Dashboard
**Priority:** Low
**Effort:** Medium (2 weeks)

Provide creators with detailed analytics on their packs.

**Tasks:**
- [ ] Download tracking by region
- [ ] Listening time analytics
- [ ] Revenue tracking
- [ ] Audience demographics
- [ ] Trend analysis charts

---

### Technical Debt: Database Migrations
**Priority:** High
**Effort:** Small (3-5 days)

Implement proper database migration system for schema changes.

**Tasks:**
- [ ] Set up Prisma Migrate or Alembic
- [ ] Create initial migration from current schema
- [ ] Document migration procedures
- [ ] Add migration tests
- [ ] Create rollback procedures

---

### Technical Debt: API Rate Limiting
**Priority:** Medium
**Effort:** Small (2-3 days)

Add rate limiting to API endpoints to prevent abuse.

**Tasks:**
- [ ] Install Flask-Limiter
- [ ] Configure rate limits per endpoint
- [ ] Add rate limit headers
- [ ] Create rate limit exceeded responses
- [ ] Monitor rate limit hits

---

### Bug: Update datetime.utcnow() Deprecation
**Priority:** Low
**Effort:** Small (1 day)

Replace deprecated datetime.utcnow() with timezone-aware datetime.now(datetime.UTC).

**Affected Files:**
- models.py (multiple locations)
- app.py (datetime usage)

**Tasks:**
- [ ] Update all datetime.utcnow() calls
- [ ] Add timezone handling
- [ ] Test datetime conversions
- [ ] Update documentation

---

## Implementation Architecture

### MCP Integration Layer Architecture

```
┌─────────────────────────────────────────────────┐
│              Ask Chopper Frontend               │
│         (React/HTML + JavaScript)               │
└─────────────────┬───────────────────────────────┘
                  │ HTTP/WebSocket
                  ▼
┌─────────────────────────────────────────────────┐
│          Flask Backend (app.py)                 │
│  ┌───────────────────────────────────────────┐ │
│  │    Chat Endpoint (/chat)                  │ │
│  │    - Receives user messages               │ │
│  │    - Enriches with MCP context            │ │
│  └───────────────┬───────────────────────────┘ │
│                  │                              │
│  ┌───────────────▼───────────────────────────┐ │
│  │         MCP Integration Manager           │ │
│  │  ┌──────────────────────────────────────┐│ │
│  │  │  MCP Context Builder                 ││ │
│  │  │  - Aggregates data from all MCPs     ││ │
│  │  │  - Prioritizes context relevance     ││ │
│  │  └──────────────────────────────────────┘│ │
│  │                                            │ │
│  │  ┌──────────────────────────────────────┐│ │
│  │  │  Memory MCP Client                   ││ │
│  │  │  - User preferences                  ││ │
│  │  │  - Conversation history              ││ │
│  │  │  Storage: ./data/agent-memory/       ││ │
│  │  └──────────────────────────────────────┘│ │
│  │                                            │ │
│  │  ┌──────────────────────────────────────┐│ │
│  │  │  File System MCP Client              ││ │
│  │  │  - Audio metadata                    ││ │
│  │  │  - Pack analysis                     ││ │
│  │  │  Access: ./uploads/                  ││ │
│  │  └──────────────────────────────────────┘│ │
│  │                                            │ │
│  │  ┌──────────────────────────────────────┐│ │
│  │  │  Brave Search MCP Client             ││ │
│  │  │  - Music knowledge                   ││ │
│  │  │  - External API calls                ││ │
│  │  │  Cache: Redis/Memory                 ││ │
│  │  └──────────────────────────────────────┘│ │
│  └─────────────────────────────────────────┘ │
│                  │                              │
│  ┌───────────────▼───────────────────────────┐ │
│  │    Anthropic Chat Completions API            │ │
│  │    - Receives enriched context            │ │
│  │    - Generates intelligent responses      │ │
│  └───────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│      SQLite Database (ask_chopper.db)           │
│  - users, audio_packs, chat_messages            │
│  - user_activity, feedback, etc.                │
└─────────────────────────────────────────────────┘

        +
┌─────────────────────────────────────────────────┐
│      External Services                          │
│  - Brave Search API                             │
│  - Audio Analysis Libraries (mutagen, music21)  │
└─────────────────────────────────────────────────┘
```

---

## Success Metrics & KPIs

### Phase 1 Success Criteria (Memory MCP)
- **User Satisfaction:** 4.5+ rating on recommendation quality
- **Engagement:** 40% increase in session duration
- **Efficiency:** 50% reduction in repeated questions
- **Retention:** 25% improvement in 7-day retention rate

### Phase 2 Success Criteria (File System MCP)
- **Search Accuracy:** 90% metadata completeness
- **Discovery:** 30% increase in pack discovery rate
- **Quality:** 25% reduction in support tickets
- **Upload Quality:** 95% of packs meet quality standards

### Phase 3 Success Criteria (Brave Search MCP)
- **Knowledge:** 80% of music questions answered correctly
- **Education:** 40% of users engage with educational content
- **Engagement:** 35% increase in conversation depth
- **API Usage:** Stay within free tier limits (< 2000/month)

---

## Technical Requirements

### Phase 1 - Memory MCP
**Backend:**
- Python 3.9+
- Flask 2.0+
- @modelcontextprotocol/server-memory (Node.js)

**Storage:**
- SQLite for MCP memory store
- Existing ask_chopper.db integration

**New Dependencies:**
```bash
# Node.js for MCP server
npm install -g @modelcontextprotocol/server-memory

# Python MCP client
pip install mcp-client
```

### Phase 2 - File System MCP
**Backend:**
- @modelcontextprotocol/server-filesystem (Node.js)
- mutagen (Python audio metadata)
- music21 (Python music theory)
- pydub (Python audio processing)

**New Dependencies:**
```bash
# Node.js MCP server
npm install -g @modelcontextprotocol/server-filesystem

# Python audio libraries
pip install mutagen music21 pydub
```

**Infrastructure:**
- Cron job for batch metadata processing
- Background task queue for uploads

### Phase 3 - Brave Search MCP
**Backend:**
- @modelcontextprotocol/server-brave-search (Node.js)
- Redis for caching (optional)
- Rate limiting middleware

**New Dependencies:**
```bash
# Node.js MCP server
npm install -g @modelcontextprotocol/server-brave-search

# Python rate limiting
pip install flask-limiter

# Redis (optional)
pip install redis
```

**External Services:**
- Brave Search API account
- API key management

---

## Risk Assessment

### High Risk Items
1. **API Rate Limits (Brave Search)**
   - Mitigation: Implement aggressive caching
   - Fallback: Static knowledge base for common queries
   - Monitoring: Track API usage dashboard

2. **Audio Processing Performance**
   - Mitigation: Background processing queue
   - Fallback: Async processing with status updates
   - Monitoring: Processing time metrics

3. **Memory Storage Growth**
   - Mitigation: Implement memory retention policy
   - Fallback: Compression and archival system
   - Monitoring: Storage usage alerts

### Medium Risk Items
1. **MCP Server Reliability**
   - Mitigation: Health checks and auto-restart
   - Fallback: Graceful degradation
   - Monitoring: Uptime tracking

2. **Context Window Limits**
   - Mitigation: Intelligent context summarization
   - Fallback: Priority-based context selection
   - Monitoring: Token usage tracking

---

## Cost Estimation

### Phase 1 - Memory MCP
**Development:** 40-60 hours
**Cost:** $0 (all open source)
**Ongoing:** Storage costs (minimal)

### Phase 2 - File System MCP
**Development:** 60-80 hours
**Cost:** $0 (all open source)
**Ongoing:** Compute for audio processing

### Phase 3 - Brave Search MCP
**Development:** 50-70 hours
**Cost:** $0-5/month (Brave Search API)
**Ongoing:** API usage costs scale with traffic

**Total Estimated Development:** 150-210 hours
**Total Ongoing Costs:** $0-10/month

---

## Definition of Done

### Feature Complete When:
- [ ] All acceptance criteria met
- [ ] Unit tests written and passing (>80% coverage)
- [ ] Integration tests passing
- [ ] Documentation updated
- [ ] Code reviewed and approved
- [ ] Deployed to staging environment
- [ ] User acceptance testing passed
- [ ] Deployed to production
- [ ] Monitoring and alerts configured
- [ ] Rollback plan documented

---

## Next Actions

### Immediate (This Week) - CRITICAL
1. **Review and approve Phase 0 production readiness scope**
2. **Provision Vercel Postgres database**
3. **Set up Vercel Blob storage**
4. **Migrate database schema and data**
5. **Update file upload/download logic**
6. **Fix security configurations**
7. **Deploy to Vercel staging**
8. **Test with 10 concurrent users**

### Short Term (Next 1-2 Weeks)
1. Complete Phase 0 production infrastructure
2. Production test with 10 beta users
3. Monitor errors, performance, and user feedback
4. Fix any critical bugs discovered
5. Document lessons learned
6. Plan Phase 1 (MCP Integration) kickoff

### Medium Term (Next 4-6 Weeks)
1. Complete Phase 1 (Memory MCP)
2. Complete Phase 2 (File System MCP)
3. Expand user base to 50-100 users
4. Gather feedback and iterate
5. Plan Phase 3 kickoff

### Long Term (Next 2-3 Months)
1. Complete Phase 3 (Brave Search MCP)
2. Measure impact on key metrics
3. Plan additional MCP integrations
4. Scale infrastructure as needed
5. Evaluate additional features from backlog

---

## Notes & Decisions

### Decision Log

**2025-12-08:** Production Readiness Assessment Completed
- Identified critical infrastructure blockers
- SQLite and local file storage incompatible with Vercel serverless
- Must migrate to Vercel Postgres + Vercel Blob before any deployment
- Added Phase 0 with 10 user stories for production infrastructure
- Estimated 3-4 days minimum for production readiness
- Security hardening and monitoring required

**Rationale:**
- Cannot deploy to production without persistent storage
- Data loss risk too high with current architecture
- Must fix critical blockers before feature development
- Security vulnerabilities need immediate attention
- Phase 0 is now blocker for all other phases

**2025-12-02:** MCP Integration Approach Selected
- Chose 3-phase rollout strategy
- Memory MCP prioritized for immediate impact
- File System MCP for medium-term value
- Brave Search MCP for long-term enhancement

**Rationale:**
- Incremental value delivery
- Risk mitigation through phased approach
- Each phase provides standalone value
- Can pause/adjust between phases based on results

---

### Enhancement: Spotify Remote Player Integration
**Priority:** Medium
**Effort:** Medium (1-2 weeks)
**Status:** 🔴 Not Started - Planning Phase

Add minimalist Spotify remote player to landing page for seamless music playback control without leaving Ask Chopper.

#### Feature Overview
A small, minimalist music player widget on the landing page that allows users to control their Spotify playback remotely (play, pause, next, previous) without leaving the website. Uses Spotify Connect Web API to control music on any active Spotify device.

#### Requirements

**Spotify Developer Setup:**
- [ ] Create Spotify Developer account
- [ ] Register app at https://developer.spotify.com/dashboard
- [ ] Obtain Client ID and Client Secret
- [ ] Configure redirect URI (e.g., `http://localhost:8000/callback` or production domain)

**User Requirements:**
- Spotify Premium account (required for playback control API)
- Active Spotify session on any device (phone, desktop, smart speaker, etc.)

**Technical Stack:**
- Spotify Web API (OAuth 2.0 authentication)
- Flask backend for OAuth flow and API proxying
- Vanilla JavaScript frontend for player controls
- Session/database storage for access/refresh tokens

#### Implementation Tasks

**Backend (Flask):**
- [ ] Create `/spotify/login` route for OAuth initiation
- [ ] Create `/spotify/callback` route for OAuth callback handling
- [ ] Create `/spotify/refresh-token` endpoint for token renewal
- [ ] Create `/api/spotify/play` endpoint (PUT /me/player/play)
- [ ] Create `/api/spotify/pause` endpoint (PUT /me/player/pause)
- [ ] Create `/api/spotify/next` endpoint (POST /me/player/next)
- [ ] Create `/api/spotify/previous` endpoint (POST /me/player/previous)
- [ ] Create `/api/spotify/current-track` endpoint (GET /me/player/currently-playing)
- [ ] Implement token storage (session or database table)
- [ ] Implement automatic token refresh logic
- [ ] Add error handling for expired tokens
- [ ] Add error handling for no active device

**Frontend (Landing Page):**
- [ ] Design minimalist player UI (small widget)
- [ ] Add 4 control buttons (play, pause, next, previous)
- [ ] Add "Connect Spotify" button/flow
- [ ] Implement JavaScript for API calls to Flask endpoints
- [ ] Add current track display (optional)
- [ ] Add loading states for button clicks
- [ ] Add error messages for user feedback
- [ ] Style player to match landing page aesthetic
- [ ] Make player responsive for mobile

**Database Schema:**
- [ ] Create `spotify_tokens` table (if using database storage)
  - user_id (FK to users table)
  - access_token (encrypted)
  - refresh_token (encrypted)
  - expires_at (timestamp)
  - created_at (timestamp)
  - updated_at (timestamp)

**Environment Variables:**
```bash
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8000/spotify/callback
```

#### Spotify API Endpoints to Use

**Authentication:**
- `POST https://accounts.spotify.com/api/token` - Get/refresh access token

**Playback Control:**
- `GET /me/player/currently-playing` - Get current track info
- `PUT /me/player/play` - Resume playback
- `PUT /me/player/pause` - Pause playback
- `POST /me/player/next` - Skip to next track
- `POST /me/player/previous` - Skip to previous track
- `GET /me/player/devices` - Get available devices (optional)

#### User Flow

1. User visits landing page
2. Sees "Connect Spotify" button on player widget
3. Clicks button → redirected to Spotify OAuth login
4. User authorizes Ask Chopper app
5. Redirected back to landing page with access token
6. Player shows active (with 4 control buttons)
7. User clicks play/pause/next/prev → controls active Spotify device
8. Token automatically refreshes when expired
9. Player persists across page refreshes (session/cookie)

#### Limitations & Constraints

- **Requires Spotify Premium:** Free tier users cannot use playback control API
- **Requires Active Device:** User must have Spotify open somewhere (phone, desktop, etc.)
- **Controls Existing Playback:** Does not create new player instance, only controls existing device
- **Rate Limits:** Spotify API has rate limits (should not be an issue for single-user control)
- **Token Expiry:** Access tokens expire after 1 hour (handle with refresh tokens)

#### Success Metrics

- 30% of landing page visitors connect Spotify
- 50% of connected users actively use player controls
- < 1% error rate on playback commands
- Zero security incidents (token leakage, XSS, etc.)
- Positive user feedback on convenience

#### Security Considerations

- [ ] Store tokens encrypted in database
- [ ] Use HTTPS for OAuth redirect
- [ ] Implement CSRF protection on OAuth callback
- [ ] Never expose client secret to frontend
- [ ] Implement rate limiting on API endpoints
- [ ] Validate all Spotify API responses
- [ ] Handle token revocation gracefully
- [ ] Add session timeout for security

#### UI/UX Design Notes

**Minimalist Player Design:**
- Small, unobtrusive widget (bottom corner or top navbar)
- Clean, modern buttons (SVG icons)
- Subtle animations on button clicks
- Dark theme to match landing page
- Optional: Show album art thumbnail (32x32px)
- Optional: Show track name and artist (truncated)
- Collapsible/expandable state
- Mobile-friendly touch targets

**Color Scheme:**
- Match existing landing page black (#0d0d0d)
- Spotify green accent (#1DB954) for connected state
- White icons for controls
- Subtle hover effects

#### Files to Create/Modify

**New Files:**
- `spotify_oauth.py` - Spotify OAuth handling logic
- `spotify_api.py` - Spotify API client wrapper
- `static/js/spotify-player.js` - Frontend player controls
- `static/css/spotify-player.css` - Player styling
- `templates/spotify_callback.html` - OAuth callback page (optional)

**Modified Files:**
- `app.py` - Add Spotify routes
- `templates/landing.html` - Add player widget
- `requirements.txt` - Add `spotipy` or `requests` library
- `models.py` - Add SpotifyToken model (if using database)
- `.env` - Add Spotify credentials

#### Dependencies

**Python Libraries:**
```bash
pip install spotipy  # Spotify API Python wrapper
# OR
pip install requests  # Manual API calls
pip install cryptography  # For token encryption
```

**Frontend:**
- No additional dependencies (vanilla JS)
- Optional: Fetch API polyfill for older browsers

#### Cost Analysis

**Free:**
- Spotify Web API (no cost for personal use)
- OAuth integration (no cost)
- Implementation using existing infrastructure

**Potential Costs:**
- Development time: 30-40 hours
- Testing time: 5-10 hours
- No ongoing infrastructure costs

#### Risk Assessment

**High Risk:**
- Security of stored tokens → Mitigation: Encryption, secure storage
- Token expiry handling → Mitigation: Automatic refresh logic
- No active device scenario → Mitigation: Clear error messaging

**Medium Risk:**
- Spotify API changes → Mitigation: Use official SDK, monitor changelog
- User doesn't have Premium → Mitigation: Clear messaging, graceful fallback
- Rate limiting → Mitigation: Client-side debouncing, rate limit headers

**Low Risk:**
- Browser compatibility → Mitigation: Modern browsers only, feature detection
- UI/UX confusion → Mitigation: Clear onboarding, tooltips

#### Testing Plan

**Unit Tests:**
- [ ] OAuth flow (token exchange)
- [ ] Token refresh logic
- [ ] API endpoint responses
- [ ] Error handling for all edge cases

**Integration Tests:**
- [ ] End-to-end OAuth flow
- [ ] Playback control commands
- [ ] Token expiry and refresh
- [ ] Error scenarios (no device, expired token)

**Manual Testing:**
- [ ] Test with Premium account
- [ ] Test with Free account (should show upgrade message)
- [ ] Test with no active device
- [ ] Test token expiry scenario
- [ ] Test on mobile devices
- [ ] Test across different browsers

#### Future Enhancements (Post-MVP)

- [ ] Display full now playing info (track, artist, album)
- [ ] Add progress bar with seek functionality
- [ ] Add volume control slider
- [ ] Add shuffle and repeat toggles
- [ ] Add playlist selection
- [ ] Add queue management
- [ ] Add device selection dropdown
- [ ] Add lyrics display integration
- [ ] Add smart recommendations based on listening history
- [ ] Integration with Ask Chopper AI (music recommendations)

#### Documentation Required

- [ ] User guide: "How to connect Spotify"
- [ ] Developer docs: Spotify API integration
- [ ] Troubleshooting guide: Common issues
- [ ] Security documentation: Token handling
- [ ] API documentation: Internal endpoints

#### Estimated Timeline

**Week 1:**
- Backend OAuth implementation (3 days)
- Token storage and refresh logic (1 day)
- API endpoint proxying (1 day)

**Week 2:**
- Frontend player UI design (2 days)
- JavaScript integration (2 days)
- Testing and debugging (3 days)

**Total:** 10-12 working days

#### Acceptance Criteria

- [ ] User can successfully connect Spotify account via OAuth
- [ ] User can play/pause current track
- [ ] User can skip to next track
- [ ] User can go to previous track
- [ ] Player shows clear "Connect Spotify" state when not connected
- [ ] Player shows active state when connected
- [ ] Tokens automatically refresh when expired
- [ ] Clear error messages for all failure scenarios
- [ ] Player is responsive on mobile devices
- [ ] No security vulnerabilities in token handling
- [ ] All unit and integration tests passing
- [ ] Documentation complete

#### Related User Stories

- Could integrate with US-007 (Current Music Trends) for recommendations
- Could enhance user engagement metrics from Phase 3
- Could tie into token system for rewards (listen X songs, earn tokens)

---

## Resources

### Documentation
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [MCP Memory Server](https://github.com/modelcontextprotocol/servers/tree/main/src/memory)
- [MCP Filesystem Server](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem)
- [MCP Brave Search](https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search)

### Related Files
- `PRODUCTION_READINESS_CHECKLIST.md` - Production deployment checklist
- `DATABASE_FIXES_SUMMARY.md` - Database architecture
- `PRISMA_STUDIO_FIX.md` - Database tooling
- `app.py` - Main Flask application
- `models.py` - Database models
- `seed.js` - Test data generation
- `vercel.json` - Vercel deployment configuration

---

**Last Updated:** 2025-12-22
**Version:** 2.1
**Maintained By:** Development Team
