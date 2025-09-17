import json
import time
import logging
from typing import Dict, List
from collections import defaultdict, deque
from fastapi import HTTPException, Path, status, Request
from threading import Lock
import asyncio

logger = logging.getLogger(__name__)

class InMemoryRateLimiter:
    """In-memory rate limiter for API endpoints"""
    
    def __init__(self, max_attempts: int = 100, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        # Use defaultdict with deque to store timestamps for each key
        self._requests: Dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Cleanup every 60 seconds
    
    async def _cleanup_old_entries(self):
        """Remove old entries to prevent memory leaks"""
        current_time = time.time()
        
        # Only cleanup if enough time has passed
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
            
        cutoff_time = current_time - self.window_seconds
        keys_to_remove = []
        
        for key, timestamps in self._requests.items():
            # Remove old timestamps
            while timestamps and timestamps[0] <= cutoff_time:
                timestamps.popleft()
            
            # If no recent requests, mark key for removal
            if not timestamps:
                keys_to_remove.append(key)
        
        # Remove empty keys
        for key in keys_to_remove:
            del self._requests[key]
        
        self._last_cleanup = current_time
        
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} rate limit entries")
    
    async def check_rate_limit(self, key: str) -> bool:
        """Check if rate limit is exceeded"""
        try:
            async with self._lock:
                current_time = time.time()
                cutoff_time = current_time - self.window_seconds
                
                # Get or create deque for this key
                timestamps = self._requests[key]
                
                # Remove old timestamps
                while timestamps and timestamps[0] <= cutoff_time:
                    timestamps.popleft()
                
                # Check if limit exceeded
                if len(timestamps) >= self.max_attempts:
                    logger.warning(f"Rate limit exceeded for key: {key}")
                    return False
                
                # Add current timestamp
                timestamps.append(current_time)
                
                # Periodic cleanup
                await self._cleanup_old_entries()
                
                return True
                
        except Exception as e:
            logger.error(f"Rate limit check error: {str(e)}")
            return True  # Allow on error
    
    async def is_rate_limited(self, request: Request, identifier: str = None) -> bool:
        """Check if request should be rate limited"""
        if not identifier:
            identifier = request.client.host if request.client else "unknown"
        
        key = f"rate_limit:{request.url.path}:{identifier}"
        return not await self.check_rate_limit(key)
    
    async def get_rate_limit_info(self, key: str) -> dict:
        """Get current rate limit info for debugging"""
        async with self._lock:
            current_time = time.time()
            cutoff_time = current_time - self.window_seconds
            
            timestamps = self._requests[key]
            
            # Remove old timestamps for accurate count
            while timestamps and timestamps[0] <= cutoff_time:
                timestamps.popleft()
            
            remaining_attempts = max(0, self.max_attempts - len(timestamps))
            reset_time = timestamps[0] + self.window_seconds if timestamps else current_time
            
            return {
                "current_requests": len(timestamps),
                "max_attempts": self.max_attempts,
                "remaining_attempts": remaining_attempts,
                "window_seconds": self.window_seconds,
                "reset_time": reset_time
            }

# Updated rate limiter instances
login_rate_limiter = InMemoryRateLimiter(max_attempts=100, window_seconds=300)  # 5 attempts per 5 minutes
general_rate_limiter = InMemoryRateLimiter(max_attempts=100, window_seconds=60)  # 100 requests per minute

async def check_login_rate_limit(request: Request):
    """Check login rate limit"""
    identifier = request.client.host if request.client else "unknown"
    
    if await login_rate_limiter.is_rate_limited(request, identifier):
        # Get rate limit info for better error messages
        key = f"rate_limit:{request.url.path}:{identifier}"
        rate_info = await login_rate_limiter.get_rate_limit_info(key)
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Please try again in {int(rate_info['reset_time'] - time.time())} seconds."
        )

async def check_general_rate_limit(request: Request):
    """Check general API rate limit"""
    identifier = request.client.host if request.client else "unknown"
    
    if await general_rate_limiter.is_rate_limited(request, identifier):
        key = f"rate_limit:{request.url.path}:{identifier}"
        rate_info = await general_rate_limiter.get_rate_limit_info(key)
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. {rate_info['remaining_attempts']} requests remaining."
        )


# Alternative sliding window implementation using a different approach
class SlidingWindowRateLimiter:
    """Sliding window rate limiter with more precise control"""
    
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        # Store list of timestamps for each key
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def check_rate_limit(self, key: str) -> bool:
        """Check if rate limit is exceeded using sliding window"""
        try:
            async with self._lock:
                current_time = time.time()
                cutoff_time = current_time - self.window_seconds
                
                # Get existing requests for this key
                requests = self._requests[key]
                
                # Filter out old requests
                self._requests[key] = [req_time for req_time in requests if req_time > cutoff_time]
                
                # Check if limit exceeded
                if len(self._requests[key]) >= self.max_attempts:
                    return False
                
                # Add current request
                self._requests[key].append(current_time)
                return True
                
        except Exception as e:
            logger.error(f"Rate limit check error: {str(e)}")
            return True

# Optional: File-based persistent rate limiter (for single-instance deployments)
class FileBasedRateLimiter:
    """File-based rate limiter that persists across restarts"""
    
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300, storage_file: str = "rate_limits.json"):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.storage_file = Path(storage_file)
        self._lock = asyncio.Lock()
        self._requests: Dict[str, List[float]] = {}
        self._load_from_file()
    
    def _load_from_file(self):
        """Load rate limit data from file"""
        try:
            if self.storage_file.exists():
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    self._requests = {k: v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error loading rate limit data: {e}")
            self._requests = {}
    
    async def _save_to_file(self):
        """Save rate limit data to file"""
        try:
            with open(self.storage_file, 'w') as f:
                # Only save recent data to prevent file from growing too large
                current_time = time.time()
                cutoff_time = current_time - self.window_seconds
                
                filtered_data = {}
                for key, timestamps in self._requests.items():
                    recent_timestamps = [t for t in timestamps if t > cutoff_time]
                    if recent_timestamps:
                        filtered_data[key] = recent_timestamps
                
                json.dump(filtered_data, f)
        except Exception as e:
            logger.error(f"Error saving rate limit data: {e}")
    
    async def check_rate_limit(self, key: str) -> bool:
        """Check if rate limit is exceeded"""
        try:
            async with self._lock:
                current_time = time.time()
                cutoff_time = current_time - self.window_seconds
                
                # Get existing requests
                requests = self._requests.get(key, [])
                
                # Filter out old requests
                recent_requests = [req_time for req_time in requests if req_time > cutoff_time]
                
                # Check limit
                if len(recent_requests) >= self.max_attempts:
                    return False
                
                # Add current request
                recent_requests.append(current_time)
                self._requests[key] = recent_requests
                
                # Periodically save to file
                if int(current_time) % 10 == 0:  # Save every 10 seconds
                    await self._save_to_file()
                
                return True
                
        except Exception as e:
            logger.error(f"Rate limit check error: {str(e)}")
            return True