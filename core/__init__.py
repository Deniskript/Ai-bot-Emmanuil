"""
Core — централизованное ядро для всех ботов

Использование:
    from core import rate_limiter, api_queue, cleanup_manager, metrics
    from core.cache import LRUCache
    from core.config import RATE_LIMIT_REQUESTS

Компоненты:
    - rate_limiter: Rate limiting на пользователя (10 req/60s)
    - api_queue: Очередь API с semaphore (max 50 concurrent)
    - cleanup_manager: Периодическая очистка (каждые 5 мин)
    - metrics: Мониторинг системы и ботов
    - LRUCache: Кэш с TTL и автоочисткой
    - config: Все лимиты в одном месте
"""

from core.cache import LRUCache
from core.cleanup import CleanupManager, cleanup_manager
from core.metrics import Metrics, metrics
from core.queue import APIQueue, api_queue
from core.rate_limiter import RateLimiter, rate_limiter
from core import config

__version__ = "1.0.0"

__all__ = [
    # Классы
    "RateLimiter",
    "LRUCache", 
    "APIQueue",
    "CleanupManager",
    "Metrics",
    
    # Глобальные экземпляры (singleton)
    "rate_limiter",
    "api_queue",
    "cleanup_manager",
    "metrics",
    
    # Конфигурация
    "config",
    
    # Версия
    "__version__"
]
