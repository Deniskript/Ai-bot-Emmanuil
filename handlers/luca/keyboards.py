"""
Клавиатуры для Luka (Soul AI)
"""
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)


# ========== REPLY КЛАВИАТУРЫ ==========

def dialog_kb(user_id: int):
    """Главное меню диалога"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💬 Начать"), KeyboardButton(text="☕️ Настроиться", web_app=WebAppInfo(url=f"https://soul-bot.ru/luca/settings?user_id={user_id}"))],
        [KeyboardButton(text="🧹 Очистить"), KeyboardButton(text="📖 Как это работает?", web_app=WebAppInfo(url=f"https://soul-bot.ru/how-it-works/dialog-new?user_id={user_id}"))],
        [KeyboardButton(text="◀️ Назад")]
    ], resize_keyboard=True)


def dialog_chat_kb():
    """Клавиатура в активном чате"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛑 Завершить"), KeyboardButton(text="🧹 Очистить")]
    ], resize_keyboard=True)


def dialog_chat_loading_kb():
    """Клавиатура при обработке запроса"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⌛️ Отменить запрос")]
    ], resize_keyboard=True)


def dialog_char_kb():
    """Выбор характера/режима"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🕊 Душа"), KeyboardButton(text="💡 Разум")],
        [KeyboardButton(text="🎤 Голос")],
        [KeyboardButton(text="◀️ Назад к Диалогу")]
    ], resize_keyboard=True)


def voice_chat_kb():
    """Клавиатура для голосового режима"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛑 Завершить"), KeyboardButton(text="🧹 Очистить")],
        [KeyboardButton(text="🔄 Сменить голос")]
    ], resize_keyboard=True)


def voice_chat_loading_kb():
    """Клавиатура при обработке запроса в голосовом режиме"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⌛️ Отменить запрос")]
    ], resize_keyboard=True)


# ========== INLINE КЛАВИАТУРЫ ==========

def voice_gender_kb():
    """Выбор голоса для голосового режима"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Мужской", callback_data="voice:gender:male")],
        [InlineKeyboardButton(text="👩 Женский", callback_data="voice:gender:female")]
    ])
