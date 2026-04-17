#  Delivery Checklist — Day 12 Lab Submission

> **Student Name:** Nguyễn Mai Phương
> **Student ID:** 2A202600175
> **Date:** 17/04/2026

---

# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

Dưới đây là ít nhất 5 anti-patterns được xác định trong `app.py` (dựa trên mã nguồn và các gợi ý được cung cấp):

1. Khóa API và bí mật được hardcode: `OPENAI_API_KEY` và `DATABASE_URL` được hardcode trực tiếp trong mã. Điều này nguy hiểm vì nếu mã được đẩy lên kho công khai (như GitHub), các bí mật sẽ bị lộ. Bí mật nên được tải từ biến môi trường hoặc hệ thống cấu hình bảo mật.

2. Không có quản lý cấu hình: Các giá trị cấu hình như `DEBUG`, `MAX_TOKENS` và URL cơ sở dữ liệu được hardcode. Không có cách tập trung để quản lý cài đặt cho các môi trường khác nhau (dev, staging, production). Điều này vi phạm nguyên tắc ứng dụng 12 yếu tố về lưu trữ cấu hình trong môi trường.

3. Ghi log không đúng cách: Mã sử dụng câu lệnh `print()` để ghi log, điều này không phù hợp cho production. Nó cũng ghi log thông tin nhạy cảm như khóa API. Ghi log đúng cách nên sử dụng logger có cấu trúc (ví dụ: module `logging` của Python) với các mức độ phù hợp và không tiết lộ bí mật.

4. Không có endpoint kiểm tra sức khỏe: Không có endpoint `/health` hoặc `/ready` để kiểm tra xem ứng dụng có đang chạy và sẵn sàng xử lý yêu cầu hay không. Các nền tảng như Railway hoặc Render sử dụng những endpoint này để giám sát ứng dụng và khởi động lại nếu nó crash.

5. Port và host cố định: Ứng dụng được hardcode để chạy trên `host="localhost"` và `port=8010`. Trong môi trường production (ví dụ: Railway, Render), port được inject qua biến môi trường `PORT`, và host nên là `0.0.0.0` để chấp nhận kết nối bên ngoài. Điều này làm cho ứng dụng không linh hoạt khi triển khai.


### Exercise 1.3: Comparison table
| Feature | Basic | Advanced | Tại sao quan trọng? |
|---------|-------|----------|---------------------|
| Config | Hardcode | Env vars | Config từ biến môi trường cho phép deploy linh hoạt giữa dev và prod, tránh hardcode secrets và thông tin môi trường. |
| Health check | Không có | Có | Health check giúp nền tảng giám sát ứng dụng và tự động khởi động lại khi service không còn đáp ứng. |
| Logging | print() | JSON | JSON log chuẩn giúp dễ thu thập, phân tích và tìm lỗi trong production, đồng thời tách log theo mức độ. |
| Shutdown | Đột ngột | Graceful | Graceful shutdown cho phép hoàn thành request hiện tại và giải phóng tài nguyên trước khi dừng, tránh mất dữ liệu và request bị gián đoạn. |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. Base image: là lớp đầu tiên, nền tảng cơ bản nhất của một Docker image, định nghĩa hệ điều hành hoặc môi trường runtime (như Node.js, Python, Alpine) mà ứng dụng sẽ chạy trên đó
2. Working directory: thư mục làm việc bên trong container nơi code và dependencies sẽ được đặt
3. Tại sao COPY requirements.txt trước? Để tận dụng Docker layer caching. Khi requirements.txt không đổi, Docker sẽ sử dụng cached layer cho pip install, tiết kiệm thời gian build
4. CMD vs ENTRYPOINT khác nhau thế nào? CMD định nghĩa command mặc định có thể bị override khi docker run, ENTRYPOINT định nghĩa executable chính và arguments không thể bị override hoàn toàn

### Exercise 2.4: Docker Compose stack
Docker Compose stack bao gồm 4 services chính:

1. agent (2 replicas): FastAPI AI agent, sử dụng multi-stage build (chỉ runtime stage), kết nối với Redis và Qdrant
2. redis: Cache database cho session và rate limiting, sử dụng Redis 7 Alpine với memory limit 256MB
3. qdrant: Vector database cho RAG (Retrieval-Augmented Generation), lưu trữ embeddings
4. nginx : Reverse proxy và load balancer, expose port 80/443 ra ngoài

**Communication flow:**
- Client → Nginx (port 80/443) → Load balance đến agent instances
- Agent → Redis (port 6379) để cache session và rate limiting data
- Agent → Qdrant (port 6333) để vector search và retrieval
- Tất cả services trong internal network, chỉ Nginx expose ra ngoài

**Architecture diagram:**
```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP/HTTPS
       ▼
┌─────────────────┐
│  Nginx (LB)     │ ← Load balancer, SSL termination
│  port 80/443    │
└──────┬──────────┘
       │
       ├─────────┬─────────┐
       ▼         ▼         ▼
   ┌──────┐  ┌──────┐  ┌──────┐
   │Agent1│  │Agent2│  │Agent3│ ← FastAPI instances
   └───┬──┘  └───┬──┘  └───┬──┘
       │         │         │
       └─────────┴─────────┘
                 │
       ┌─────────┴─────────┐
       ▼                   ▼
┌──────────┐        ┌──────────┐
│  Redis   │        │  Qdrant  │
│ (Cache)  │        │ (Vector) │
└──────────┘        └──────────┘
```

### Exercise 3.1: Railway deployment
Railway deployment đã được thực hiện với các bước sau:

1. ✅ Install Railway CLI: `npm i -g @railway/cli`
2. ✅ Login: `railway login`
3. ✅ Initialize project: `railway init` → tạo project "day12-agent-deployment"
4. ✅ Link service: `railway service` → link service thành công
5. ✅ Deploy: `railway up` → deploy thành công
6. ✅ Get public URL: https://proud-kindness-production-9e63.up.railway.app

**Deployment successful!** App đang chạy và accessible tại public URL.

### Exercise 3.2: Render deployment comparison
**So sánh render.yaml vs railway.toml:**

| Aspect | render.yaml | railway.toml |
|--------|-------------|--------------|
| **Format** | YAML declarative | TOML simple |
| **Infrastructure** | Định nghĩa đầy đủ services (web + redis) | Chỉ config cho 1 service |
| **Build** | Chỉ định `buildCommand` và `startCommand` | Dùng builder (NIXPACKS/Dockerfile) + `startCommand` |
| **Environment** | `envVars` array với `sync/generateValue` | Variables set qua CLI/dashboard riêng |
| **Health check** | `healthCheckPath` | `healthcheckPath` + timeout |
| **Scaling** | Plan-based (free/starter/pro) | Dynamic scaling |
| **Auto-deploy** | `autoDeploy: true` | Không config trong file |
| **Persistence** | `disk` config cho storage | Không có trong file |

**Khác biệt chính:**
- Render dùng YAML để define toàn bộ infrastructure (IaC), Railway dùng TOML chỉ cho config
- Render support multiple services trong 1 file, Railway cần CLI commands
- Render có auto-deploy flag, Railway phụ thuộc vào git integration
- Render có disk persistence config, Railway không có trong config file
- URL:  https://proud-kindness-production-9e63.up.railway.app
- Screenshot: day12_ha-tang-cloud_va_deployment\03-cloud-deployment\RailwayDeploy.png

## Part 4: API Security

### Exercise 4.1: API Key authentication
Đọc `app.py` trong `04-api-gateway/develop`:

- **API key được check ở đâu?** Trong dependency function `verify_api_key()` (dòng 32-47), sử dụng `APIKeyHeader` từ FastAPI security
- **Điều gì xảy ra nếu sai key?** Raise `HTTPException` với status code 403 và message "Invalid API key."
- **Điều gì xảy ra nếu không có key?** Raise `HTTPException` với status code 401 và message "Missing API key. Include header: X-API-Key: <your-key>"
- **Làm sao rotate key?** Thay đổi giá trị biến môi trường `AGENT_API_KEY`, restart application. Trong production nên dùng secret management service (AWS Secrets Manager, Azure Key Vault, etc.)

**Test results:**
- ✅ Với key đúng: `curl -H "X-API-Key: demo-key-change-in-production" http://localhost:8000/ask?question=hello` → trả về response JSON
- ✅ Không có key: `curl http://localhost:8000/ask?question=hello` → 401 Unauthorized  
- ✅ Key sai: trả về 403 Forbidden

### Exercise 4.2: JWT authentication
Đọc `auth.py` trong `04-api-gateway/production`:

**JWT flow:**
1. Client gửi POST `/auth/token` với `username` và `password`
2. Server authenticate và tạo JWT token chứa `sub` (username), `role`, `iat`, `exp`
3. Client sử dụng token trong header `Authorization: Bearer <token>`
4. Server verify token signature và extract user info

**Demo credentials:**
- `student` / `demo123` (user role, 10 req/min)
- `teacher` / `teach456` (admin role, 100 req/min)

**Test commands:**
```bash
# 1. Get token
curl http://localhost:8000/auth/token -X POST \
  -H "Content-Type: application/json" \
  -d '{"username": "student", "password": "demo123"}'

# 2. Use token
TOKEN="<token_from_step_1>"
curl http://localhost:8000/ask -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain JWT"}'
```

### Exercise 4.3: Rate limiting
Đọc `rate_limiter.py`:

- **Algorithm:** Sliding Window Counter - đếm requests trong cửa sổ thời gian trượt (60 giây)
- **Limit:** 10 requests/minute cho user, 100 requests/minute cho admin
- **Bypass cho admin:** Admin có limit cao hơn (100 vs 10), không có bypass đặc biệt khác

**Test:** Gọi API 20 lần liên tiếp sẽ hit rate limit và nhận 429 status code.

### Exercise 4.4: Cost guard
Đọc `cost_guard.py` và implement logic:

```python
def check_budget(user_id: str, estimated_cost: float) -> bool:
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"
    
    current = float(r.get(key) or 0)
    if current + estimated_cost > 10:  # $10/month limit
        return False
    
    r.incrbyfloat(key, estimated_cost)
    r.expire(key, 32 * 24 * 3600)  # 32 days
    return True
```

**Logic:**
- Mỗi user có budget $10/tháng
- Track spending trong Redis với key `budget:{user_id}:{YYYY-MM}`
- Reset tự động khi qua tháng mới (32 ngày expiry)
- Block request nếu vượt budget (HTTP 402 Payment Required)

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks
Implement 2 endpoints trong `05-scaling-reliability/production/app.py`:

```python
@app.get("/health")
def health():
    redis_ok = False
    if USE_REDIS:
        try:
            _redis.ping()
            redis_ok = True
        except Exception:
            redis_ok = False
    
    status = "ok" if (not USE_REDIS or redis_ok) else "degraded"
    return {
        "status": status,
        "instance_id": INSTANCE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "storage": "redis" if USE_REDIS else "in-memory",
        "redis_connected": redis_ok if USE_REDIS else "N/A",
    }

@app.get("/ready")
def ready():
    if USE_REDIS:
        try:
            _redis.ping()
        except Exception:
            raise HTTPException(503, "Redis not available")
    return {"ready": True, "instance": INSTANCE_ID}
```

**Liveness vs Readiness:**
- `/health` (liveness): Check if process is running, return 200 even if Redis down (degraded status)
- `/ready` (readiness): Check if ready to serve traffic, return 503 if Redis unavailable

### Exercise 5.2: Graceful shutdown
Implement signal handler trong `05-scaling-reliability/production/app.py`:

```python
import signal
import sys

def shutdown_handler(signum, frame):
    """Handle SIGTERM from container orchestrator"""
    logger.info(f"Received {signum}, shutting down gracefully...")
    # Stop accepting new requests (FastAPI handles this)
    # Finish current requests (FastAPI handles this) 
    # Close connections
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
```

**Test:** Gửi request dài, sau đó `kill -TERM <PID>`, request vẫn hoàn thành trước khi shutdown.

### Exercise 5.3: Stateless design
Refactor để stateless bằng Redis session storage:

**Anti-pattern (stateful):**
```python
conversation_history = {}  # ❌ In-memory, không scale

@app.post("/ask")
def ask(user_id: str, question: str):
    history = conversation_history.get(user_id, [])  # ❌ Mất khi restart
```

**Correct (stateless):**
```python
def save_session(session_id: str, data: dict, ttl_seconds: int = 3600):
    serialized = json.dumps(data)
    _redis.setex(f"session:{session_id}", ttl_seconds, serialized)

def load_session(session_id: str) -> dict:
    data = _redis.get(f"session:{session_id}")
    return json.loads(data) if data else {}

@app.post("/chat")
def chat(body: ChatRequest):
    session_id = body.session_id or str(uuid.uuid4())
    append_to_history(session_id, "user", body.question)
    # ... process ...
    append_to_history(session_id, "assistant", answer)
```

**Tại sao quan trọng:** Khi scale ra nhiều instances, mỗi instance có memory riêng. Redis đảm bảo tất cả instances truy cập cùng state.

### Exercise 5.4: Load balancing
Chạy stack với Nginx load balancer:

```bash
docker compose up --scale agent=3
```

**Services:**
- 3 agent instances (FastAPI)
- 1 Redis (session storage)
- 1 Nginx (load balancer + reverse proxy)

**Nginx config (`nginx.conf`):**
```
upstream agent_backend {
    server agent:8000;
    server agent:8001; 
    server agent:8002;
}

server {
    listen 80;
    location / {
        proxy_pass http://agent_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Quan sát:** Requests được phân tán đều giữa 3 instances, nếu 1 instance die thì traffic chuyển sang instances còn lại.

### Exercise 5.5: Test stateless
Script `test_stateless.py`:
1. Tạo session mới
2. Gửi 5 requests liên tiếp với cùng `session_id`
3. Quan sát `served_by` field — mỗi request có thể đến instance khác nhau
4. Kiểm tra history — tất cả messages được preserve dù instances khác nhau

**Kết quả:** ✅ Session history được duy trì qua Redis, chứng minh stateless design hoạt động.

## Part 6: Final Project

### Production-Ready Agent Implementation
Đã implement hoàn chỉnh production-ready AI agent trong `06-lab-complete/` với tất cả concepts từ Day 12:

**✅ Functional Requirements:**
- Agent trả lời câu hỏi qua REST API (`/ask` endpoint)
- Support conversation history với session management
- Structured JSON responses

**✅ Non-functional Requirements:**
- **Dockerized**: Multi-stage build (builder + runtime), slim base image, non-root user
- **Config**: Environment variables only (12-factor compliant)
- **Security**: API key authentication, rate limiting (10 req/min), cost guard ($10/month)
- **Reliability**: Health check (`/health`), readiness check (`/ready`), graceful shutdown (SIGTERM handler)
- **Scalability**: Stateless design với Redis session storage
- **Observability**: Structured JSON logging
- **Deployment**: Config files cho Railway và Render

**🏗 Architecture Implemented:**
```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP/HTTPS
       ▼
┌─────────────────┐
│  Nginx (LB)     │
└──────┬──────────┘
       │
       ├─────────┬─────────┐
       ▼         ▼         ▼
   ┌──────┐  ┌──────┐  ┌──────┐
   │Agent1│  │Agent2│  │Agent3│
   └───┬──┘  └───┬──┘  └───┬──┘
       │         │         │
       └─────────┴─────────┘
                 │
                 ▼
           ┌──────────┐
           │  Redis   │
           └──────────┘
```

**📊 Production Readiness Check Results:**
```
Result: 20/20 checks passed (100%)
🎉 PRODUCTION READY! Deploy nào!
```

**🚀 Deployed URL:** https://feisty-serenity-production-b58d.up.railway.app

**Key Implementation Highlights:**
- **Config Management**: `app/config.py` với Pydantic BaseSettings
- **Authentication**: API key header validation
- **Rate Limiting**: Sliding window algorithm (10 req/min per user)
- **Cost Guard**: Monthly budget tracking ($10/user) với Redis
- **Health Checks**: Liveness (`/health`) và readiness (`/ready`) probes
- **Stateless Design**: Session storage trong Redis, không memory
- **Security Headers**: CORS, XSS protection, content-type options
- **Graceful Shutdown**: SIGTERM handler với proper cleanup
- **Docker**: Multi-stage build, health checks, security best practices

**Deployment Ready:**
- Railway: `railway.toml` config
- Render: `render.yaml` IaC definition
- Docker Compose: Full stack với load balancing

**Testing:**
```bash
cd 06-lab-complete
python check_production_ready.py  # ✅ 100% pass
docker compose up                 # Test full stack locally
```

Project này đáp ứng đầy đủ tất cả requirements và sẵn sàng deploy lên production!

---