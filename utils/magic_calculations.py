"""
Вспомогательные вычисления для модуля Магия
"""
from __future__ import annotations

from datetime import date, datetime, timedelta


MASTER_NUMBERS = {11, 22, 33}


def reduce_number(value: int) -> int:
    """Свести число к вибрации (1-9), учитывая мастер-числа."""
    while value > 9 and value not in MASTER_NUMBERS:
        value = sum(int(d) for d in str(value))
    return value


def digits_sum(text: str) -> int:
    """Сумма цифр строки."""
    return sum(int(c) for c in text if c.isdigit())


def name_number(full_name: str) -> int:
    """Число имени по буквам (рус/лат)."""
    if not full_name:
        return 0
    mapping = {
        # Латиница
        "A": 1, "J": 1, "S": 1,
        "B": 2, "K": 2, "T": 2,
        "C": 3, "L": 3, "U": 3,
        "D": 4, "M": 4, "V": 4,
        "E": 5, "N": 5, "W": 5,
        "F": 6, "O": 6, "X": 6,
        "G": 7, "P": 7, "Y": 7,
        "H": 8, "Q": 8, "Z": 8,
        "I": 9, "R": 9,
        # Кириллица
        "А": 1, "И": 1, "С": 1, "Ъ": 1,
        "Б": 2, "Й": 2, "Т": 2, "Ы": 2,
        "В": 3, "К": 3, "У": 3, "Ь": 3,
        "Г": 4, "Л": 4, "Ф": 4, "Э": 4,
        "Д": 5, "М": 5, "Х": 5, "Ю": 5,
        "Е": 6, "Н": 6, "Ц": 6, "Я": 6,
        "Ё": 7, "О": 7, "Ч": 7,
        "Ж": 8, "П": 8, "Ш": 8,
        "З": 9, "Р": 9, "Щ": 9,
    }
    total = 0
    for ch in full_name.upper():
        total += mapping.get(ch, 0)
    return reduce_number(total)


def destiny_number(birth_date: str) -> int:
    """Число судьбы по дате рождения YYYY-MM-DD."""
    if not birth_date:
        return 0
    total = digits_sum(birth_date)
    return reduce_number(total)


def day_number(target_date: date | None = None) -> int:
    """Число дня."""
    if not target_date:
        target_date = date.today()
    total = digits_sum(target_date.isoformat())
    return reduce_number(total)


def personal_year_number(birth_date: str, target_date: date | None = None) -> int:
    """Персональный год по дате рождения и текущему году."""
    if not birth_date:
        return 0
    if not target_date:
        target_date = date.today()
    bd = date.fromisoformat(birth_date)
    total = bd.day + bd.month + target_date.year
    return reduce_number(total)


def karma_number(birth_date: str, full_name: str) -> int:
    """Кармическое число как объединение даты и имени."""
    return reduce_number(destiny_number(birth_date) + name_number(full_name))


def zodiac_sign(birth_date: str) -> str:
    """Определить знак зодиака по дате рождения."""
    if not birth_date:
        return "неизвестен"
    d = date.fromisoformat(birth_date)
    md = d.month * 100 + d.day
    signs = [
        (120, "Козерог"), (219, "Водолей"), (320, "Рыбы"),
        (420, "Овен"), (521, "Телец"), (621, "Близнецы"),
        (722, "Рак"), (823, "Лев"), (923, "Дева"),
        (1023, "Весы"), (1122, "Скорпион"), (1222, "Стрелец"),
        (1231, "Козерог"),
    ]
    for limit, name in signs:
        if md <= limit:
            return name
    return "Козерог"


def moon_phase_info(target_date: date | None = None) -> dict:
    """Простая оценка фазы луны."""
    if not target_date:
        target_date = date.today()
    known_new_moon = datetime(2024, 1, 11)
    synodic_days = 29.530588
    days = (datetime.combine(target_date, datetime.min.time()) - known_new_moon).days
    phase = (days % synodic_days) / synodic_days
    if phase < 0.03 or phase > 0.97:
        name = "Новолуние"
    elif phase < 0.25:
        name = "Растущий серп"
    elif phase < 0.28:
        name = "Первая четверть"
    elif phase < 0.48:
        name = "Растущая луна"
    elif phase < 0.53:
        name = "Полнолуние"
    elif phase < 0.75:
        name = "Убывающая луна"
    elif phase < 0.78:
        name = "Последняя четверть"
    else:
        name = "Убывающий серп"
    return {"name": name, "phase": round(phase, 2)}


def moon_day_advice(phase_name: str) -> dict:
    """Рекомендации по фазе."""
    advice = {
        "Новолуние": ("🌑 Время начинаний и намерений.", "❌ Не торопите события."),
        "Растущий серп": ("🌒 Планируйте и запускайте проекты.", "❌ Избегайте суеты."),
        "Первая четверть": ("🌓 Решительные действия приветствуются.", "❌ Не перегружайтесь."),
        "Растущая луна": ("🌔 Время роста и развития.", "❌ Не сомневайтесь в себе."),
        "Полнолуние": ("🌕 Энергия на пике, завершайте дела.", "❌ Не принимайте импульсивных решений."),
        "Убывающая луна": ("🌖 Хорошо отпускать и очищать.", "❌ Не начинайте тяжёлые проекты."),
        "Последняя четверть": ("🌗 Подведите итоги и скорректируйте планы.", "❌ Не цепляйтесь за старое."),
        "Убывающий серп": ("🌘 Завершение, отдых, восстановление.", "❌ Избегайте конфликтов."),
    }
    ok, no = advice.get(phase_name, ("✅ День для мягких дел.", "❌ Не перегружайте себя."))
    return {"good": ok, "bad": no}


def moon_month_calendar(start_date: date | None = None) -> str:
    """Краткий календарь на месяц с фазами."""
    if not start_date:
        start_date = date.today().replace(day=1)
    lines = []
    for i in range(0, 30, 5):
        d = start_date + timedelta(days=i)
        info = moon_phase_info(d)
        lines.append(f"{d.strftime('%d.%m')}: {info['name']}")
    return "\n".join(lines)


def moon_month_grid(target_date: date | None = None) -> list:
    """Сетка календаря на месяц с фазами."""
    if not target_date:
        target_date = date.today()
    first_day = target_date.replace(day=1)
    # Определяем сколько дней в месяце
    next_month = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1)
    last_day = next_month - timedelta(days=1)
    days_in_month = last_day.day
    start_weekday = first_day.weekday()  # 0=Mon

    grid = []
    week = []
    # Заполняем пустые перед первым днем
    for _ in range(start_weekday):
        week.append(None)
    for day in range(1, days_in_month + 1):
        d = first_day.replace(day=day)
        info = moon_phase_info(d)
        week.append({
            "day": day,
            "phase": info["name"]
        })
        if len(week) == 7:
            grid.append(week)
            week = []
    if week:
        while len(week) < 7:
            week.append(None)
        grid.append(week)
    return grid
