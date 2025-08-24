# Functional Requirements

## Epic 1: Core Bot Functionality

### Epic 1.1: User Authentication & Authorization
- **FR-1.1.1**: Bot SHALL authenticate users via Telegram user ID
- **FR-1.1.2**: System SHALL maintain authorized user whitelist
- **FR-1.1.3**: Unauthorized access SHALL be logged and rejected

### Epic 1.2: Message Processing
- **FR-1.2.1**: Bot SHALL accept text, voice, images, and documents
- **FR-1.2.2**: System SHALL preserve original message metadata
- **FR-1.2.3**: Processing SHALL complete within 5 seconds for text messages

## Epic 2: Smart Rails Routing System

### Epic 2.1: Deterministic Preprocessing
- **FR-2.1.1**: System SHALL extract @mentions with 100% confidence
- **FR-2.1.2**: System SHALL extract /commands with 100% confidence
- **FR-2.1.3**: System SHALL identify site references (Eagle Lake, Crockett, Mathis)
- **FR-2.1.4**: System SHALL recognize time patterns (tomorrow, 3pm, next week)

### Epic 2.2: Entity Type Classification
- **FR-2.2.1**: System SHALL route to appropriate processor:
  - `/newlist` → List Processor
  - `/newtask` → Task Processor
  - `/report` → Field Report Processor
  - Natural language → Dynamic routing

### Epic 2.3: Confidence-Based Execution
- **FR-2.3.1**: 100% confidence → Direct execution (0 tokens)
- **FR-2.3.2**: 80-99% confidence → Focused LLM (50-100 tokens)
- **FR-2.3.3**: <80% confidence → Full LLM analysis (200-500 tokens)

## Epic 3: FLRTS Entity Management

### Epic 3.1: Field Reports
- **FR-3.1.1**: System SHALL create structured field reports with metadata
- **FR-3.1.2**: Reports SHALL include site, timestamp, operator, equipment status
- **FR-3.1.3**: System SHALL support image attachments and equipment photos

### Epic 3.2: Lists Management
- **FR-3.2.1**: System SHALL maintain shopping lists, tool lists, equipment lists
- **FR-3.2.2**: Lists SHALL support add/remove operations via natural language
- **FR-3.2.3**: System SHALL track list ownership and modification history

### Epic 3.3: Tasks & Reminders
- **FR-3.3.1**: System SHALL create tasks with assignee, deadline, priority
- **FR-3.3.2**: Tasks SHALL support hierarchical sub-tasks
- **FR-3.3.3**: System SHALL send deadline reminders via Telegram

## Epic 4: Storage & Persistence

### Epic 4.1: Document Storage
- **FR-4.1.1**: System SHALL use Supabase for structured data
- **FR-4.1.2**: System SHALL maintain audit trail for all operations
- **FR-4.1.3**: Documents SHALL be versioned with change tracking

### Epic 4.2: Vector Search
- **FR-4.2.1**: System SHALL use Upstash Vector for semantic search
- **FR-4.2.2**: Search SHALL return relevant results within 2 seconds
- **FR-4.2.3**: System SHALL maintain search result caching

### Epic 4.3: Graph Memory
- **FR-4.3.1**: System SHALL use Neo4j for relationship tracking
- **FR-4.3.2**: Entities SHALL be linked (tasks→sites, reports→equipment)
- **FR-4.3.3**: System SHALL support relationship queries

## Epic 5: Telegram Mini App

### Epic 5.1: Mobile Interface
- **FR-5.1.1**: App SHALL provide mobile-optimized interface
- **FR-5.1.2**: Users SHALL access dashboard, tasks, lists, and chat
- **FR-5.1.3**: Interface SHALL support offline reading

### Epic 5.2: Real-time Sync
- **FR-5.2.1**: Changes SHALL sync between bot and web app
- **FR-5.2.2**: System SHALL show typing indicators and status updates
- **FR-5.2.3**: App SHALL support push notifications
