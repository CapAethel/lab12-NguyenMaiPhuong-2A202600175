"""
Rate Limiting Module
Implements sliding window rate limiting using Redis for distributed systems.
"""
import time
import logging
import redis
from typing import Optional
from fastapi import HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Sliding window rate limiter using Redis.
    Tracks requests in the last window_duration seconds.
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        window_duration: int = 60,  # seconds
        max_requests: int = 10
    ):
        self.redis = redis_client
        self.window_duration = window_duration
        self.max_requests = max_requests

        # Fallback to in-memory if no Redis
        if not self.redis:
            logger.warning("No Redis client provided, using in-memory rate limiting")
            self._memory_store = {}

    def _get_memory_count(self, key: str) -> int:
        """Get request count from memory (fallback)."""
        now = time.time()
        requests = self._memory_store.get(key, [])

        # Remove expired requests
        requests = [req_time for req_time in requests if now - req_time < self.window_duration]

        if not requests:
            del self._memory_store[key]
            return 0

        self._memory_store[key] = requests
        return len(requests)

    def _add_memory_request(self, key: str) -> bool:
        """Add request to memory store."""
        now = time.time()
        requests = self._memory_store.get(key, [])

        # Clean expired requests
        requests = [req_time for req_time in requests if now - req_time < self.window_duration]

        if len(requests) >= self.max_requests:
            return False

        requests.append(now)
        self._memory_store[key] = requests
        return True

    def is_allowed(self, key: str, max_requests: Optional[int] = None) -> bool:
        """
        Check if request is allowed for the given key.
        Returns True if allowed, False if rate limited.
        """
        limit = max_requests or self.max_requests

        if self.redis:
            return self._check_redis(key, limit)
        else:
            return self._get_memory_count(key) < limit

    def record_request(self, key: str) -> bool:
        """
        Record a request for the given key.
        Returns True if request was recorded, False if rate limited.
        """
        if self.redis:
            return self._record_redis(key)
        else:
            return self._add_memory_request(key)

    def check_and_record(self, key: str, max_requests: Optional[int] = None) -> bool:
        """
        Check if allowed and record the request if so.
        Returns True if request was allowed and recorded, False if rate limited.
        """
        if not self.is_allowed(key, max_requests):
            return False

        return self.record_request(key)

    def _check_redis(self, key: str, limit: int) -> bool:
        """Check rate limit using Redis."""
        try:
            now = time.time()
            window_key = f"ratelimit:{key}"

            # Remove requests outside the window
            self.redis.zremrangebyscore(window_key, 0, now - self.window_duration)

            # Count remaining requests
            count = self.redis.zcard(window_key)

            return count < limit

        except redis.RedisError as e:
            logger.error(f"Redis error in rate limit check: {e}")
            # Fallback to allow on Redis error
            return True

    def _record_redis(self, key: str) -> bool:
        """Record request in Redis."""
        try:
            now = time.time()
            window_key = f"ratelimit:{key}"

            # Add current request timestamp
            self.redis.zadd(window_key, {str(now): now})

            # Set expiry on the sorted set (window + buffer)
            self.redis.expire(window_key, self.window_duration + 10)

            return True

        except redis.RedisError as e:
            logger.error(f"Redis error in rate limit record: {e}")
            # Fallback to allow on Redis error
            return True

    def get_remaining_requests(self, key: str, max_requests: Optional[int] = None) -> int:
        """Get remaining requests allowed in current window."""
        limit = max_requests or self.max_requests

        if self.redis:
            try:
                now = time.time()
                window_key = f"ratelimit:{key}"
                self.redis.zremrangebyscore(window_key, 0, now - self.window_duration)
                count = self.redis.zcard(window_key)
                return max(0, limit - count)
            except redis.RedisError:
                return limit  # Allow all on error
        else:
            count = self._get_memory_count(key)
            return max(0, limit - count)

    def get_reset_time(self, key: str) -> float:
        """Get time until rate limit resets (seconds)."""
        if self.redis:
            try:
                window_key = f"ratelimit:{key}"
                # Get the oldest timestamp in the window
                oldest = self.redis.zrange(window_key, 0, 0, withscores=True)
                if oldest:
                    return max(0, self.window_duration - (time.time() - oldest[0][1]))
            except redis.RedisError:
                pass

        return self.window_duration


# Global rate limiter instance
_rate_limiter = None

def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _rate_limiter

    if _rate_limiter is None:
        redis_client = None
        if settings.redis_url:
            try:
                redis_client = redis.from_url(settings.redis_url)
                # Test connection
                redis_client.ping()
                logger.info("Connected to Redis for rate limiting")
            except redis.RedisError as e:
                logger.warning(f"Failed to connect to Redis: {e}")

        _rate_limiter = RateLimiter(
            redis_client=redis_client,
            window_duration=60,  # 1 minute window
            max_requests=settings.rate_limit_per_minute
        )

    return _rate_limiter


def check_rate_limit(request: Request, user_id: str) -> None:
    """
    Check and record rate limit for a request.
    Raises HTTPException if rate limited.
    """
    limiter = get_rate_limiter()

    # Use user_id as the rate limit key
    key = f"user:{user_id}"

    if not limiter.check_and_record(key):
        reset_time = limiter.get_reset_time(key)
        raise HTTPException(
            status_code=429,
            detail=".1f",
            headers={
                "Retry-After": str(int(reset_time)),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + reset_time))
            }
        )


def get_rate_limit_info(user_id: str) -> dict:
    """Get current rate limit status for a user."""
    limiter = get_rate_limiter()
    key = f"user:{user_id}"

    return {
        "remaining": limiter.get_remaining_requests(key),
        "reset_in_seconds": limiter.get_reset_time(key),
        "limit": settings.rate_limit_per_minute
    }