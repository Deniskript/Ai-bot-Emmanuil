"""
Модуль точного подсчёта токенов для всех ботов.
Учитывает:
- Русский текст (меньше символов на токен)
- Разницу цен input/output (output в 5 раз дороже)
- Маржу 50-60%
"""

# Множитель маржи (1.8 = ~50-55% маржи)
TOKEN_MARGIN = 1.8


def count_tokens_estimate(text: str) -> int:
    """
    Оценка количества токенов в тексте.
    
    Русский текст: ~2.5 символа на токен
    Английский: ~4 символа на токен
    Смешанный: ~3 символа на токен
    """
    if not text:
        return 0
    
    # Считаем долю кириллицы
    cyrillic = sum(1 for c in text if 'а' <= c.lower() <= 'я' or c in 'ёЁ')
    total = len(text)
    
    if total == 0:
        return 0
    
    cyrillic_ratio = cyrillic / total
    
    # Чем больше русского, тем меньше делитель
    if cyrillic_ratio > 0.5:
        divisor = 2.5  # Русский текст
    elif cyrillic_ratio > 0.2:
        divisor = 3.0  # Смешанный
    else:
        divisor = 4.0  # Английский
    
    return int(len(text) / divisor)


def calculate_tokens(messages: list, response: str) -> int:
    """
    Главная функция подсчёта токенов для списания.
    
    Учитывает что output дороже input в 5 раз:
    - Input: $3 / 1M токенов  
    - Output: $15 / 1M токенов
    
    Формула: (input + output×3) × маржа
    """
    # Собираем весь input текст
    input_text = ""
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, str):
            input_text += content + " "
        elif isinstance(content, list):
            # Мультимодальный контент (картинки)
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    input_text += item.get("text", "") + " "
    
    # Считаем токены
    input_tokens = count_tokens_estimate(input_text)
    output_tokens = count_tokens_estimate(response)
    
    # Взвешенная сумма (output × 3 т.к. дороже)
    weighted = input_tokens + (output_tokens * 3)
    
    # Применяем маржу
    final = int(weighted * TOKEN_MARGIN)
    
    # Минимум 50 токенов за запрос
    return max(final, 50)


def calculate_tokens_simple(input_len: int, output_len: int) -> int:
    """
    Упрощённый подсчёт по длине текста.
    Для случаев когда messages недоступны.
    """
    input_tokens = input_len // 3  # Для русского
    output_tokens = output_len // 3
    
    weighted = input_tokens + (output_tokens * 3)
    final = int(weighted * TOKEN_MARGIN)
    
    return max(final, 50)
