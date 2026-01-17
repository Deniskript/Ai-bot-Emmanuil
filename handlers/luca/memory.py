"""
Долгая память для Luca (Soul AI)
Работает с PostgreSQL через database.postgres_db
"""
from typing import List, Dict
from database import postgres_db as db
from .prompts import (
    LUCA_BASE,
    CHARS,
    CHAR_NAMES,
    build_memory_context,
    build_prompt_with_memory
)

# Экспортируем для обратной совместимости
__all__ = [
    'get_user_memory',
    'save_user_memory',
    'build_memory_context',
    'build_prompt_with_memory',
    'LUCA_BASE',
    'CHARS',
    'CHAR_NAMES'
]


async def get_user_memory(user_id: int) -> List:
    """
    Получить долгую память пользователя для Luca
    Returns: список фактов о пользователе
    """
    return await db.get_memory(user_id, 'luca')


async def save_user_memory(user_id: int, facts: List):
    """
    Сохранить обновлённую долгую память пользователя
    """
    await db.save_memory(user_id, 'luca', facts)
