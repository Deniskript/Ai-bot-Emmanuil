"""
Централизованный LRU кэш для всех ботов
"""

import asyncio
import logging
import time
from collections import OrderedDict
from typing import Any, Optional

from .config import CACHE_DEFAULT_TTL, CACHE_MAX_SIZE

logger = logging.getLogger(__name__)


class LRUCache:
    """
    LRU кэш с TTL и автоочисткой.
    Потокобезопасный.
    
    Использование:
        cache = LRUCache(max_size=1000)
        await cache.set("key", value, ttl=300)
        value = await cache.get("key")
    """
    
    def __init__(
        self, 
        max_size: int = CACHE_MAX_SIZE,
        default_ttl: int = CACHE_DEFAULT_TTL
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._lock = asyncio.Lock()
    
    async def get(self, key: Any) -> Optional[Any]:
        """Получить значение. None если нет или истёк TTL."""
        async with self._lock:
            str_key = str(key)
            if str_key not in self._cache:
                return None
            
            entry = self._cache[str_key]
            
            # Проверить TTL
            if entry["expires"] and time.time() > entry["expires"]:
                del self._cache[str_key]
                return None
            
            # Переместить в конец (LRU)
            self._cache.move_to_end(str_key)
            return entry["value"]
    
    async def set(
        self, 
        key: Any, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> None:
        """Сохранить значение с TTL."""
        async with self._lock:
            str_key = str(key)
            ttl = ttl if ttl is not None else self.default_ttl
            expires = time.time() + ttl if ttl > 0 else None
            
            if str_key in self._cache:
                self._cache.move_to_end(str_key)
            
            self._cache[str_key] = {
                "value": value,
                "expires": expires,
                "created": time.time()
            }
            
            # Удалить старые если превышен лимит
            while len(self._cache) > self.max_size:
                removed_key, _ = self._cache.popitem(last=False)
                logger.debug(f"LRU evicted: {removed_key}")
    
    async def delete(self, key: Any) -> bool:
        """Удалить ключ. Возвращает True если был."""
        async with self._lock:
            str_key = str(key)
            if str_key in self._cache:
                del self._cache[str_key]
                return True
            return False
    
    async def cleanup(self) -> int:
        """Очистить истёкшие записи. Возвращает количество."""
        async with self._lock:
            now = time.time()
            expired = [
                k for k, v in self._cache.items()
                if v["expires"] and now > v["expires"]
            ]
            for k in expired:
                del self._cache[k]
            
            if expired:
                logger.debug(f"Cache cleanup: {len(expired)} expired entries")
            return len(expired)
    
    async def clear(self) -> int:
        """Очистить весь кэш."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count
    
    def __len__(self) -> int:
        """Количество записей в кэше."""
        return len(self._cache)
    
    def stats(self) -> dict:
        """Статистика для мониторинга."""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "default_ttl": self.default_ttl
        }
