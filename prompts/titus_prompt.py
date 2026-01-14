"""
DEPRECATED: Этот файл создан для обратной совместимости с админ-панелью.
Настоящие промпты находятся в handlers/titus/prompts.py
"""
from handlers.titus.prompts import TITUS_BASE

# Для обратной совместимости с админ-панелью
SYSTEM_PROMPT = TITUS_BASE

__all__ = ['TITUS_BASE', 'SYSTEM_PROMPT']
