"""
Централизованный Rate Limiter для всех ботов
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Dict, List, Tuple

from .config import RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter на пользователя.
    Потокобезопасный, с автоочисткой.
    
    Использование:
        limiter = RateLimiter()
        allowed, wait_time = await limiter.check(user_id)
        if not allowed:
            await message.answer(f"Подожди {wait_time} сек")
    """
    
    def __init__(
        self, 
        max_requests: int = RATE_LIMIT_REQUESTS, 
        window_seconds: int = RATE_LIMIT_WINDOW
    ):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: Dict[int, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        
    async def check(self, user_id: int) -> Tuple[bool, int]:
        """
        Проверить разрешён ли запрос.
        
        Returns:
            (True, 0) — разрешён
            (False, seconds) — заблокирован, ждать seconds
        """
        async with self._lock:
            now = time.time()
            
            # Очистить старые запросы
            self._requests[user_id] = [
                t for t in self._requests[user_id]
                if now - t < self.window
            ]
            
            # Проверить лимит
            if len(self._requests[user_id]) >= self.max_requests:
                oldest = min(self._requests[user_id])
                wait_time = int(self.window - (now - oldest)) + 1
                logger.debug(f"Rate limited user {user_id}, wait {wait_time}s")
                return False, wait_time
            
            # Записать запрос
            self._requests[user_id].append(now)
            return True, 0
    
    async def cleanup(self) -> int:
        """Очистить старые записи. Возвращает количество очищенных."""
        async with self._lock:
            now = time.time()
            cleaned = 0
            empty_users = []
            
            for user_id, timestamps in self._requests.items():
                old_len = len(timestamps)
                self._requests[user_id] = [
                    t for t in timestamps if now - t < self.window
                ]
                cleaned += old_len - len(self._requests[user_id])
                
                if not self._requests[user_id]:
                    empty_users.append(user_id)
            
            for user_id in empty_users:
                del self._requests[user_id]
            
            if cleaned > 0:
                logger.debug(f"RateLimiter cleanup: {cleaned} entries")
            return cleaned
    
    def stats(self) -> dict:
        """Статистика для мониторинга."""
        return {
            "users_tracked": len(self._requests),
            "total_requests": sum(len(v) for v in self._requests.values()),
            "max_requests": self.max_requests,
            "window_seconds": self.window
        }


# Глобальный экземпляр (singleton)
rate_limiter = RateLimiter()
