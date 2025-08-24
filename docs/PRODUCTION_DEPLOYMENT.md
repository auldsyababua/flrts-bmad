# FLRTS-BMAD Production Deployment Guide

**For Small Teams (5-20 users) with Story 1.6 Direct Execution**

## Quick Start Checklist

### 1. Environment Setup ✅
```bash
# Copy and configure environment
cp .env.example.clean .env
# Edit .env with your actual credentials

# Validate configuration
python scripts/validate_config.py
```

### 2. Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt

# Verify Story 1.6 integration
python -c "from src.rails.router import KeywordRouter; r = KeywordRouter(); print('✅ Direct execution ready')"
```

### 3. Database Setup
```bash
# Run any pending migrations
python scripts/migrate_database.py  # (to be created)

# Verify database connectivity
python scripts/validate_config.py --env-file .env
```

### 4. Health Checks
```bash
# Start the application
python main.py

# Test health endpoints (in another terminal)
curl http://localhost:5000/health/
curl http://localhost:5000/health/story-1-6
```

## Production Configuration

### Required Environment Variables
```bash
# Core services
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Authorization (JSON arrays)
AUTHORIZED_USERNAMES='["user1", "user2"]'
AUTHORIZED_USER_IDS='[123456, 789012]'

# Cloudflare (optional but recommended)
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_api_token
USE_CLOUDFLARE_VECTORIZE=true
USE_CLOUDFLARE_CACHE=true
```

### Performance Settings (Small Team Optimized)
```bash
# Database pools (conservative for 5-20 users)
SUPABASE_POOL_SIZE=5
SUPABASE_MAX_OVERFLOW=2
SUPABASE_POOL_TIMEOUT=10

# Story 1.6 settings
GPT_MODEL=gpt-4o-mini  # Faster for fallbacks
MAX_TOKENS=1000        # Smaller for speed
TEMPERATURE=0.1        # Consistent for direct execution
```

## Deployment Options

### Option A: Simple Server Deployment (Recommended)
```bash
# For small teams - single server deployment
git clone your-repo
cd flrts-bmad
cp .env.example.clean .env
# Configure .env
pip install -r requirements.txt
python main.py
```

### Option B: Docker Deployment
```dockerfile
# Dockerfile (create if needed)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Option C: Cloud Platform (Render.com/Railway)
- Connect your Git repository
- Set environment variables in platform UI
- Deploy automatically on push

## Monitoring & Health Checks

### Health Check Endpoints
```
GET /health/           # Basic health (for load balancers)
GET /health/detailed   # Full system status
GET /health/story-1-6  # Direct execution status
GET /health/ready      # Kubernetes-style readiness
GET /health/live       # Kubernetes-style liveness
```

### Production Logging
Story 1.6 operations are automatically logged with prefixes:
- `[STORY-1.6-DIRECT]` - Direct execution operations
- `[STORY-1.6-ROUTER]` - Routing decisions
- `[STORY-1.6-PERF]` - Performance warnings
- `[STORY-1.6-SYSTEM]` - System events

### Performance Monitoring
```bash
# Check direct execution performance
curl http://localhost:5000/health/performance

# Monitor logs for Story 1.6 operations
tail -f app.log | grep "STORY-1.6"
```

## Story 1.6 Verification

### Test Direct Execution
```bash
# These should trigger direct execution (bypass LLM)
curl -X POST http://localhost:5000/api/message \
  -H "Content-Type: application/json" \
  -d '{"message": "/newtask Check oil levels @john", "user_id": "123"}'

# Verify in logs:
# [STORY-1.6-ROUTER] tasks/create (confidence: 1.00, direct: true)
# [STORY-1.6-DIRECT] create for tasks: SUCCESS in 45.2ms (confidence: 1.00, bypassed_llm: true)
```

### Performance Targets
- **Direct Execution**: <500ms (typically <100ms)
- **Router Decisions**: <50ms  
- **Health Checks**: <200ms
- **Overall Request**: <1000ms including database

## Security Checklist

- [ ] Environment variables are not exposed in logs
- [ ] `DEBUG=false` in production
- [ ] `TESTING_MODE=false` in production
- [ ] HTTPS enabled (if web interface)
- [ ] Authorized users configured correctly
- [ ] API keys rotated regularly

## Backup & Recovery

### Database Backups
```bash
# Supabase automatically backs up, but you can export:
# Use Supabase dashboard or CLI for exports
```

### Configuration Backups
```bash
# Backup your .env file securely
cp .env .env.backup
# Store in secure location (not in Git!)
```

## Troubleshooting

### Common Issues

1. **Direct Execution Not Working**
   ```bash
   # Check health endpoint
   curl http://localhost:5000/health/story-1-6
   # Should show "direct_execution_ready": true
   ```

2. **Performance Issues**
   ```bash
   # Check performance summary
   curl http://localhost:5000/health/performance
   # Look for Story 1.6 performance metrics
   ```

3. **Database Connection Issues**
   ```bash
   # Validate configuration
   python scripts/validate_config.py
   ```

### Logs to Monitor
```bash
# Error logs
grep "ERROR" app.log

# Story 1.6 performance warnings  
grep "STORY-1.6-PERF" app.log

# Direct execution failures
grep "STORY-1.6-DIRECT.*FAILED" app.log
```

## Scaling Considerations

For 5-20 users, this deployment should handle:
- **Concurrent Users**: 5-10 simultaneous
- **Daily Messages**: 500-2000 
- **Direct Execution Rate**: 60-80% of commands
- **Response Time**: <500ms for direct, <2s for LLM fallback

If you exceed these limits:
1. Increase database pool sizes
2. Consider horizontal scaling
3. Optimize slow queries
4. Add Redis caching

## Support

### Health Check URLs (bookmark these)
- System Status: `http://your-domain/health/detailed`
- Story 1.6 Status: `http://your-domain/health/story-1-6`
- Performance: `http://your-domain/health/performance`

### Configuration Validation
```bash
# Run before any deployment
python scripts/validate_config.py --env-file .env
```

**Story 1.6 Direct Execution is ready for production! 🚀**