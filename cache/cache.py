# ============================================================================
# IIStudio — Redis кэш (с fallback на in-memory)
# ============================================================================

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Optional

from utils.logger import logger

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class InMemoryCache:
    """Простой in-memory кэш (LRU) — fallback если Redis недоступен."""

    def __init__(self, max_size: int = 1000) -> None:
        self._store: Dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)
        self.max_size = max_size

    async def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at and time.time() > expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        if len(self._store) >= self.max_size:
            # Удалить старейший ключ
            oldest = next(iter(self._store))
            del self._store[oldest]
        expires_at = time.time() + ttl if ttl > 0 else 0
        self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def clear(self) -> None:
        self._store.clear()

    async def size(self) -> int:
        return len(self._store)

    async def close(self) -> None:
        pass


class RedisCache:
    """Redis-based кэш с JSON сериализацией."""

    def __init__(self, redis_url: str, default_ttl: int = 3600) -> None:
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._client: Optional[Any] = None

    async def connect(self) -> bool:
        if not REDIS_AVAILABLE:
            logger.warning("redis.asyncio не установлен")
            return False
        try:
            self._client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            await self._client.ping()
            logger.info("Redis подключён: {}", self.redis_url.split("@")[-1])
            return True
        except Exception as e:
            logger.warning("Redis недоступен: {} — используем in-memory кэш", e)
            self._client = None
            return False

    async def get(self, key: str) -> Optional[Any]:
        if not self._client:
            return None
        try:
            raw = await self._client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.warning("Redis GET ошибка: {}", e)
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if not self._client:
            return
        try:
            ttl = ttl if ttl is not None else self.default_ttl
            serialized = json.dumps(value, ensure_ascii=False)
            if ttl > 0:
                await self._client.setex(key, ttl, serialized)
            else:
                await self._client.set(key, serialized)
        except Exception as e:
            logger.warning("Redis SET ошибка: {}", e)

    async def delete(self, key: str) -> None:
        if not self._client:
            return
        try:
            await self._client.delete(key)
        except Exception as e:
            logger.warning("Redis DELETE ошибка: {}", e)

    async def exists(self, key: str) -> bool:
        if not self._client:
            return False
        try:
            return bool(await self._client.exists(key))
        except Exception:
            return False

    async def clear(self, pattern: str = "iistudio:*") -> int:
        """Очистить ключи по паттерну."""
        if not self._client:
            return 0
        try:
            keys = await self._client.keys(pattern)
            if keys:
                return await self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning("Redis CLEAR ошибка: {}", e)
            return 0

    async def size(self) -> int:
        if not self._client:
            return 0
        try:
            return await self._client.dbsize()
        except Exception:
            return 0

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


class CacheManager:
    """Единая точка доступа к кэшу (Redis или in-memory fallback)."""

    KEY_PREFIX = "iistudio:"

    def __init__(self, redis_url: str, default_ttl: int = 3600, max_memory_size: int = 10000) -> None:
        self.default_ttl = default_ttl
        self._redis = RedisCache(redis_url, default_ttl)
        self._memory = InMemoryCache(max_memory_size)
        self._use_redis = False

    async def start(self) -> None:
        self._use_redis = await self._redis.connect()
        if not self._use_redis:
            logger.info("CacheManager: используем in-memory кэш")

    async def stop(self) -> None:
        await self._redis.close()

    def _make_key(self, key: str) -> str:
        if key.startswith(self.KEY_PREFIX):
            return key
        return f"{self.KEY_PREFIX}{key}"

    async def get(self, key: str) -> Optional[Any]:
        k = self._make_key(key)
        if self._use_redis:
            return await self._redis.get(k)
        return await self._memory.get(k)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        k = self._make_key(key)
        t = ttl if ttl is not None else self.default_ttl
        if self._use_redis:
            await self._redis.set(k, value, t)
        else:
            await self._memory.set(k, value, t)

    async def delete(self, key: str) -> None:
        k = self._make_key(key)
        if self._use_redis:
            await self._redis.delete(k)
        else:
            await self._memory.delete(k)

    async def exists(self, key: str) -> bool:
        k = self._make_key(key)
        if self._use_redis:
            return await self._redis.exists(k)
        return await self._memory.exists(k)

    async def get_or_set(
        self, key: str, factory, ttl: Optional[int] = None
    ) -> Any:
        """Получить из кэша или вычислить и сохранить."""
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
        await self.set(key, value, ttl)
        return value

    async def info(self) -> Dict[str, Any]:
        if self._use_redis:
            size = await self._redis.size()
            backend = "redis"
        else:
            size = await self._memory.size()
            backend = "memory"
        return {"backend": backend, "size": size, "ttl": self.default_ttl}
