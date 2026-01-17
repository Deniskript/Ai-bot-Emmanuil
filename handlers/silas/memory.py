"""
Долгая память для Silas (Психолог)
Работает с PostgreSQL через database.postgres_db
"""
from typing import List
from database import postgres_db as db
from .prompts import SILAS_SYSTEM, MOODS

# Экспортируем для обратной совместимости
__all__ = [
    'get_user_memory',
    'save_user_memory',
    'build_memory_context',
]


async def get_user_memory(user_id: int) -> List:
    """
    Получить долгую память пользователя для Silas
    Returns: список фактов о пользователе
    """
    return await db.get_memory(user_id, 'silas')


async def save_user_memory(user_id: int, facts: List):
    """
    Сохранить обновлённую долгую память пользователя
    """
    await db.save_memory(user_id, 'silas', facts)


def build_memory_context(memory_data) -> str:
    """
    Строит контекст памяти для промпта из списка фактов
    """
    if not memory_data:
        return ""
    
    try:
        if isinstance(memory_data, list):
            if memory_data:
                return "\n\n📝 Что я помню о тебе:\n• " + "\n• ".join(memory_data[:10])
            return ""
        
        if isinstance(memory_data, str):
            import json
            data = json.loads(memory_data)
            if isinstance(data, list) and data:
                return "\n\n📝 Что я помню о тебе:\n• " + "\n• ".join(data[:10])
        
        return ""
    except:
        return ""
