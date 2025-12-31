from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🤖 Emmanuil AI"), KeyboardButton(text="👤 Кабинет")],
        [KeyboardButton(text="💰 Пополнить"), KeyboardButton(text="💡 Помощь")]
    ], resize_keyboard=True)
