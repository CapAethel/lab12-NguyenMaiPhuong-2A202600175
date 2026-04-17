"""
Production AI Agent — Kết hợp tất cả Day 12 concepts

Checklist:
  ✅ Config từ environment (12-factor)
  ✅ Structured JSON logging
  ✅ API Key authentication
  ✅ JWT authentication
  ✅ Rate limiting (Redis)
  ✅ Cost guard (Redis)
  ✅ Input validation (Pydantic)
  ✅ Health check + Readiness probe
  ✅ Graceful shutdown
  ✅ Security headers
  ✅ CORS
  ✅ Error handling
  ✅ Stateless design
"""
import os
import time
import signal
import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, Depends, Request, Response
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings
from app.auth import UserCredentials, TokenResponse, authenticate_user, create_access_token, verify_token, get_current_user
from app.rate_limiter import check_rate_limit, get_rate_limit_info
from app.cost_guard import check_and_record_cost, estimate_request_cost, get_budget_status

# Mock LLM (thay bằng OpenAI/Anthropic khi có API key)
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# ─────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
        )
    return api_key

# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    time.sleep(0.1)  # simulate init
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))

    yield

    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))

# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers.pop("server", None)
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception as e:
        _error_count += 1
        raise

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000,
                          description="Your question for the agent")

class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    timestamp: str
    user_id: str
    tokens_used: int

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "auth_token": "POST /auth/token (get JWT token)",
            "auth_me": "GET /auth/me (current user info)",
            "ask": "POST /ask (requires JWT Bearer token)",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics (requires API key)",
        },
    }


@app.post("/auth/token", response_model=TokenResponse, tags=["Authentication"])
async def login(credentials: UserCredentials):
    """
    Get JWT access token for authenticated users.

    **Demo users:**
    - `student` / `demo123` (user role, 10 req/min)
    - `teacher` / `teach456` (admin role, 100 req/min)
    - `admin` / `secret` (admin role, 1000 req/min)
    """
    user = authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    # Create token with 30 minute expiry
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]}
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=1800,  # 30 minutes
        user=user["username"],
        role=user["role"]
    )


@app.get("/auth/me", tags=["Authentication"])
async def get_current_user_info(user_info: dict = Depends(get_current_user)):
    """Get current authenticated user information."""
    return {
        "user": user_info["username"],
        "role": user_info["role"],
        "rate_limit_info": get_rate_limit_info(user_info["username"]),
        "budget_info": get_budget_status(user_info["username"])
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    user_info: dict = Depends(get_current_user),
):
    """
    Send a question to the AI agent.

    **Authentication:** Include header `Authorization: Bearer <token>`
    """
    user_id = user_info["username"]

    # Rate limit check
    check_rate_limit(request, user_id)

    # Estimate and check cost
    estimated_cost = estimate_request_cost(body.question)
    check_and_record_cost(user_id, estimated_cost)

    logger.info(json.dumps({
        "event": "agent_call",
        "user_id": user_id,
        "q_len": len(body.question),
        "estimated_cost": round(estimated_cost, 6),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    answer = llm_ask(body.question)

    # Record actual cost (mock for now)
    actual_cost = estimate_request_cost(body.question, len(answer))
    check_and_record_cost(user_id, actual_cost - estimated_cost)  # Adjust for difference

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_id=user_id,
        tokens_used=len(body.question.split()) + len(answer.split())
    )


@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe. Platform restarts container if this fails."""
    status = "ok"
    checks = {"llm": "mock" if not settings.openai_api_key else "openai"}
    return {
        "status": status,
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe. Load balancer stops routing here if not ready."""
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    return {"ready": True}


@app.get("/metrics", tags=["Operations"])
def metrics(_key: str = Depends(verify_api_key)):
    """Basic metrics (protected)."""
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "environment": settings.environment,
        "redis_connected": bool(settings.redis_url),
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "monthly_budget_usd": settings.daily_budget_usd * 30,
    }


# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum}))

signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    logger.info(f"API Key: {settings.agent_api_key[:4]}****")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
