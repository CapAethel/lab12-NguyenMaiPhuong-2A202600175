"""
Cost Guard Module
Tracks and enforces spending limits to prevent budget overruns.
Uses Redis for persistent storage across restarts and scaling.
"""
import time
import logging
import redis
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)


class CostGuard:
    """
    Cost guard that tracks spending and enforces budget limits.
    Uses Redis for persistence and distributed coordination.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None, monthly_budget: float = 10.0):
        self.redis = redis_client
        self.monthly_budget = monthly_budget

        # Fallback to in-memory if no Redis
        if not self.redis:
            logger.warning("No Redis client provided, using in-memory cost tracking")
            self._memory_spending = {}

    def _get_month_key(self, user_id: str) -> str:
        """Get Redis key for user's monthly spending."""
        now = datetime.now()
        return f"cost:{user_id}:{now.year}:{now.month}"

    def _get_memory_key(self, user_id: str) -> str:
        """Get memory key for user's monthly spending."""
        now = datetime.now()
        return f"{user_id}:{now.year}:{now.month}"

    def get_current_spending(self, user_id: str) -> float:
        """Get current month's spending for a user."""
        if self.redis:
            try:
                key = self._get_month_key(user_id)
                spending = self.redis.get(key)
                return float(spending) if spending else 0.0
            except redis.RedisError as e:
                logger.error(f"Redis error getting spending: {e}")
                return 0.0
        else:
            key = self._get_memory_key(user_id)
            return self._memory_spending.get(key, 0.0)

    def add_cost(self, user_id: str, cost_usd: float) -> float:
        """Add cost to user's spending. Returns new total."""
        if self.redis:
            try:
                key = self._get_month_key(user_id)
                # Use Redis atomic increment
                new_total = self.redis.incrbyfloat(key, cost_usd)
                # Set expiry (32 days to cover longest month + buffer)
                self.redis.expire(key, 32 * 24 * 3600)
                return new_total
            except redis.RedisError as e:
                logger.error(f"Redis error adding cost: {e}")
                return 0.0
        else:
            key = self._get_memory_key(user_id)
            current = self._memory_spending.get(key, 0.0)
            new_total = current + cost_usd
            self._memory_spending[key] = new_total
            return new_total

    def check_budget(self, user_id: str, additional_cost: float = 0.0) -> Dict[str, Any]:
        """
        Check if user is within budget.
        Returns dict with budget status and details.
        """
        current_spending = self.get_current_spending(user_id)
        projected_spending = current_spending + additional_cost

        budget_remaining = self.monthly_budget - current_spending
        can_afford = projected_spending <= self.monthly_budget

        return {
            "current_spending": round(current_spending, 4),
            "budget_limit": self.monthly_budget,
            "budget_remaining": round(max(0, budget_remaining), 4),
            "budget_used_percent": round((current_spending / self.monthly_budget) * 100, 1),
            "can_afford_additional": round(additional_cost, 4) if can_afford else 0.0,
            "within_budget": can_afford
        }

    def enforce_budget(self, user_id: str, cost_usd: float) -> None:
        """
        Check budget and add cost if within limits.
        Raises HTTPException if budget would be exceeded.
        """
        budget_info = self.check_budget(user_id, cost_usd)

        if not budget_info["within_budget"]:
            raise HTTPException(
                status_code=402,  # Payment Required
                detail=".4f",
                headers={
                    "X-Budget-Limit": str(self.monthly_budget),
                    "X-Current-Spending": str(budget_info["current_spending"]),
                    "X-Budget-Remaining": str(budget_info["budget_remaining"])
                }
            )

        # Add the cost
        new_total = self.add_cost(user_id, cost_usd)

        logger.info(f"Cost recorded for user {user_id}: +${cost_usd:.4f}, total: ${new_total:.4f}")

    def reset_budget(self, user_id: str, year: Optional[int] = None, month: Optional[int] = None) -> bool:
        """Manually reset budget for a user (admin function)."""
        if year is None or month is None:
            now = datetime.now()
            year = now.year
            month = now.month

        if self.redis:
            try:
                key = f"cost:{user_id}:{year}:{month}"
                self.redis.delete(key)
                return True
            except redis.RedisError as e:
                logger.error(f"Redis error resetting budget: {e}")
                return False
        else:
            key = f"{user_id}:{year}:{month}"
            self._memory_spending.pop(key, None)
            return True

    def get_budget_report(self, user_id: str) -> Dict[str, Any]:
        """Get detailed budget report for a user."""
        budget_info = self.check_budget(user_id)

        # Get spending history for last 3 months
        history = []
        now = datetime.now()

        for months_back in range(3):
            check_date = now.replace(month=now.month - months_back, year=now.year)
            if check_date.month <= 0:
                check_date = check_date.replace(year=check_date.year - 1, month=check_date.month + 12)

            if self.redis:
                try:
                    key = f"cost:{user_id}:{check_date.year}:{check_date.month}"
                    spending = self.redis.get(key)
                    spending = float(spending) if spending else 0.0
                except redis.RedisError:
                    spending = 0.0
            else:
                key = f"{user_id}:{check_date.year}:{check_date.month}"
                spending = self._memory_spending.get(key, 0.0)

            history.append({
                "year": check_date.year,
                "month": check_date.month,
                "spending": round(spending, 4)
            })

        return {
            **budget_info,
            "spending_history": history
        }


# Global cost guard instance
_cost_guard = None

def get_cost_guard() -> CostGuard:
    """Get or create global cost guard instance."""
    global _cost_guard

    if _cost_guard is None:
        redis_client = None
        if settings.redis_url:
            try:
                redis_client = redis.from_url(settings.redis_url)
                # Test connection
                redis_client.ping()
                logger.info("Connected to Redis for cost tracking")
            except redis.RedisError as e:
                logger.warning(f"Failed to connect to Redis: {e}")

        _cost_guard = CostGuard(
            redis_client=redis_client,
            monthly_budget=settings.daily_budget_usd * 30  # Convert daily to monthly estimate
        )

    return _cost_guard


def check_and_record_cost(user_id: str, cost_usd: float) -> None:
    """
    Check budget and record cost.
    Raises HTTPException if budget exceeded.
    """
    guard = get_cost_guard()
    guard.enforce_budget(user_id, cost_usd)


def estimate_request_cost(question: str, estimated_response_length: int = 200) -> float:
    """
    Estimate cost of a request based on token counts.
    Rough estimation: 1 token ≈ 4 characters, GPT-4o-mini pricing.
    """
    # Rough token estimation
    input_tokens = len(question) / 4  # ~4 chars per token
    output_tokens = estimated_response_length / 4

    # GPT-4o-mini pricing (per 1M tokens)
    input_cost = (input_tokens / 1000000) * 0.15
    output_cost = (output_tokens / 1000000) * 0.60

    return input_cost + output_cost


def get_budget_status(user_id: str) -> Dict[str, Any]:
    """Get current budget status for a user."""
    guard = get_cost_guard()
    return guard.get_budget_report(user_id)