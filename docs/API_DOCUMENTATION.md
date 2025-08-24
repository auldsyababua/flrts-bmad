# FLRTS-BMAD API Documentation

## Overview

The FLRTS-BMAD system provides REST API endpoints for health monitoring, webhook processing, and Story 1.6 Direct Execution features. This documentation covers all available endpoints for production use.

---

## Base URL

- **Local Development**: `http://localhost:8000`
- **Production**: `https://your-domain.com`

---

## Health Check Endpoints

### GET /health

Basic health check endpoint for load balancers and monitoring systems.

**Response** (200 OK or 503 Service Unavailable):
```json
{
  "status": "healthy|unhealthy",
  "timestamp": 1755639910.85494,
  "uptime_seconds": 27.4,
  "services": {
    "database": {
      "redis": {
        "status": "healthy|degraded|unhealthy",
        "error": null,
        "response_time_ms": 2.44
      },
      "vector_store": {
        "status": "healthy|degraded|unhealthy",
        "error": null,
        "response_time_ms": 15.3
      }
    },
    "memory": {
      "status": "healthy",
      "error": null,
      "response_time_ms": 22.21
    }
  },
  "system": {
    "memory": {
      "total_mb": 16384.0,
      "used_mb": 7141.28,
      "available_mb": 3216.38,
      "percent_used": 80.4
    },
    "cpu": {
      "percent_used": 27.3
    },
    "disk": {
      "total_gb": 228.27,
      "used_gb": 13.73,
      "free_gb": 9.43,
      "percent_used": 6.02
    },
    "uptime": {
      "seconds": 27.4,
      "human_readable": "0:00:27"
    }
  },
  "bot_info": {
    "name": "Markdown Brain Bot",
    "mode": "webhook",
    "version": "1.0.0"
  }
}
```

**Status Codes**:
- `200 OK`: System is healthy
- `503 Service Unavailable`: One or more critical services are unhealthy

**Usage Example**:
```bash
curl http://localhost:8000/health
```

---

## Webhook Endpoints

### POST /webhook

Receives updates from Telegram webhook.

**Headers**:
- `Content-Type: application/json`
- `X-Telegram-Bot-Api-Secret-Token` (optional): Secret token for webhook validation

**Request Body**:
```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 42,
    "from": {
      "id": 123456,
      "is_bot": false,
      "first_name": "John",
      "username": "johndoe"
    },
    "chat": {
      "id": 123456,
      "type": "private"
    },
    "date": 1755639910,
    "text": "/newtask Check oil levels @john"
  }
}
```

**Response** (200 OK):
```json
{
  "status": "ok"
}
```

**Story 1.6 Direct Execution**:
Commands with high confidence (≥0.8) bypass the LLM for immediate execution:
- `/newtask`, `/newlist`, `/newreport`
- Natural language: "add task", "create list", "make report"

---

## Story 1.6 Direct Execution API

### GET /api/metrics/story-16

Get Story 1.6 performance metrics (planned endpoint).

**Response** (200 OK):
```json
{
  "timestamp": 1755639910,
  "metrics": {
    "avg_confidence": 0.85,
    "direct_execution_rate": 0.75,
    "bypassed_llm_count": 450,
    "llm_fallback_count": 150,
    "avg_response_time_ms": 125,
    "p95_response_time_ms": 480,
    "router_decisions": {
      "tasks": {
        "create": 250,
        "update": 100,
        "delete": 50
      },
      "lists": {
        "create": 30,
        "update": 15,
        "delete": 5
      }
    }
  },
  "status": {
    "direct_execution_enabled": true,
    "confidence_threshold": 0.8,
    "synonym_library_version": "1.0.0"
  }
}
```

### POST /api/test/router

Test the Story 1.6 router with a command (development only).

**Request Body**:
```json
{
  "command": "add task clean kitchen"
}
```

**Response** (200 OK):
```json
{
  "entity_type": "tasks",
  "operation": "create",
  "confidence": 1.0,
  "direct_execution": true,
  "bypasses_llm": true,
  "processing_time_ms": 12
}
```

---

## Performance Targets

All endpoints should meet these performance targets for small teams (5-20 users):

| Endpoint | Target Response Time | Notes |
|----------|---------------------|--------|
| `/health` | < 200ms | For load balancer checks |
| `/webhook` (direct) | < 500ms | Story 1.6 direct execution |
| `/webhook` (LLM) | < 2000ms | When LLM fallback needed |
| `/api/metrics/*` | < 100ms | Metrics should be cached |

---

## Error Responses

All endpoints may return these error responses:

### 400 Bad Request
```json
{
  "error": "Invalid request format",
  "detail": "Missing required field: message.text"
}
```

### 401 Unauthorized
```json
{
  "error": "Unauthorized",
  "detail": "Invalid or missing authentication"
}
```

### 404 Not Found
```json
{
  "detail": "Not Found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "detail": "An unexpected error occurred"
}
```

### 503 Service Unavailable
```json
{
  "error": "Service temporarily unavailable",
  "detail": "Database connection failed"
}
```

---

## Authentication

The webhook endpoint validates requests using:
1. IP allowlist (if configured)
2. Telegram secret token (recommended)
3. User authorization checks (AUTHORIZED_USERNAMES, AUTHORIZED_USER_IDS)

---

## Rate Limiting

For small teams (5-20 users):
- No explicit rate limiting implemented
- System designed for ~500-2000 daily messages
- Database pool limited to 5 connections

---

## Monitoring Integration

### Prometheus Metrics (Planned)

Metrics will be exposed at `/metrics` in Prometheus format:

```
# HELP flrts_story16_confidence Story 1.6 router confidence
# TYPE flrts_story16_confidence histogram
flrts_story16_confidence_bucket{le="0.5"} 10
flrts_story16_confidence_bucket{le="0.8"} 45
flrts_story16_confidence_bucket{le="1.0"} 450

# HELP flrts_direct_execution_total Total direct executions
# TYPE flrts_direct_execution_total counter
flrts_direct_execution_total{entity="tasks",operation="create"} 250
```

### Logging

All requests are logged with prefixes:
- `[STORY-1.6-DIRECT]` - Direct execution operations
- `[STORY-1.6-ROUTER]` - Routing decisions
- `[STORY-1.6-PERF]` - Performance warnings
- `[WEBHOOK]` - Webhook processing

---

## Example Integration

### Python Client Example

```python
import requests
import json

class FLRTSClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def check_health(self):
        """Check system health."""
        response = requests.get(f"{self.base_url}/health")
        return response.json()
    
    def send_command(self, command, user_id=123456):
        """Send a command via webhook."""
        payload = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "from": {
                    "id": user_id,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser"
                },
                "chat": {"id": user_id, "type": "private"},
                "date": int(time.time()),
                "text": command
            }
        }
        response = requests.post(
            f"{self.base_url}/webhook",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        return response.status_code == 200

# Usage
client = FLRTSClient()
health = client.check_health()
print(f"System status: {health['status']}")

# Test direct execution
success = client.send_command("/newtask Check oil levels")
print(f"Command sent: {success}")
```

### Bash Monitoring Script

```bash
#!/bin/bash
# Health check monitoring script

HEALTH_URL="http://localhost:8000/health"

while true; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)
    
    if [ "$STATUS" -eq 200 ]; then
        echo "✅ System healthy"
    else
        echo "🚨 System unhealthy (HTTP $STATUS)"
        # Send alert
    fi
    
    sleep 60
done
```

---

## Version History

- **v1.0.0** - Initial release with Story 1.6 Direct Execution
- Health endpoints
- Webhook processing
- Basic metrics

---

## Support

For issues or questions:
1. Check application logs: `tail -f app.log`
2. Monitor Story 1.6 operations: `grep "STORY-1.6" app.log`
3. Review health endpoint: `curl http://localhost:8000/health`

---

*Last Updated: August 2025*