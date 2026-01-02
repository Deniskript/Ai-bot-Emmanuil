from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🚀 Душа AI"), KeyboardButton(text="📕 Мой Кабинет")],
        [KeyboardButton(text="💎 Оплата"), KeyboardButton(text="❓ Помощь")]
    ], resize_keyboard=True)


def bots_menu_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💭 Диалог"), KeyboardButton(text="🛋️ Психолог"), KeyboardButton(text="📓 Обучение")],
        [KeyboardButton(text="◀️ Главное меню")]
    ], resize_keyboard=True)


def dialog_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💬 Начать диалог"), KeyboardButton(text="🌓 Характер")],
        [KeyboardButton(text="🗑 Очистить"), KeyboardButton(text="❓ Помощь")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)


def dialog_chat_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛑 Завершить"), KeyboardButton(text="🗑 Очистить")]
    ], resize_keyboard=True)


def dialog_char_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🙏 Поддержка"), KeyboardButton(text="🔥 Мотивация"), KeyboardButton(text="⚡️ Решение")],
        [KeyboardButton(text="◀️ Назад к Диалогу")]
    ], resize_keyboard=True)


def psycho_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛋️ Начать сеанс"), KeyboardButton(text="📔 Настроение")],
        [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)


def psycho_chat_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛑 Завершить"), KeyboardButton(text="🗑 Очистить")]
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


def study_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Новый курс"), KeyboardButton(text="📂 Ваши курсы")],
        [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)


def study_chat_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛑 Завершить"), KeyboardButton(text="🗑 Очистить")]
    ], resize_keyboard=True)


def study_steps_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🚀 10 шагов"), KeyboardButton(text="📘 40 шагов")],
        [KeyboardButton(text="📖 80 шагов")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)


def back_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)


def courses_action_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="▶️ Продолжить курс"), KeyboardButton(text="🗑 Удалить курс")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)


def courses_list_kb(courses):
    kb = []
    for i, c in enumerate(courses[:5], 1):
        kb.append([KeyboardButton(text=f"{i}. {c['name'][:20]}")])
    kb.append([KeyboardButton(text="◀️ Назад")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# === Алиасы для совместимости (можно удалить позже) ===
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


def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⌛️ Отменить запрос")]
    ], resize_keyboard=True)
