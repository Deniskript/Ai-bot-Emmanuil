"""
Модуль расчёта звёзд ⭐ за операции с AI.
Приоритет: реальные данные usage от API → fallback расчёт по тексту.
Маржа: 1.75× (75%)
"""

from config import STAR_MARGIN, USD_TO_RUB, STAR_COST_RUB

# Цены OpenRouter за 1M токенов (USD)
# Источник: https://openrouter.ai/docs#models
OPENROUTER_PRICES = {
    "anthropic/claude-sonnet-4.5": {"input": 3.0, "output": 15.0},
    "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    "anthropic/claude-opus-4": {"input": 15.0, "output": 75.0},
    "openai/gpt-4o": {"input": 2.5, "output": 10.0},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "google/gemini-flash-1.5": {"input": 0.075, "output": 0.30},
    # Default для неизвестных моделей (консервативно берём Claude)
    "default": {"input": 3.0, "output": 15.0},
}


def calculate_stars_from_usage(usage: dict, model: str = "default") -> int:
    """
    Рассчитать звёзды по РЕАЛЬНЫМ данным usage от API.
    
    Args:
        usage: {"prompt_tokens": N, "completion_tokens": M, "total_tokens": X}
        model: название модели для определения цены
    
    Returns:
        Количество звёзд к списанию или None если usage пустой
    """
    if not usage:
        return None
    
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    
    if prompt_tokens == 0 and completion_tokens == 0:
        return None
    
    # Получить цены для модели
    prices = OPENROUTER_PRICES.get(model, OPENROUTER_PRICES["default"])
    
    # Рассчитать стоимость API в USD
    input_cost = (prompt_tokens / 1_000_000) * prices["input"]
    output_cost = (completion_tokens / 1_000_000) * prices["output"]
    api_cost_usd = input_cost + output_cost
    
    # Конвертировать в рубли с маржой
    cost_rub = api_cost_usd * USD_TO_RUB * STAR_MARGIN
    
    # Конвертировать в звёзды
    stars = int(cost_rub / STAR_COST_RUB)
    
    # Минимум 1 звезда
    return max(1, stars)


def calculate_stars_fallback(input_text: str, output_text: str) -> int:
    """
    Fallback расчёт по длине текста (если API не вернул usage).
    Консервативная оценка для русского текста.
    
    Args:
        input_text: входной текст (промпт + история)
        output_text: ответ модели
    
    Returns:
        Количество звёзд к списанию
    """
    # Примерная оценка токенов для русского текста:
    # Русский: ~1.5-2 токена на слово, ~0.4-0.5 токена на символ
    # Берём консервативно: 1 токен ≈ 3 символа
    
    input_chars = len(input_text) if isinstance(input_text, str) else sum(len(str(m)) for m in input_text)
    output_chars = len(output_text) if output_text else 0
    
    # Примерные токены
    est_input_tokens = input_chars // 3
    est_output_tokens = output_chars // 3
    
    # Используем default цены (Claude Sonnet)
    prices = OPENROUTER_PRICES["default"]
    
    input_cost = (est_input_tokens / 1_000_000) * prices["input"]
    output_cost = (est_output_tokens / 1_000_000) * prices["output"]
    api_cost_usd = input_cost + output_cost
    
    # С маржой
    cost_rub = api_cost_usd * USD_TO_RUB * STAR_MARGIN
    stars = int(cost_rub / STAR_COST_RUB)
    
    # Минимум 1 звезда
    return max(1, stars)


def calculate_stars(messages, response_text: str, usage: dict = None, model: str = "default") -> int:
    """
    Основная функция расчёта звёзд.
    
    Приоритет:
    1. Реальные данные usage от API (если есть)
    2. Fallback по длине текста
    
    Args:
        messages: входные сообщения (list или str)
        response_text: текст ответа от модели
        usage: данные usage от API (опционально)
        model: название модели
    
    Returns:
        Количество звёзд к списанию
    """
    # Приоритет: реальные данные от API
    if usage:
        stars = calculate_stars_from_usage(usage, model)
        if stars:
            print(f"[STARS] method=API, model={model}, "
                  f"prompt_tokens={usage.get('prompt_tokens')}, "
                  f"completion_tokens={usage.get('completion_tokens')}, "
                  f"stars={stars}")
            return stars
    
    # Fallback: расчёт по длине текста
    input_text = str(messages) if messages else ""
    stars = calculate_stars_fallback(input_text, response_text)
    
    print(f"[STARS] method=FALLBACK, "
          f"input_len={len(input_text)}, "
          f"output_len={len(response_text or '')}, "
          f"stars={stars}")
    
    return stars


def calculate_stars_simple(input_len: int, output_len: int) -> int:
    """
    Упрощённый расчёт по длине (для обратной совместимости).
    Использует fallback логику.
    
    Args:
        input_len: длина входного текста в символах
        output_len: длина выходного текста в символах
    
    Returns:
        Количество звёзд к списанию
    """
    est_input_tokens = input_len // 3
    est_output_tokens = output_len // 3
    
    prices = OPENROUTER_PRICES["default"]
    
    input_cost = (est_input_tokens / 1_000_000) * prices["input"]
    output_cost = (est_output_tokens / 1_000_000) * prices["output"]
    api_cost_usd = input_cost + output_cost
    
    cost_rub = api_cost_usd * USD_TO_RUB * STAR_MARGIN
    stars = int(cost_rub / STAR_COST_RUB)
    
    return max(1, stars)
