"""
Централизованный мониторинг для всех ботов
"""

import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Опциональный импорт psutil
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil not installed, system metrics unavailable")


class Metrics:
    """
    Сбор метрик системы и ботов.
    
    Использование:
        metrics = Metrics()
        stats = metrics.collect()
        print(stats)
    """
    
    def __init__(self):
        self._start_time = time.time()
        self._custom_metrics: Dict[str, Any] = {}
        self._counters: Dict[str, int] = {}
    
    def set(self, key: str, value: Any) -> None:
        """Установить кастомную метрику."""
        self._custom_metrics[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Получить метрику."""
        return self._custom_metrics.get(key, default)
    
    def increment(self, key: str, amount: int = 1) -> int:
        """Увеличить счётчик. Возвращает новое значение."""
        self._counters[key] = self._counters.get(key, 0) + amount
        return self._counters[key]
    
    def get_counter(self, key: str) -> int:
        """Получить значение счётчика."""
        return self._counters.get(key, 0)
    
    def uptime(self) -> int:
        """Время работы в секундах."""
        return int(time.time() - self._start_time)
    
    def collect(self) -> dict:
        """Собрать все метрики."""
        result = {
            "uptime_seconds": self.uptime(),
            "counters": self._counters.copy(),
            "custom": self._custom_metrics.copy()
        }
        
        if HAS_PSUTIL:
            try:
                process = psutil.Process()
                memory = process.memory_info()
                
                result["system"] = {
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "memory_used_mb": round(psutil.virtual_memory().used / 1024 / 1024, 1),
                }
                result["process"] = {
                    "memory_rss_mb": round(memory.rss / 1024 / 1024, 1),
                    "memory_vms_mb": round(memory.vms / 1024 / 1024, 1),
                    "threads": process.num_threads(),
                }
            except Exception as e:
                logger.debug(f"Error collecting system metrics: {e}")
                result["system"] = {"error": str(e)}
        
        return result
    
    def summary(self) -> str:
        """Краткая сводка для логов."""
        stats = self.collect()
        
        parts = [f"Uptime: {stats['uptime_seconds']}s"]
        
        if "system" in stats and "error" not in stats["system"]:
            parts.append(f"CPU: {stats['system']['cpu_percent']}%")
            parts.append(f"RAM: {stats['system']['memory_percent']}%")
        
        if "process" in stats:
            parts.append(f"RSS: {stats['process']['memory_rss_mb']}MB")
        
        return " | ".join(parts)


# Глобальный экземпляр
metrics = Metrics()
