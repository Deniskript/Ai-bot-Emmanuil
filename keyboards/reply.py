from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✨ Начать диалог"), KeyboardButton(text="👤 Мой кабинет")],
        [KeyboardButton(text="💰 Пополнить"), KeyboardButton(text="💡 Помощь")]
    ], resize_keyboard=True)
