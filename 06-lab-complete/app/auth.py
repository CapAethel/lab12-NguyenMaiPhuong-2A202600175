"""
JWT Authentication Module
Provides JWT token generation and validation for user authentication.
"""
import time
import jwt
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


class UserCredentials(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: str
    role: str


class TokenPayload(BaseModel):
    sub: str  # subject (username)
    role: str
    exp: int
    iat: int


# Demo users (in production, use proper user database)
DEMO_USERS = {
    "student": {
        "password": "demo123",
        "role": "user",
        "rate_limit": 10,  # requests per minute
    },
    "teacher": {
        "password": "teach456",
        "role": "admin",
        "rate_limit": 100,  # requests per minute
    },
    "admin": {
        "password": "secret",
        "role": "admin",
        "rate_limit": 1000,  # requests per minute
    }
}


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate user credentials.
    Returns user info dict if valid, None otherwise.
    """
    user = DEMO_USERS.get(username)
    if user and user["password"] == password:
        return {
            "username": username,
            "role": user["role"],
            "rate_limit": user["rate_limit"]
        }
    return None


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=30)  # Default 30 min

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret,
        algorithm="HS256"
    )

    return encoded_jwt


def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Dict[str, Any]:
    """
    Verify JWT token and return user info.
    Raises HTTPException if token is invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"]
        )

        username: str = payload.get("sub")
        role: str = payload.get("role")

        if username is None or role is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if token is expired
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=401,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {
            "username": username,
            "role": role,
            "token_payload": payload
        }

    except jwt.PyJWTError as e:
        logger.warning(f"JWT validation error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(user_info: Dict[str, Any] = Depends(verify_token)) -> Dict[str, Any]:
    """
    Dependency to get current authenticated user.
    """
    return user_info


def require_role(required_role: str):
    """
    Create a dependency that requires a specific role.
    """
    def role_checker(user_info: Dict[str, Any] = Depends(verify_token)) -> Dict[str, Any]:
        if user_info["role"] != required_role:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required role: {required_role}",
            )
        return user_info

    return role_checker