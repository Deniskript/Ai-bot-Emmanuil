"""
Централизованная очередь API запросов
"""

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from .config import API_MAX_CONCURRENT, API_TIMEOUT

logger = logging.getLogger(__name__)

T = TypeVar('T')


class APIQueue:
    """
    Управление очередью запросов к внешним API.
    Ограничивает параллельные запросы и добавляет таймауты.
    
    Использование:
        queue = APIQueue()
        result = await queue.execute(api_call, arg1, arg2)
        
        # Или как декоратор:
        @queue.limit
        async def my_api_call():
            ...
    """
    
    def __init__(
        self,
        max_concurrent: int = API_MAX_CONCURRENT,
        timeout: float = API_TIMEOUT
    ):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0
        self._total_requests = 0
        self._failed_requests = 0
        self._timeout_requests = 0
        self._lock = asyncio.Lock()
    
    async def execute(
        self,
        func: Callable[..., Any],
        *args,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Optional[Any]:
        """
        Выполнить функцию с ограничением параллелизма и таймаутом.
        
        Returns:
            Результат функции или None при таймауте
            
        Raises:
            Exception при ошибке (кроме таймаута)
        """
        timeout = timeout or self.timeout
        
        async with self._lock:
            self._active_count += 1
            self._total_requests += 1
        
        try:
            async with self._semaphore:
                try:
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout
                    )
                    return result
                except asyncio.TimeoutError:
                    logger.warning(f"API timeout after {timeout}s: {func.__name__}")
                    async with self._lock:
                        self._timeout_requests += 1
                    return None
                except Exception as e:
                    logger.error(f"API error in {func.__name__}: {e}")
                    async with self._lock:
                        self._failed_requests += 1
                    raise
        finally:
            async with self._lock:
                self._active_count -= 1
    
    def limit(self, func: Callable[..., T]) -> Callable[..., T]:
        """Декоратор для ограничения API вызовов."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.execute(func, *args, **kwargs)
        return wrapper
    
    @property
    def is_busy(self) -> bool:
        """Проверить загружена ли очередь (>80%)."""
        return self._active_count > self.max_concurrent * 0.8
    
    @property
    def active_count(self) -> int:
        """Количество активных запросов."""
        return self._active_count
    
    def stats(self) -> dict:
        """Статистика для мониторинга."""
        return {
            "active": self._active_count,
            "max_concurrent": self.max_concurrent,
            "total_requests": self._total_requests,
            "failed_requests": self._failed_requests,
            "timeout_requests": self._timeout_requests,
            "timeout": self.timeout,
            "is_busy": self.is_busy
        }


# Глобальный экземпляр
api_queue = APIQueue()
