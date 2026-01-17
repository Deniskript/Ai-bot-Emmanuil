"""
Модуль точного подсчёта звёзд ⭐ для всех ботов.
Учитывает:
- Русский текст (меньше символов на единицу API)
- Разницу цен input/output (output дороже)
- Маржу 50-60%
"""

# Множитель маржи (2.5 = ~150% маржи)
STAR_MARGIN = 2.5


def count_api_units_estimate(text: str) -> int:
    """
    Оценка количества единиц API в тексте.
    
    Русский текст: ~2.5 символа на единицу
    Английский: ~4 символа на единицу
    Смешанный: ~3 символа на единицу
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


def calculate_stars(messages: list, response: str) -> int:
    """
    Подсчёт использованных звёзд ⭐.
    Конверсия: 100 единиц API = 1 звезда.
    
    Учитывает что output дороже input:
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
    
    # Считаем единицы API
    input_units = count_api_units_estimate(input_text)
    output_units = count_api_units_estimate(response)
    
    # Взвешенная сумма (output × 3 т.к. дороже)
    weighted = input_units + (output_units * 3)
    
    # Применяем маржу
    api_units = int(weighted * STAR_MARGIN)
    
    # Конвертируем единицы API -> звёзды
    return max(1, api_units // 100)


def calculate_stars_simple(input_len: int, output_len: int) -> int:
    """
    Упрощённый подсчёт по длине текста.
    Для случаев когда messages недоступны.
    """
    input_units = input_len // 3  # Для русского
    output_units = output_len // 3
    
    weighted = input_units + (output_units * 3)
    api_units = int(weighted * STAR_MARGIN)
    
    return max(1, api_units // 100)
