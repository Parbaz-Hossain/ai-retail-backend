import time
import logging
from typing import Dict, Optional
from fastapi import HTTPException, status, Request
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter for API endpoints"""
    
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
    
    async def check_rate_limit(self, key: str) -> bool:
        """Check if rate limit is exceeded"""
        try:
            current_time = int(time.time())
            window_start = current_time - self.window_seconds
            
            # Get current count from Redis
            pipe = redis_client.redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(current_time): current_time})
            pipe.expire(key, self.window_seconds)
            
            results = await pipe.execute()
            request_count = results[1]
            
            return request_count < self.max_attempts
            
        except Exception as e:
            logger.error(f"Rate limit check error: {str(e)}")
            return True  # Allow on error
    
    async def is_rate_limited(self, request: Request, identifier: str = None) -> bool:
        """Check if request should be rate limited"""
        if not identifier:
            identifier = request.client.host if request.client else "unknown"
        
        key = f"rate_limit:{request.url.path}:{identifier}"
        return not await self.check_rate_limit(key)

# Rate limiters for different endpoints
login_rate_limiter = RateLimiter(max_attempts=5, window_seconds=300)  # 5 attempts per 5 minutes
general_rate_limiter = RateLimiter(max_attempts=100, window_seconds=60)  # 100 requests per minute

async def check_login_rate_limit(request: Request):
    """Check login rate limit"""
    identifier = request.client.host if request.client else "unknown"
    
    if await login_rate_limiter.is_rate_limited(request, identifier):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )

async def check_general_rate_limit(request: Request):
    """Check general API rate limit"""
    identifier = request.client.host if request.client else "unknown"
    
    if await general_rate_limiter.is_rate_limited(request, identifier):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )