"""
Утилиты для работы с калориями и питанием
"""
import re
from datetime import date, timedelta
from typing import Dict, List


def parse_calories_response(text: str) -> Dict:
    """
    Парсит ответ AI с калориями и БЖУ
    
    Args:
        text: Текст ответа от AI
    
    Returns:
        Dict с данными о еде
    """
    result = {
        "name": "",
        "portion": "",
        "calories": 0,
        "protein": 0.0,
        "fat": 0.0,
        "carbs": 0.0
    }
    
    # Ищем название блюда
    name_match = re.search(r'Блюдо:?\s*(.+?)(?:\n|⚖️)', text, re.IGNORECASE)
    if name_match:
        result["name"] = name_match.group(1).strip()
    
    # Ищем порцию
    portion_match = re.search(r'Порци[яи]:?\s*(.+?)(?:\n|🔥)', text, re.IGNORECASE)
    if portion_match:
        result["portion"] = portion_match.group(1).strip()
    
    # Ищем калории
    cal_match = re.search(r'(\d+)\s*ккал', text)
    if cal_match:
        result["calories"] = int(cal_match.group(1))
    
    # Ищем белки
    protein_match = re.search(r'Белк[ои]:?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if protein_match:
        result["protein"] = float(protein_match.group(1))
    
    # Ищем жиры
    fat_match = re.search(r'Жир[ыа]:?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if fat_match:
        result["fat"] = float(fat_match.group(1))
    
    # Ищем углеводы
    carbs_match = re.search(r'Углевод[ыа]:?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
    if carbs_match:
        result["carbs"] = float(carbs_match.group(1))
    
    return result


def calculate_bmr(weight: float, height: int, age: int, gender: str) -> int:
    """
    Рассчитать базовый метаболизм по формуле Миффлина-Сан Жеора
    
    Args:
        weight: Вес в кг
        height: Рост в см
        age: Возраст в годах
        gender: Пол ('м' или 'ж')
    
    Returns:
        Базовый метаболизм в ккал
    """
    if gender.lower() in ['м', 'm', 'муж', 'male']:
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    
    return int(bmr)


def calculate_tdee(bmr: int, activity: str) -> int:
    """
    Рассчитать общий расход энергии (TDEE)
    
    Args:
        bmr: Базовый метаболизм
        activity: Уровень активности
    
    Returns:
        TDEE в ккал
    """
    activity_multipliers = {
        "низкая": 1.2,
        "низкий": 1.2,
        "low": 1.2,
        "средняя": 1.55,
        "средний": 1.55,
        "medium": 1.55,
        "высокая": 1.9,
        "высокий": 1.9,
        "high": 1.9
    }
    
    multiplier = activity_multipliers.get(activity.lower(), 1.55)
    return int(bmr * multiplier)


def calculate_macros(daily_calories: int, weight: float, goal: str) -> Dict:
    """
    Рассчитать макронутриенты (БЖУ)
    
    Args:
        daily_calories: Дневная норма калорий
        weight: Вес в кг
        goal: Цель ('lose', 'maintain', 'gain')
    
    Returns:
        Dict с белками, жирами и углеводами
    """
    # Белки: 1.6-2.2г на кг веса в зависимости от цели
    if goal == "lose":
        protein = int(weight * 2.0)  # Больше белка при похудении
    elif goal == "gain":
        protein = int(weight * 2.2)  # Максимум белка для набора массы
    else:
        protein = int(weight * 1.8)  # Средний уровень
    
    # Жиры: 25-30% от калорий
    fat_calories = int(daily_calories * 0.25)
    fat = int(fat_calories / 9)  # 9 ккал в 1г жира
    
    # Углеводы: остаток калорий
    remaining_calories = daily_calories - (protein * 4) - (fat * 9)
    carbs = int(remaining_calories / 4)  # 4 ккал в 1г углеводов
    
    return {
        "protein": protein,
        "fat": fat,
        "carbs": carbs
    }


def format_date(days_ago: int = 0) -> str:
    """Форматировать дату для отображения"""
    target_date = date.today() - timedelta(days=days_ago)
    
    if days_ago == 0:
        return "Сегодня"
    elif days_ago == 1:
        return "Вчера"
    else:
        return target_date.strftime("%d.%m.%Y")


def get_meal_time() -> str:
    """Определить текущий приём пищи"""
    from datetime import datetime
    hour = datetime.now().hour
    
    if 5 <= hour < 11:
        return "завтрак"
    elif 11 <= hour < 16:
        return "обед"
    elif 16 <= hour < 19:
        return "полдник"
    elif 19 <= hour < 23:
        return "ужин"
    else:
        return "ночной перекус"


def format_calories_summary(stats: Dict, goal: Dict = None) -> str:
    """
    Форматировать сводку по калориям
    
    Args:
        stats: Статистика калорий
        goal: Цель пользователя (опционально)
    
    Returns:
        Отформатированная строка
    """
    text = f"🔥 Калории: {stats['calories']:,} ккал\n"
    text += f"🥩 Белки: {stats['protein']:.1f}г\n"
    text += f"🧈 Жиры: {stats['fat']:.1f}г\n"
    text += f"🍞 Углеводы: {stats['carbs']:.1f}г"
    
    if goal:
        remaining = goal['daily_calories'] - stats['calories']
        if remaining > 0:
            text += f"\n\n📊 Осталось: {remaining:,} ккал"
        else:
            text += f"\n\n⚠️ Превышение: {abs(remaining):,} ккал"
    
    return text
