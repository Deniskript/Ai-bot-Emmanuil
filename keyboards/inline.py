from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CHANNEL_URL, SUPPORT_URL

def cabinet_keyboard(mem_on):
    mem_text = "🧠 Память: ВКЛ" if mem_on else "🧠 Память: ВЫКЛ"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup_balance")],
        [InlineKeyboardButton(text=mem_text, callback_data="toggle_memory")],
        [InlineKeyboardButton(text="🗑 Очистить память", callback_data="clear_memory")]
    ])

def confirm_clear_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, очистить", callback_data="confirm_clear")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_clear")]
    ])

def topup_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥉 45 000 токенов • 300 ₽", callback_data="buy:45000")],
        [InlineKeyboardButton(text="🥈 90 000 токенов • 600 ₽", callback_data="buy:90000")],
        [InlineKeyboardButton(text="🥇 180 000 токенов • 900 ₽", callback_data="buy:180000")],
        [InlineKeyboardButton(text="💬 Оплатить", url=SUPPORT_URL)]
    ])

def help_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Наш канал", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="🆘 Поддержка", url=SUPPORT_URL)]
    ])

def long_response_keyboard(url: str, rid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Отфильтрованный ответ", callback_data=f"filter:{rid}")],
        [InlineKeyboardButton(text="💬 Просмотреть весь диалог", url=url)]
    ])

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Выдать токены", callback_data="admin_give")],
        [InlineKeyboardButton(text="👤 Найти пользователя", callback_data="admin_find")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔧 Тех. работы", callback_data="admin_maint")],
        [InlineKeyboardButton(text="🗿 Антиспам", callback_data="admin_spam")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")]
    ])

def admin_cancel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
    ])

def admin_back():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])

def give_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥉 +45 000 токенов", callback_data="give:45000")],
        [InlineKeyboardButton(text="🥈 +90 000 токенов", callback_data="give:90000")],
        [InlineKeyboardButton(text="🥇 +180 000 токенов", callback_data="give:180000")],
        [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="give_custom")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
    ])

def maint_keyboard(on):
    text = "🟢 Выключить тех. работы" if on else "🔴 Включить тех. работы"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data="toggle_maint")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])

def bc_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить всем", callback_data="bc_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
    ])

def user_keyboard(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Выдать токены", callback_data=f"adm_give:{uid}")],
        [InlineKeyboardButton(text="🧠 Посмотреть память", callback_data=f"adm_mem:{uid}")],
        [InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"adm_block:{uid}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])

def spam_keyboard(settings):
    on = settings.get('enabled', True)
    status = "🟢 ВКЛ" if on else "🔴 ВЫКЛ"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🛡 Антиспам: {status}", callback_data="spam_toggle")],
        [InlineKeyboardButton(text=f"⏱ Интервал: {settings.get('interval', 2)} сек", callback_data="spam_interval")],
        [InlineKeyboardButton(text=f"🔄 Макс. запросов: {settings.get('max_requests', 1)}", callback_data="spam_max")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])

def spam_interval_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ 1 сек", callback_data="set_interval:1"),
         InlineKeyboardButton(text="🔹 2 сек", callback_data="set_interval:2")],
        [InlineKeyboardButton(text="🔸 3 сек", callback_data="set_interval:3"),
         InlineKeyboardButton(text="🔶 5 сек", callback_data="set_interval:5")],
        [InlineKeyboardButton(text="🔴 10 сек", callback_data="set_interval:10")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_spam")]
    ])

def spam_max_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ 1 запрос", callback_data="set_max:1"),
         InlineKeyboardButton(text="2️⃣ 2 запроса", callback_data="set_max:2")],
        [InlineKeyboardButton(text="3️⃣ 3 запроса", callback_data="set_max:3"),
         InlineKeyboardButton(text="5️⃣ 5 запросов", callback_data="set_max:5")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_spam")]
    ])

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Начать диалог", callback_data="start_dialog")],
        [InlineKeyboardButton(text="👤 Мой кабинет", callback_data="my_cabinet")],
        [InlineKeyboardButton(text="💎 Пополнить", callback_data="top_up")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])
