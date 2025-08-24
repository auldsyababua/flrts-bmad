# Core Components

## 1. Bot Layer

### 1.1 Webhook Server (Production)
- **Technology**: FastAPI with async/await
- **Purpose**: Receive Telegram webhook calls in production
- **Location**: `src/bot/webhook_bot.py`
- **Key Features**:
  - Real-time message processing
  - Automatic SSL/TLS termination
  - Request validation and rate limiting
  - Health check endpoints

### 1.2 Polling Bot (Development)
- **Technology**: aiogram polling
- **Purpose**: Local development and testing
- **Location**: `src/bot/handlers.py`
- **Key Features**:
  - Hot reloading for development
  - Debug logging and error handling
  - Simulated webhook behavior

### 1.3 Message Handlers
- **Technology**: aiogram handlers with middleware
- **Purpose**: Route different message types to appropriate processors
- **Key Features**:
  - Text, voice, document, and image handling
  - User authentication and authorization
  - Message preprocessing and validation

## 2. Smart Rails Processing Layer

### 2.1 Router Component
- **Location**: `src/rails/router.py`
- **Purpose**: Intelligent message routing with confidence scoring
- **Algorithm**:
  ```python
  if confidence >= 100:
      return direct_execution()  # 0 tokens, <50ms
  elif confidence >= 80:
      return focused_llm(extracted_data)  # 50-100 tokens
  else:
      return full_llm_analysis()  # 200-500 tokens
  ```

### 2.2 Deterministic Preprocessor
- **Location**: `src/rails/processors/base_processor.py`
- **Purpose**: Extract structured data before LLM processing
- **Extraction Patterns**:
  - `@username` → Assignee with 100% confidence
  - `/command` → Entity type and operation
  - Site names → Eagle Lake, Crockett, Mathis
  - Time patterns → tomorrow, 3pm, next week
  - Equipment IDs → Generator #2, Pump A, etc.

### 2.3 Entity Processors

#### Field Report Processor
- **Location**: `src/rails/processors/field_report_processor.py`
- **Purpose**: Process field operation reports
- **Schema**:
  ```yaml
  field_report:
    site: string (Eagle Lake | Crockett | Mathis)
    equipment: string
    status: string (operational | warning | failure)
    operator: string
    timestamp: datetime
    description: text
    attachments: array[file]
  ```

#### Task Processor
- **Location**: `src/rails/processors/task_processor.py`
- **Purpose**: Manage tasks and reminders
- **Schema**:
  ```yaml
  task:
    title: string
    assignee: string
    site: string
    priority: enum (low | medium | high | urgent)
    deadline: datetime
    parent_task: uuid (optional)
    status: enum (pending | in_progress | completed | cancelled)
    dependencies: array[uuid]
  ```

#### List Processor
- **Location**: `src/rails/processors/list_processor.py`
- **Purpose**: Manage shopping, tool, and equipment lists
- **Schema**:
  ```yaml
  list:
    type: enum (shopping | tools | equipment)
    site: string
    items: array[list_item]
    owner: string
    last_updated: datetime
  
  list_item:
    name: string
    quantity: integer
    status: enum (needed | ordered | received)
    priority: enum (low | medium | high)
  ```

## 3. Storage Layer

### 3.1 Document Storage Service
- **Location**: `src/storage/storage_service.py`
- **Database**: Supabase PostgreSQL
- **Purpose**: Structured data storage with audit trails
- **Key Tables**:
  - `documents` - Main document storage
  - `document_versions` - Version history
  - `audit_logs` - All system operations
  - `user_sessions` - Authentication tracking

### 3.2 Vector Store Service
- **Location**: `src/storage/vector_store.py`
- **Database**: Upstash Vector
- **Purpose**: Semantic search and similarity matching
- **Features**:
  - Namespace isolation (10netzero)
  - Automatic embedding generation
  - Similarity search with configurable k
  - Caching layer for performance

### 3.3 Redis Store Service
- **Location**: `src/storage/redis_store.py`
- **Database**: Upstash Redis
- **Purpose**: Session management and caching
- **Data Types**:
  - Conversation history (TTL: 24 hours)
  - Search result cache (TTL: 5 minutes)
  - Rate limiting counters
  - System configuration

### 3.4 Media Storage Service
- **Location**: `src/storage/media_storage.py`
- **Storage**: Supabase Storage
- **Purpose**: File and image storage
- **Features**:
  - Automatic file type detection
  - Image thumbnail generation
  - PDF text extraction
  - Access control and signing

## 4. Intelligence Layer

### 4.1 LLM Service
- **Location**: `src/core/llm.py`
- **Provider**: OpenAI GPT-4o
- **Purpose**: Natural language understanding and generation
- **Features**:
  - Dynamic prompt generation
  - Context-aware responses
  - Fallback to GPT-3.5-turbo
  - Token usage optimization

### 4.2 Memory Service (mem0)
- **Location**: `src/core/memory.py`
- **Database**: Neo4j (optional)
- **Purpose**: Relationship tracking and context building
- **Capabilities**:
  - Entity relationship mapping
  - Conversation memory
  - User preference learning
  - Cross-session context

## 5. Frontend Layer

### 5.1 Telegram Mini App
- **Location**: `telegram-mini-app/`
- **Technology**: React 18 + TypeScript + Vite
- **Purpose**: Mobile-optimized interface for FLRTS operations

#### Component Architecture
```
src/
├── components/
│   ├── Chat/           # Real-time messaging
│   ├── Dashboard/      # Operations overview
│   ├── Lists/          # List management
│   ├── Tasks/          # Task tracking
│   └── Common/         # Shared components
├── services/           # API communication
├── context/            # State management
└── utils/              # Helper functions
```

#### Key Features
- **Real-time sync** with backend via WebSocket
- **Offline reading** with service worker caching
- **Mobile-first design** with touch optimization
- **Progressive Web App** capabilities
