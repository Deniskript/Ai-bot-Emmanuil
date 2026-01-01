from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🚀   Emmanuil AI"), KeyboardButton(text="📕 Мой Кабинет")],
        [KeyboardButton(text="⚡️ Пополнить баланс"), KeyboardButton(text="⚠️ Помошь")]
    ], resize_keyboard=True)


def bots_menu_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💭Luca"), KeyboardButton(text="🛋️ Silas"), KeyboardButton(text="📓 Titus")],
        [KeyboardButton(text="◀️ Главное меню")]
    ], resize_keyboard=True)


def luca_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Новый курс"), KeyboardButton(text="🎚️ Характер")],
        [KeyboardButton(text="🗑 Очистить"), KeyboardButton(text="❓ Помощь")],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)


def luca_chat_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛑 Завершить"), KeyboardButton(text="🗑 Очистить")]
    ], resize_keyboard=True)


def luca_char_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🙏 Заботливый"), KeyboardButton(text="💯 Строгий"), KeyboardButton(text="💭 Нейтральный")],
        [KeyboardButton(text="◀️ Назад к Luca")]
    ], resize_keyboard=True)


def silas_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛋️ Начать сеанс"), KeyboardButton(text="📔 Настроение")],
        [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)


def silas_chat_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛑 Завершить"), KeyboardButton(text="🗑 Очистить")]
    ], resize_keyboard=True)


def silas_dur_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="15 минут"), KeyboardButton(text="30 минут"), KeyboardButton(text="60 минут")],
        [KeyboardButton(text="◀️ Назад к Silas")]
    ], resize_keyboard=True)


def silas_mood_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Хорошо"), KeyboardButton(text="Устал"), KeyboardButton(text="Тяжело")],
        [KeyboardButton(text="✏️Ваше настроение"), KeyboardButton(text="Статистика")],
        [KeyboardButton(text="◀️ Назад к Silas")]
    ], resize_keyboard=True)


def titus_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Новый курс"), KeyboardButton(text="📂 Ваши курсы")],
        [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)


def titus_chat_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛑 Завершить"), KeyboardButton(text="🗑 Очистить")]
    ], resize_keyboard=True)


def titus_steps_kb():
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
