import redis.asyncio as redis
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self.redis = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self.redis.ping()
            logger.info("✅ Redis connected successfully")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {str(e)}")
            raise
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
            logger.info("Redis disconnected")
    
    async def get(self, key: str):
        """Get value by key"""
        if not self.redis:
            await self.connect()
        return await self.redis.get(key)
    
    async def set(self, key: str, value: str, expire: int = None):
        """Set key-value pair"""
        if not self.redis:
            await self.connect()
        return await self.redis.set(key, value, ex=expire)
    
    async def delete(self, key: str):
        """Delete key"""
        if not self.redis:
            await self.connect()
        return await self.redis.delete(key)
    
    async def lpush(self, key: str, value: str):
        """Left push to list"""
        if not self.redis:
            await self.connect()
        return await self.redis.lpush(key, value)
    
    async def lrange(self, key: str, start: int, end: int):
        """Get range from list"""
        if not self.redis:
            await self.connect()
        return await self.redis.lrange(key, start, end)
    
    async def ltrim(self, key: str, start: int, end: int):
        """Trim list"""
        if not self.redis:
            await self.connect()
        return await self.redis.ltrim(key, start, end)
    
    async def expire(self, key: str, seconds: int):
        """Set expiration"""
        if not self.redis:
            await self.connect()
        return await self.redis.expire(key, seconds)

# Global Redis client instance
redis_client = RedisClient()