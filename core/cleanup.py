"""
Централизованная автоочистка для всех ботов
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, List, Optional

from .config import CLEANUP_INTERVAL

logger = logging.getLogger(__name__)


class CleanupManager:
    """
    Менеджер периодической очистки.
    Регистрирует задачи очистки и выполняет их по расписанию.
    
    Использование:
        cleanup = CleanupManager()
        cleanup.register(rate_limiter.cleanup)
        cleanup.register(cache.cleanup)
        await cleanup.start()
    """
    
    def __init__(self, interval: int = CLEANUP_INTERVAL):
        self.interval = interval
        self._tasks: List[Callable[[], Awaitable[Any]]] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def register(self, cleanup_func: Callable[[], Awaitable[Any]]) -> None:
        """Зарегистрировать функцию очистки."""
        self._tasks.append(cleanup_func)
        logger.debug(f"Registered cleanup: {cleanup_func.__name__ if hasattr(cleanup_func, '__name__') else 'anonymous'}")
    
    async def run_once(self) -> dict:
        """Выполнить все задачи очистки один раз."""
        results = {}
        for task in self._tasks:
            name = task.__name__ if hasattr(task, '__name__') else str(task)
            try:
                result = await task()
                results[name] = result
            except Exception as e:
                logger.error(f"Cleanup error in {name}: {e}")
                results[name] = f"error: {e}"
        return results
    
    async def _loop(self) -> None:
        """Внутренний цикл очистки."""
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                results = await self.run_once()
                # Логируем только если что-то очищено
                cleaned = sum(v for v in results.values() if isinstance(v, int))
                if cleaned > 0:
                    logger.info(f"Cleanup completed: {results}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    async def start(self) -> None:
        """Запустить периодическую очистку."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Cleanup manager started (interval: {self.interval}s, tasks: {len(self._tasks)})")
    
    async def stop(self) -> None:
        """Остановить очистку."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Cleanup manager stopped")
    
    def stats(self) -> dict:
        """Статистика для мониторинга."""
        return {
            "running": self._running,
            "interval": self.interval,
            "registered_tasks": len(self._tasks)
        }


# Глобальный экземпляр
cleanup_manager = CleanupManager()
