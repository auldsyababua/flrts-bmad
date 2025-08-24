# BrainBot Requirements Specification

## Overview

BrainBot is an intelligent Telegram bot that acts as a personal filing assistant using Creation Augmented Generation (CAG). It automatically organizes information without asking questions, preserving all sources with an audit trail.

## User Stories and Requirements

### 1. Core Bot Functionality

#### US-1.1: Bot Initialization
**As a** team member  
**I want to** start interacting with the bot  
**So that** I can begin organizing my information

**Acceptance Criteria (EARS Format):**
- WHEN a user sends /start command THEN the system SHALL display a welcome message with available commands
- WHEN an unauthorized user attempts to use the bot THEN the system SHALL display an authorization rejection message
- IF the user is authorized THEN the system SHALL allow full bot functionality

#### US-1.2: Message Processing
**As a** user  
**I want to** send any text to the bot  
**So that** it automatically organizes the information

**Acceptance Criteria:**
- WHEN a user sends a text message THEN the system SHALL analyze content using GPT-4o
- WHEN content is analyzed THEN the system SHALL decide whether to merge with existing content or create new
- WHEN content is processed THEN the system SHALL preserve the original source with metadata
- WHEN processing is complete THEN the system SHALL send a brief confirmation message

### 2. Smart Rails Routing

#### US-2.1: Deterministic Command Processing
**As a** user  
**I want to** use specific commands for different entity types  
**So that** the bot processes my requests accurately

**Acceptance Criteria:**
- WHEN a user includes @username THEN the system SHALL extract it as assignee with 100% confidence
- WHEN a user includes /command THEN the system SHALL extract entity type/operation with 100% confidence
- WHEN preprocessing is complete THEN the system SHALL send only cleaned content to LLM

#### US-2.2: Entity Type Routing
**As a** user  
**I want to** work with different entity types  
**So that** information is organized appropriately

**Acceptance Criteria:**
- WHEN /lists is used THEN the system SHALL route to list processor
- WHEN /tasks is used THEN the system SHALL route to task processor
- WHEN /reports is used THEN the system SHALL route to field report processor
- IF no explicit command is used THEN the system SHALL use pattern matching with confidence scoring

#### US-2.3: Command Routing Specifications
**As a** user  
**I want** explicit command syntax to route deterministically  
**So that** I get predictable, fast responses for common operations

**Acceptance Criteria (EARS format):**

**Hidden Commands (100% confidence):**
- WHEN the user sends "/newlist [name]" THEN the system SHALL route to entity_type='lists' AND operation='create' with 100% confidence
- WHEN the user sends "/addtolist [items]" THEN the system SHALL route to entity_type='lists' AND operation='add_items' with 100% confidence
- WHEN the user sends "/removefromlist [items]" THEN the system SHALL route to entity_type='lists' AND operation='remove_items' with 100% confidence
- WHEN the user sends "/showlist [name]" THEN the system SHALL route to entity_type='lists' AND operation='read' with 100% confidence
- WHEN the user sends "/newtask [description]" THEN the system SHALL route to entity_type='tasks' AND operation='create' with 100% confidence
- WHEN the user sends "/newreminder [description]" THEN the system SHALL route to entity_type='tasks' AND operation='create' with 100% confidence
- WHEN the user sends "/completetask [description]" THEN the system SHALL route to entity_type='tasks' AND operation='complete' with 100% confidence
- WHEN the user sends "/reassigntask [description]" THEN the system SHALL route to entity_type='tasks' AND operation='reassign' with 100% confidence
- WHEN the user sends "/showtasks" THEN the system SHALL route to entity_type='tasks' AND operation='read' with 100% confidence
- WHEN the user sends "/showmytasks" THEN the system SHALL route to entity_type='tasks' AND operation='read' with 100% confidence
- WHEN the user sends "/showmyreminders" THEN the system SHALL route to entity_type='tasks' AND operation='read' with 100% confidence

**Telegram Category Commands (entity routing only):**
- WHEN the user sends "/lists [any text]" OR "/l [any text]" THEN the system SHALL set entity_type='lists' AND let LLM determine operation
- WHEN the user sends "/tasks [any text]" OR "/t [any text]" OR "/tnr [any text]" THEN the system SHALL set entity_type='tasks' AND let LLM determine operation
- WHEN the user sends "/fr [any text]" THEN the system SHALL set entity_type='field_reports' AND let LLM determine operation

**Natural Language Patterns (Lists):**
- WHEN the user message contains "new list|create list|make list|start list|build list" THEN the system SHALL suggest entity_type='lists' AND operation='create'
- WHEN the user message contains "show list|print list|read list|what's on|display list|view list" THEN the system SHALL suggest entity_type='lists' AND operation='read'
- WHEN the user message contains "add to list|append to list|include in list|put on list|list needs" THEN the system SHALL suggest entity_type='lists' AND operation='add_items'
- WHEN the user message contains "remove from list|take off list|delete from list|take out" THEN the system SHALL suggest entity_type='lists' AND operation='remove_items'
- WHEN the user message contains "rename list|change list name|call list" THEN the system SHALL suggest entity_type='lists' AND operation='rename'
- WHEN the user message contains "clear list|empty list|remove all" THEN the system SHALL suggest entity_type='lists' AND operation='clear'
- WHEN the user message contains "delete list|remove list|trash list" THEN the system SHALL suggest entity_type='lists' AND operation='delete'

**Natural Language Patterns (Tasks):**
- WHEN the user message contains "new task|create task|add task|remind me|task for" THEN the system SHALL suggest entity_type='tasks' AND operation='create'
- WHEN the user message contains "show tasks|list tasks|what tasks|my tasks|tasks for" THEN the system SHALL suggest entity_type='tasks' AND operation='read'
- WHEN the user message contains "mark complete|finish task|done with|task complete|completed" THEN the system SHALL suggest entity_type='tasks' AND operation='complete'
- WHEN the user message contains "reassign to|assign to|assign|give to|transfer to|hand to" THEN the system SHALL suggest entity_type='tasks' AND operation='reassign'
- WHEN the user message contains "reschedule to|move to|change date|push to" THEN the system SHALL suggest entity_type='tasks' AND operation='reschedule'
- WHEN the user message contains "add note to|note on|update with|add details" THEN the system SHALL suggest entity_type='tasks' AND operation='add_notes'

**Natural Language Patterns (Field Reports):**
- WHEN the user message contains "new field report|create field report|field report for|report for" THEN the system SHALL suggest entity_type='field_reports' AND operation='create'
- WHEN the user message contains "show field report|latest field report|read field report|reports for" THEN the system SHALL suggest entity_type='field_reports' AND operation='read'
- WHEN the user message contains "add followup|followup for|action item|needs followup" THEN the system SHALL suggest entity_type='field_reports' AND operation='add_followups'
- WHEN the user message contains "mark report|report status|finalize report|draft report" THEN the system SHALL suggest entity_type='field_reports' AND operation='update_status'

**Confidence Scoring Rules:**
- IF a hidden command is detected THEN confidence SHALL be 1.0 (100%)
- IF a telegram category command is detected THEN entity confidence SHALL be 1.0 but operation confidence depends on keyword matching
- IF only natural language patterns match THEN confidence SHALL be calculated based on:
  - Keyword position (earlier = higher confidence)
  - Keyword length (longer = higher confidence)  
  - User assignment presence (@mentions increase confidence)
  - Context clues (time references for tasks, site names for reports)
- IF confidence >= 0.7 THEN the system SHALL use direct routing
- IF confidence < 0.7 THEN the system SHALL fall back to LLM processing

**User Assignment Extraction:**
- WHEN the user message contains "@[username]" THEN the system SHALL extract username as assignee with 100% confidence
- WHEN assignee is extracted THEN the system SHALL resolve to canonical username using personnel table aliases
- IF multiple @mentions exist THEN the system SHALL extract all as a list of assignees

### 3. Storage and Retrieval

#### US-3.1: Document Storage
**As a** user  
**I want** my information stored persistently  
**So that** I can retrieve it later

**Acceptance Criteria:**
- WHEN content is created THEN the system SHALL store in Supabase with metadata
- WHEN content is stored THEN the system SHALL index in Upstash Vector for semantic search
- WHEN storing documents THEN the system SHALL maintain YAML frontmatter format
- IF storage fails THEN the system SHALL retry with exponential backoff

#### US-3.2: Semantic Search
**As a** user  
**I want to** search for information using natural language  
**So that** I can find relevant content easily

**Acceptance Criteria:**
- WHEN a user asks a question THEN the system SHALL perform semantic vector search
- WHEN search is performed THEN the system SHALL return top K relevant results
- IF vector search is enabled THEN the system SHALL use caching for performance
- WHEN results are found THEN the system SHALL synthesize an intelligent response

### 4. Memory Management (mem0)

#### US-4.1: Conversation Memory
**As a** user  
**I want** the bot to remember our conversations  
**So that** it maintains context over time

**Acceptance Criteria:**
- WHEN a conversation occurs THEN the system SHALL extract important memories using mem0
- WHEN memories are extracted THEN the system SHALL store with user context
- IF graph memory is enabled THEN the system SHALL create relationship mappings
- WHEN /memories command is used THEN the system SHALL display user's memories

#### US-4.2: Memory Corrections
**As a** user  
**I want to** correct wrong memories  
**So that** the bot maintains accurate information

**Acceptance Criteria:**
- WHEN /correct command is used THEN the system SHALL update the specified memory
- WHEN memory is updated THEN the system SHALL maintain version history
- IF webhooks are configured THEN the system SHALL send memory update notifications

### 5. Multi-User Support

#### US-5.1: User Authorization
**As an** administrator  
**I want to** control who can use the bot  
**So that** only authorized team members have access

**Acceptance Criteria:**
- WHEN checking authorization THEN the system SHALL verify against Supabase personnel table
- IF user has valid Telegram username in personnel table THEN the system SHALL grant access
- WHEN unauthorized access is attempted THEN the system SHALL log the attempt

#### US-5.2: User Isolation
**As a** user  
**I want** my data isolated from other users  
**So that** information remains private

**Acceptance Criteria:**
- WHEN storing data THEN the system SHALL associate with user's Telegram ID
- WHEN retrieving data THEN the system SHALL filter by user context
- IF namespace isolation is enabled THEN the system SHALL use separate vector namespaces

### 6. Document Processing

#### US-6.1: File Upload Handling
**As a** user  
**I want to** upload documents to the bot  
**So that** their content becomes searchable

**Acceptance Criteria:**
- WHEN a document is uploaded THEN the system SHALL download and process it
- WHEN processing PDFs THEN the system SHALL extract text content
- WHEN content exceeds limits THEN the system SHALL chunk into smaller pieces
- WHEN processing is complete THEN the system SHALL index all chunks

### 7. Performance Requirements

#### NF-7.1: Response Time
- WHEN processing a message THEN the system SHALL respond within 5 seconds
- WHEN performing vector search THEN the system SHALL return results within 2 seconds
- IF cache is enabled THEN the system SHALL serve cached results within 500ms
- POST-MIGRATION: WHEN on Cloudflare THEN the system SHALL achieve <50ms latency for edge operations

#### NF-7.2: Scalability
- The system SHALL support concurrent users without performance degradation
- The system SHALL handle documents up to 10MB in size
- The system SHALL maintain conversation history for configurable TTL
- POST-MIGRATION: The system SHALL leverage Cloudflare's global edge network for unlimited scalability

#### NF-7.3: Reliability
- The system SHALL retry failed operations with exponential backoff
- The system SHALL log all errors to Supabase for monitoring
- The system SHALL gracefully handle API failures with user-friendly messages
- POST-MIGRATION: The system SHALL use Durable Objects for guaranteed state consistency

#### NF-7.4: Cost Optimization (Migration Target)
- The system SHALL reduce infrastructure costs by 70% through Cloudflare free tier usage
- The system SHALL eliminate monthly Supabase/Upstash fees
- The system SHALL use R2 storage with zero egress fees
- The system SHALL operate within Cloudflare Workers free tier limits (100k requests/day)

### 8. Deployment Requirements

#### US-8.1: Production Deployment (Current - Python)
**As an** operations team  
**I want** the bot deployed on Render  
**So that** it's accessible 24/7

**Acceptance Criteria:**
- WHEN deployed THEN the system SHALL use webhook mode for efficiency
- WHEN webhook is configured THEN the system SHALL verify SSL certificate
- The system SHALL provide health check endpoint at /health
- The system SHALL expose metrics endpoint at /metrics

#### US-8.2: Cloudflare Migration
**As an** operations team  
**I want** the bot migrated to Cloudflare Workers  
**So that** we reduce costs and improve global performance

**Acceptance Criteria:**
- WHEN migrated THEN the system SHALL run on Cloudflare Workers edge infrastructure
- WHEN processing messages THEN the system SHALL use Queues for reliable delivery
- WHEN storing data THEN the system SHALL use KV for metadata, R2 for documents, and Vectorize for embeddings
- IF complex orchestration is needed THEN the system SHALL integrate with n8n workflows
- WHEN migration is complete THEN the system SHALL achieve <50ms latency globally

#### US-8.3: Zero-Downtime Migration
**As a** user  
**I want** uninterrupted service during migration  
**So that** my workflow is not disrupted

**Acceptance Criteria:**
- WHEN migrating THEN the system SHALL run both Python and Cloudflare systems in parallel
- WHEN routing traffic THEN the system SHALL support percentage-based distribution
- IF Cloudflare processing fails THEN the system SHALL fallback to Python processor
- WHEN migration is complete THEN the system SHALL gracefully deprecate Python backend

## Non-Functional Requirements

### Security
- All API keys SHALL be stored in environment variables
- User data SHALL be encrypted in transit using TLS
- Sensitive data SHALL never be logged or exposed in responses

### Maintainability
- All code SHALL follow Python PEP-8 standards
- All functions SHALL have comprehensive docstrings
- Test coverage SHALL be maintained above 80%

### Compliance
- The system SHALL comply with Telegram Bot API terms of service
- The system SHALL respect OpenAI usage policies
- User data SHALL be handled according to privacy regulations

---

## Extending Requirements

When adding new features:
1. Create a new user story following the format above
2. Define acceptance criteria in EARS format
3. Ensure traceability to design and tasks
4. Update this document before implementation begins