"""
AEGIS UNIFIED DATA CORE - Redis Cache & In-Memory Fallback Client
Provides high-performance caching for live observations, telemetry streams,
distributed locks, and rate limiting with automatic in-memory fallback.
"""
import json
import time
from typing import Optional, Any, Dict
import redis.asyncio as aioredis
from backend.app.core.config import settings
from backend.app.utils.logger import logger


class CacheManager:
    _redis: Optional[aioredis.Redis] = None
    _memory_cache: dict = {}
    _memory_expiry: dict = {}
    _is_redis_connected: bool = False
    _last_connect_attempt: float = 0.0
    _connect_cooldown_sec: float = 60.0

    @classmethod
    async def get_redis(cls) -> Optional[aioredis.Redis]:
        if cls._is_redis_connected and cls._redis is not None:
            return cls._redis

        now = time.time()
        if now - cls._last_connect_attempt < cls._connect_cooldown_sec:
            return None

        cls._last_connect_attempt = now
        try:
            client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=0.5
            )
            await client.ping()
            cls._redis = client
            cls._is_redis_connected = True
            logger.info(f"Connected to Redis cache at {settings.REDIS_URL} successfully.")
            return cls._redis
        except Exception as e:
            cls._redis = None
            cls._is_redis_connected = False
            return None

    @classmethod
    async def check_health(cls) -> Dict[str, Any]:
        """Returns health status of caching subsystem."""
        if cls._is_redis_connected and cls._redis is not None:
            return {"status": "HEALTHY", "engine": "Redis", "connected": True}
        return {
            "status": "HEALTHY",
            "engine": "In-Memory Fallback Cache",
            "connected": True,
            "cached_keys": len(cls._memory_cache)
        }

    @classmethod
    async def get(cls, key: str) -> Optional[Any]:
        """Retrieves cached JSON item by key."""
        try:
            r = await cls.get_redis()
            if r:
                val = await r.get(key)
                return json.loads(val) if val else None
        except Exception:
            cls._is_redis_connected = False
            cls._redis = None

        # In-memory fallback
        now = time.time()
        if key in cls._memory_cache:
            if cls._memory_expiry.get(key, 0) > now:
                return cls._memory_cache[key]
            else:
                cls._memory_cache.pop(key, None)
                cls._memory_expiry.pop(key, None)
        return None

    @classmethod
    async def set(cls, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Sets a cached JSON item with TTL."""
        ttl = ttl_seconds or settings.CACHE_DEFAULT_TTL_SEC
        try:
            r = await cls.get_redis()
            if r:
                serialized = json.dumps(value)
                await r.set(key, serialized, ex=ttl)
                return True
        except Exception:
            cls._is_redis_connected = False
            cls._redis = None

        # In-memory fallback
        cls._memory_cache[key] = value
        cls._memory_expiry[key] = time.time() + ttl
        return True

    @classmethod
    async def delete(cls, key: str) -> bool:
        """Deletes a key from cache."""
        try:
            r = await cls.get_redis()
            if r:
                await r.delete(key)
        except Exception:
            cls._is_redis_connected = False
            cls._redis = None

        cls._memory_cache.pop(key, None)
        cls._memory_expiry.pop(key, None)
        return True

    @classmethod
    async def clear_all(cls):
        """Clears local memory cache."""
        cls._memory_cache.clear()
        cls._memory_expiry.clear()
        try:
            r = await cls.get_redis()
            if r:
                await r.flushdb()
        except Exception:
            pass
