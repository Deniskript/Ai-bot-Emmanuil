from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

# ============================================
# === ОБЩИЕ КЛАВИАТУРЫ ===
# ============================================

def main_kb(user_id: int):
    """Главное меню с Mini App кнопками"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🫧 Soul AI"), KeyboardButton(text="💼 Кабинет", web_app=WebAppInfo(url=f"https://soul-bot.ru/webapp?user_id={user_id}"))],
        [KeyboardButton(text="💳 Оплата", web_app=WebAppInfo(url=f"https://soul-bot.ru/payment?user_id={user_id}")), KeyboardButton(text="❓ Помощь", web_app=WebAppInfo(url=f"https://soul-bot.ru/help?user_id={user_id}"))]
    ], resize_keyboard=True)

def bots_menu_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💬 Диалог"), KeyboardButton(text="🛋️ Психолог")],
        [KeyboardButton(text="📚 Обучение"), KeyboardButton(text="🎨 Творчество")],
        [KeyboardButton(text="🍎 Здоровье"), KeyboardButton(text="🏃 Лайфстайл")],
        [KeyboardButton(text="◀️ Главное меню")]
    ], resize_keyboard=True)

def back_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

# ============================================
# === ДИАЛОГ (Soul AI) ===
# ============================================

# ============================================
# === LUKA (Soul AI) - ПЕРЕНЕСЕНО В handlers/luka/keyboards.py ===
# ============================================
# Функции dialog_kb, dialog_chat_kb, dialog_chat_loading_kb, dialog_char_kb
# теперь находятся в автономном модуле handlers/luka/

# ============================================
# === ПСИХОЛОГ (Silas) - ПЕРЕНЕСЕНО В handlers/silas/keyboards.py ===
# ============================================
# Функции psycho_kb, psycho_chat_kb, psycho_dur_kb, psycho_mood_kb
# теперь находятся в автономном модуле handlers/silas/

# ============================================
# === ОБУЧЕНИЕ (Titus) ===
# ============================================

def study_kb(user_id: int):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Новый курс"), KeyboardButton(text="📂 Ваши курсы")],
        [KeyboardButton(text="📚 Анализ видео")],
        [KeyboardButton(text="🔍 Помощь", web_app=WebAppInfo(url=f"https://soul-bot.ru/help?user_id={user_id}")), KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def study_chat_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛑 Завершить"), KeyboardButton(text="🗑 Очистить")]
    ], resize_keyboard=True)

def study_chat_loading_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⌛️ Отменить запрос")]
    ], resize_keyboard=True)

def study_steps_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🚀 10 шагов"), KeyboardButton(text="📘 40 шагов")],
        [KeyboardButton(text="📖 80 шагов")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def courses_action_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="▶️ Продолжить курс"), KeyboardButton(text="🗑 Удалить курс")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def courses_list_kb(courses, show_progress: bool = False):
    kb = []
    for i, c in enumerate(courses[:5], 1):
        name = c['name'][:18]
        if show_progress:
            current = c.get('current', 1)
            total = c.get('total', 10)
            text = f"{i}. {name} ({current}/{total})"
        else:
            text = f"{i}. {name}"
        kb.append([KeyboardButton(text=text)])
    kb.append([KeyboardButton(text="◀️ Назад")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ============================================
# === ВИРУСНЫЙ РАЗБОР ===
# ============================================

def viral_kb(user_id: int):
    """Клавиатура для вирусного разбора"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💬 Текстовый совет")],
        [KeyboardButton(text="📤 Загрузить видео"), KeyboardButton(text="🔗 Отправить ссылку")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def health_kb(user_id: int):
    """Меню раздела Здоровье"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🍽 Подсчёт калорий")],
        [KeyboardButton(text="📊 Журнал калорий"), KeyboardButton(text="🥗 Питание")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def calories_menu_kb():
    """Меню подсчёта калорий"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📸 По фото")],
        [KeyboardButton(text="✏️ Записать вручную")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def journal_menu_kb():
    """Меню журнала калорий"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📅 Сегодня"), KeyboardButton(text="📅 Вчера")],
        [KeyboardButton(text="📅 Неделя"), KeyboardButton(text="📅 Месяц")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def nutrition_menu_kb():
    """Меню питания"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Что поесть сейчас?")],
        [KeyboardButton(text="📅 План на день")],
        [KeyboardButton(text="🎯 Моя цель"), KeyboardButton(text="💡 Советы")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def lifestyle_kb(user_id: int):
    """Меню раздела Лайфстайл"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎬 Вирусный разбор"), KeyboardButton(text="🌅 Режим дня")],
        [KeyboardButton(text="🎯 Трекер целей"), KeyboardButton(text="🧘 Ментальное")],
        [KeyboardButton(text="💰 Финансы")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)


def goals_menu_kb():
    """Меню трекера целей"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Новая цель")],
            [KeyboardButton(text="📋 Мои цели"), KeyboardButton(text="🔥 Мой streak")],
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )


def routine_menu_kb():
    """Меню режима дня"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="☀️ Утренний чеклист"), KeyboardButton(text="🌙 Вечерняя рефлексия")],
            [KeyboardButton(text="⚙️ Настроить рутину"), KeyboardButton(text="📊 Продуктивность")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )


def mental_menu_kb():
    """Меню ментального здоровья"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧘‍♀️ Медитация"), KeyboardButton(text="😊 Настроение")],
            [KeyboardButton(text="💆 Убрать тревогу"), KeyboardButton(text="✨ Аффирмация")],
            [KeyboardButton(text="📊 График настроения")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )


def finance_menu_kb():
    """Меню финансов"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Записать трату")],
            [KeyboardButton(text="📊 Мои расходы"), KeyboardButton(text="🎯 Бюджет")],
            [KeyboardButton(text="💡 Советы"), KeyboardButton(text="📈 Аналитика")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )

# ============================================
# === ТВОРЧЕСТВО (Фото/Видео/Блогерам/Креатив) ===
# ============================================

def creativity_kb(user_id: int):
    """Меню творчества: каждая кнопка сразу открывает WebApp"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎬 Видео", web_app=WebAppInfo(url=f"https://soul-bot.ru/creativity/video?user_id={user_id}")),
         KeyboardButton(text="📷 Фото", web_app=WebAppInfo(url=f"https://soul-bot.ru/creativity/photo?user_id={user_id}"))],
        [KeyboardButton(text="📱 Блогерам", web_app=WebAppInfo(url=f"https://soul-bot.ru/creativity/blogger?user_id={user_id}")),
         KeyboardButton(text="🎭 Креатив", web_app=WebAppInfo(url=f"https://soul-bot.ru/creativity/creative?user_id={user_id}"))],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)


# Backward-compat alias: старые места в коде вызывают photo_kb()
def photo_kb(user_id: int):
    return creativity_kb(user_id)

# ============================================
# === ГОЛОСОВОЙ РЕЖИМ ===
# ============================================

# ============================================
# === ГОЛОСОВОЙ РЕЖИМ - ПЕРЕНЕСЕНО В handlers/luka/keyboards.py ===
# ============================================
# Функции voice_chat_kb и voice_chat_loading_kb
# теперь находятся в автономном модуле handlers/luka/

# ============================================
# === АЛИАСЫ ДЛЯ СОВМЕСТИМОСТИ ===
# ============================================

# Luka и Silas теперь автономные модули - алиасы удалены
titus_kb = study_kb
titus_chat_kb = study_chat_kb
titus_steps_kb = study_steps_kb
