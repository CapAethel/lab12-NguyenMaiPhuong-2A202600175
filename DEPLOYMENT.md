# Deployment Information

## Public URL
https://feisty-serenity-production-b58d.up.railway.app

## Platform
Railway

## Test Commands

### Health Check
```bash
curl https://feisty-serenity-production-b58d.up.railway.app/health
# Expected: {"status": "ok", "platform": "Railway"}
```

### API Test (with authentication)
```bash
curl -X POST https://feisty-serenity-production-b58d.up.railway.app/ask \
  -H "X-API-Key: prod-key-secure-2026" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: 200 OK with JSON response
```

### JWT Authentication Test
```bash
# 1. Get token
curl https://feisty-serenity-production-b58d.up.railway.app/auth/token \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"username": "student", "password": "demo123"}'

# 2. Use token
TOKEN="<token_from_step_1>"
curl -X POST https://feisty-serenity-production-b58d.up.railway.app/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain JWT"}'
```

## Environment Variables Set
- ENVIRONMENT=production
- AGENT_API_KEY=prod-key-secure-2026
- JWT_SECRET=super-secure-jwt-secret-2026
- PORT (auto-set by Railway)

## Screenshots
- [Railway Dashboard](screenshots/railway-dashboard.txt)
- [Health Check Response](screenshots/health-check.txt)
- [API Test Response](screenshots/api-test.txt)

## Deployment Details
- **Build Method**: Docker (multi-stage build)
- **Runtime**: Python 3.11 + FastAPI + Uvicorn
- **Workers**: 2 (configured in railway.toml)
- **Health Check**: /health endpoint with 30s timeout
- **Restart Policy**: ON_FAILURE with 3 max retries

## Architecture
```
Client → Railway CDN → Railway Edge → Docker Container (FastAPI)
                                      ↓
                                 Redis (session storage)
```

## Monitoring
- Railway provides built-in metrics and logs
- Health checks run every deployment
- Automatic scaling based on traffic