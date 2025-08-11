import logging
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.rate_limiter import general_rate_limiter

logger = logging.getLogger(__name__)

class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""
    
    # Routes that don't require rate limiting
    EXEMPT_ROUTES = [
        "/",
        "/health",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json"
    ]
    
    async def dispatch(self, request: Request, call_next):
        # Check if route is exempt
        if any(request.url.path.startswith(route) for route in self.EXEMPT_ROUTES):
            return await call_next(request)
        
        # Check rate limit
        if await general_rate_limiter.is_rate_limited(request):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down.",
                headers={"Retry-After": "60"}
            )
        
        return await call_next(request)
