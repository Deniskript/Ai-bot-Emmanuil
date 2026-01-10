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
        [KeyboardButton(text="💭 Диалог"), KeyboardButton(text="🛋️ Психолог")],
        [KeyboardButton(text="📓 Обучение"), KeyboardButton(text="📷 Фото")],
        [KeyboardButton(text="◀️ Главное меню")]
    ], resize_keyboard=True)

def back_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

# ============================================
# === ДИАЛОГ (Soul AI) ===
# ============================================

def dialog_kb(user_id: int):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="☁️ Начать"), KeyboardButton(text="🔄 Режим")],
        [KeyboardButton(text="🗑 Очистить"), KeyboardButton(text="🔍 Помощь", web_app=WebAppInfo(url=f"https://soul-bot.ru/help?user_id={user_id}"))],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def dialog_chat_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛑 Завершить"), KeyboardButton(text="🗑 Очистить")]
    ], resize_keyboard=True)

def dialog_chat_loading_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⌛️ Отменить запрос")]
    ], resize_keyboard=True)

def dialog_char_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🕊 Душа"), KeyboardButton(text="💡 Разум")],
        [KeyboardButton(text="◀️ Назад к Диалогу")]
    ], resize_keyboard=True)

# ============================================
# === ПСИХОЛОГ (Silas) ===
# ============================================

def psycho_kb(user_id: int):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛋️ Начать сеанс"), KeyboardButton(text="📔 Настроение")],
        [KeyboardButton(text="🔍 Помощь", web_app=WebAppInfo(url=f"https://soul-bot.ru/help?user_id={user_id}")), KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

def psycho_chat_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛑 Завершить"), KeyboardButton(text="🗑 Очистить")]
    ], resize_keyboard=True)

def psycho_chat_loading_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⌛️ Отменить запрос")]
    ], resize_keyboard=True)

def psycho_dur_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="15 минут"), KeyboardButton(text="30 минут"), KeyboardButton(text="60 минут")],
        [KeyboardButton(text="◀️ Назад к Психологу")]
    ], resize_keyboard=True)

def psycho_mood_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Хорошо"), KeyboardButton(text="Устал"), KeyboardButton(text="Тяжело")],
        [KeyboardButton(text="✏️ Ваше настроение"), KeyboardButton(text="Статистика")],
        [KeyboardButton(text="◀️ Назад к Психологу")]
    ], resize_keyboard=True)

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
# === ГЕНЕРАЦИЯ ФОТО ===
# ============================================

def photo_kb(user_id: int):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📷 Создать"), KeyboardButton(text="✏️ Редактор")],
        [KeyboardButton(text="🎨 4K Фото"), KeyboardButton(text="⚙️ Настройки", web_app=WebAppInfo(url=f"https://soul-bot.ru?user_id={user_id}#photoSettings"))],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)

# ============================================
# === АЛИАСЫ ДЛЯ СОВМЕСТИМОСТИ ===
# ============================================

luca_kb = dialog_kb
luca_chat_kb = dialog_chat_kb
luca_char_kb = dialog_char_kb
silas_kb = psycho_kb
silas_chat_kb = psycho_chat_kb
silas_dur_kb = psycho_dur_kb
silas_mood_kb = psycho_mood_kb
titus_kb = study_kb
titus_chat_kb = study_chat_kb
titus_steps_kb = study_steps_kb
