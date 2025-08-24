# FLRTS BrainBot Architecture Document

## System Overview

The FLRTS BrainBot is a Python and React/TypeScript application designed for low-friction task, list, and note management via a Telegram bot. The system uses Supabase for its database, OpenAI for intelligence, and is in the process of migrating vector/caching services from Upstash to Cloudflare.

## Core Architecture Components

### Smart Rails System
The core innovation of the system is the "Smart Rails" system, which preprocesses natural language commands to reduce latency and cost by bypassing LLM calls for high-confidence actions. This system:
- Routes high-confidence commands directly to processors
- Falls back to LLM for ambiguous requests
- Maintains sub-500ms response times for direct execution

### Technology Stack
- **Backend**: Python >=3.9 with FastAPI 0.111.0
- **Frontend**: React ^18.3.1 with TypeScript ^5.6.0
- **Bot Framework**: python-telegram-bot 21.0.1
- **Database**: Supabase (PostgreSQL) 2.11.0
- **Vector Store**: Migrating from Upstash to Cloudflare Vectorize
- **Cache**: Migrating from Upstash Redis to Cloudflare KV/Redis
- **AI/ML**: OpenAI GPT-4o, mem0ai 0.0.15
- **Deployment**: Render.com

## Project Structure

```
flrts-bmad/
├── src/
│   ├── rails/           # Smart Rails routing system
│   │   ├── router.py     # Main routing logic
│   │   └── processors/   # Direct execution processors
│   ├── storage/          # Data storage layer
│   │   └── vector_store.py  # Vector operations (migrating)
│   ├── api/             # API endpoints
│   ├── telegram/        # Telegram bot integration
│   └── utils/           # Utilities and helpers
├── tests/               # Test suite
├── web-bundles/         # Frontend React application
├── docs/                # Documentation
├── .github/             # GitHub Actions workflows
└── render.yaml          # Render deployment config
```

## Data Flow

1. **User Input**: Natural language command via Telegram
2. **Smart Rails Router**: Analyzes intent and confidence
3. **Decision Point**:
   - High confidence (>95%): Direct processor execution
   - Low confidence: LLM processing via OpenAI
4. **Database Operations**: CRUD via Supabase
5. **Response**: Formatted message back to user

## Service Architecture

### Production Environment
- **Main Branch**: Deploys to production on Render.com
- **Database**: Production Supabase instance
- **Services**: Production Cloudflare services

### Development Environment (Post-MVP)
- **Develop Branch**: Deploys to preview environment
- **Database**: Separate Supabase instance
- **Services**: Separate Cloudflare instances

## Migration Strategy

### Current State (Legacy)
- Vector storage: Upstash Vector
- Caching: Upstash Redis
- Memory: mem0 with Upstash backend

### Target State
- Vector storage: Cloudflare Vectorize
- Caching: Cloudflare KV or Redis
- Memory: mem0 with Cloudflare backend

## Security & Performance

### Security Measures
- Environment-based configuration
- Secure API key management
- Telegram webhook validation
- Database row-level security

### Performance Targets
- Direct command execution: <500ms
- LLM fallback: <3s
- Cold start elimination via always-on services
- Caching for frequent operations

## Monitoring & Logging

- **Application Logs**: SupabaseLogger integration
- **Health Checks**: `/health` endpoint monitoring all services
- **Error Tracking**: Comprehensive error logging
- **User Corrections**: Dedicated table for improvement tracking

## Development Workflow

### Git Strategy
- `main`: Production branch
- `develop`: Integration branch for new features
- Feature branches: Created from `develop`

### CI/CD Pipeline
- GitHub Actions for automated testing
- Render.com automatic deployments
- Environment-specific configurations

## API Endpoints

### Core Endpoints
- `POST /webhook`: Telegram webhook handler
- `GET /health`: System health check
- `POST /process`: Command processing

### Internal APIs
- TaskProcessor: Direct task CRUD operations
- ListProcessor: Direct list CRUD operations
- VectorStore: Embedding operations
- CacheManager: Session and state management

## Database Schema

### Core Tables
- `users`: User profiles and preferences
- `tasks`: Task entries with metadata
- `lists`: List definitions
- `list_items`: Items within lists
- `notes`: Freeform notes
- `user_corrections`: Correction feedback (planned)

### Relationships
- Users -> Tasks (one-to-many)
- Users -> Lists (one-to-many)
- Lists -> ListItems (one-to-many)
- Users -> Notes (one-to-many)

## Future Architecture Considerations

### Post-MVP Enhancements
1. **Serverless Migration**: Move to Cloudflare Workers
2. **Enhanced Learning**: User-specific routing rules
3. **Workers AI Integration**: Evaluate Cloudflare AI models
4. **Multi-channel Support**: Beyond Telegram

### Scalability Plan
- Horizontal scaling via Render
- Database connection pooling
- Aggressive caching strategies
- CDN for static assets