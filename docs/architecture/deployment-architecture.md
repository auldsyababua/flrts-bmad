# Deployment Architecture

## Production Environment
```yaml
platform: render.com
services:
  - name: brainbot-api
    type: web_service
    runtime: python3.9
    build_command: pip install -r requirements.txt
    start_command: python main.py
    environment:
      - TELEGRAM_BOT_TOKEN
      - OPENAI_API_KEY
      - SUPABASE_URL
      - SUPABASE_KEY
      - UPSTASH_REDIS_REST_URL
      - UPSTASH_REDIS_REST_TOKEN
      - UPSTASH_VECTOR_REST_URL
      - UPSTASH_VECTOR_REST_TOKEN
```

## Development Environment
```yaml
local_development:
  runtime: python3.9
  package_manager: uv
  environment_file: .env
  start_command: python run_bot.py
  hot_reload: true
  debug_mode: true
```

## Container Architecture (Future)
```dockerfile