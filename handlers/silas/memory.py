"""
Долгая память для Silas (Психолог)
Работает с PostgreSQL через database.postgres_db
"""
import json
import logging
from typing import Any, List, Optional

from database import postgres_db as db

logger = logging.getLogger(__name__)

# Экспортируем для обратной совместимости
__all__ = [
    'get_user_memory',
    'save_user_memory',
    'build_memory_context',
]


async def get_user_memory(user_id: int) -> List[str]:
    """
    Получить долгую память пользователя для Silas
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Список фактов о пользователе
    """
    return await db.get_memory(user_id, 'silas')


async def save_user_memory(user_id: int, facts: List[str]) -> None:
    """
    Сохранить обновлённую долгую память пользователя
    
    Args:
        user_id: ID пользователя
        facts: Список фактов для сохранения
    """
    await db.save_memory(user_id, 'silas', facts)


def build_memory_context(memory_data: Any) -> str:
    """
    Строит контекст памяти для промпта из списка фактов
    
    Args:
        memory_data: Данные памяти (list, str или None)
        
    Returns:
        Строка контекста для добавления в промпт
    """
    if not memory_data:
        return ""
    
    try:
        if isinstance(memory_data, list):
            if memory_data:
                # Ограничиваем до 10 фактов
                facts = memory_data[:10]
                return "\n\n📝 Что я помню о тебе:\n• " + "\n• ".join(facts)
            return ""
        
        if isinstance(memory_data, str):
            try:
                data = json.loads(memory_data)
                if isinstance(data, list) and data:
                    facts = data[:10]
                    return "\n\n📝 Что я помню о тебе:\n• " + "\n• ".join(facts)
            except json.JSONDecodeError:
                logger.debug(f"Failed to parse memory_data as JSON")
        
        return ""
        
    except Exception as e:
        logger.error(f"Error in build_memory_context: {e}")
        return ""
