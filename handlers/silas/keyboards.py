"""
Клавиатуры для Silas (Психолог)
"""
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)


# ========== REPLY КЛАВИАТУРЫ ==========

def psycho_kb(user_id: int):
    """Главное меню психолога"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛋️ Начать сессию"), KeyboardButton(text="☕️ Настроиться", web_app=WebAppInfo(url=f"https://soul-bot.ru/silas/settings?user_id={user_id}"))],
        [KeyboardButton(text="📖 Как это работает?", web_app=WebAppInfo(url=f"https://soul-bot.ru/how-it-works/psychologist?user_id={user_id}")), KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)


def psycho_chat_kb():
    """Клавиатура в активном сеансе"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛑 Завершить")]
    ], resize_keyboard=True)


def psycho_chat_loading_kb():
    """Клавиатура при обработке запроса"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⌛️ Отменить запрос")]
    ], resize_keyboard=True)


def psycho_dur_kb():
    """Выбор длительности сеанса"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="15 минут"), KeyboardButton(text="30 минут"), KeyboardButton(text="60 минут")],
        [KeyboardButton(text="◀️ Назад к Психологу")]
    ], resize_keyboard=True)


def psycho_mood_kb():
    """Дневник настроения"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Хорошо"), KeyboardButton(text="Устал"), KeyboardButton(text="Тяжело")],
        [KeyboardButton(text="✏️ Ваше настроение"), KeyboardButton(text="Статистика")],
        [KeyboardButton(text="◀️ Назад к Психологу")]
    ], resize_keyboard=True)


# ========== INLINE КЛАВИАТУРЫ ==========

def silas_msg_kb(has_telegraph: bool = False):
    """Inline клавиатура для сообщений психолога"""
    if has_telegraph:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Telegraph", callback_data="silas:tg")]
        ])
    return None
