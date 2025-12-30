from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUPPORT_URL

def agree_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принимаю", callback_data="agree_yes")],
        [InlineKeyboardButton(text="❌ Отказываюсь", callback_data="agree_no")]
    ])

def bots_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑 Luca", callback_data="bot:luca"),
         InlineKeyboardButton(text="🧠 Silas", callback_data="bot:silas")],
        [InlineKeyboardButton(text="📚 Titus", callback_data="bot:titus")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def luca_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Диалог", callback_data="luca:start"),
         InlineKeyboardButton(text="🎭 Характер", callback_data="luca:char")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="help:luca"),
         InlineKeyboardButton(text="🏠 Меню", callback_data="back_main")]
    ])

def luca_char_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💖 Душевный", callback_data="char:душевный")],
        [InlineKeyboardButton(text="😐 Серьёзный", callback_data="char:серьезный")],
        [InlineKeyboardButton(text="🧑 Человек", callback_data="char:человек")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bot:luca")]
    ])

def silas_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Сеанс", callback_data="silas:session"),
         InlineKeyboardButton(text="📔 Дневник", callback_data="silas:diary")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="help:silas"),
         InlineKeyboardButton(text="◀️ Назад", callback_data="emmanuil")]
    ])

def silas_dur_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕐 20 мин", callback_data="ses:20")],
        [InlineKeyboardButton(text="🕑 40 мин", callback_data="ses:40")],
        [InlineKeyboardButton(text="🕐 60 мин", callback_data="ses:60")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bot:silas")]
    ])

def silas_diary_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😊 Хорошо/Спокойно", callback_data="mood:good")],
        [InlineKeyboardButton(text="😔 Устал/Пусто", callback_data="mood:tired")],
        [InlineKeyboardButton(text="😰 Больно/Страшно", callback_data="mood:pain")],
        [InlineKeyboardButton(text="✏️ Своё", callback_data="mood:custom")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="silas:stats")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bot:silas")]
    ])

def titus_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Новый курс", callback_data="titus:new"),
         InlineKeyboardButton(text="📂 Мои курсы", callback_data="titus:list")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="help:titus"),
         InlineKeyboardButton(text="◀️ Назад", callback_data="emmanuil")]
    ])

def titus_steps_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 10 шагов", callback_data="steps:10")],
        [InlineKeyboardButton(text="📘 40 шагов", callback_data="steps:40")],
        [InlineKeyboardButton(text="📖 80 шагов", callback_data="steps:80")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="bot:titus")]
    ])

def help_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑 Про Luca", callback_data="help:luca")],
        [InlineKeyboardButton(text="🧠 Про Silas", callback_data="help:silas")],
        [InlineKeyboardButton(text="📚 Про Titus", callback_data="help:titus")],
        [InlineKeyboardButton(text="💳 Как оплатить", callback_data="help:pay")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def topup_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥉 45 000 — 300₽", callback_data="buy:45000")],
        [InlineKeyboardButton(text="🥈 90 000 — 600₽", callback_data="buy:90000")],
        [InlineKeyboardButton(text="🥇 180 000 — 900₽", callback_data="buy:180000")],
        [InlineKeyboardButton(text="💬 Оплатить", url=SUPPORT_URL)]
    ])

def cabinet_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить", callback_data="topup")]
    ])

def back_kb(to: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=to)]
    ])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Выдать токены", callback_data="adm:give"),
         InlineKeyboardButton(text="👤 Найти", callback_data="adm:find")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm:bc"),
         InlineKeyboardButton(text="🔧 Тех.работы", callback_data="adm:maint")],
        [InlineKeyboardButton(text="🗿 Антиспам", callback_data="adm:spam")],
        [InlineKeyboardButton(text="🤖 Состояние ботов", callback_data="adm:bots")],
        [InlineKeyboardButton(text="📊 Нагрузка", callback_data="adm:load")],
        [InlineKeyboardButton(text="📈 Статистика", callback_data="adm:stats")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm:close")]
    ])

def admin_bots_kb(l, s, t):
    e = lambda x: "🟢" if x else "🔴"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{e(l)} Luca", callback_data="botcfg:luca")],
        [InlineKeyboardButton(text=f"{e(s)} Silas", callback_data="botcfg:silas")],
        [InlineKeyboardButton(text=f"{e(t)} Titus", callback_data="botcfg:titus")],
        [InlineKeyboardButton(text="🔄 Проверить", callback_data="adm:bots")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def bot_cfg_kb(bot: str, enabled: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Выключить" if enabled else "🟢 Включить", callback_data=f"tog:{bot}")],
        [InlineKeyboardButton(text="🔄 Сменить модель", callback_data=f"model:{bot}")],
        [InlineKeyboardButton(text="📝 Изменить версию", callback_data=f"ver:{bot}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:bots")]
    ])

def user_manage_kb(uid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Выдать токены", callback_data=f"give:{uid}")],
        [InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"block:{uid}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def give_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥉 +45 000", callback_data="gadd:45000")],
        [InlineKeyboardButton(text="🥈 +90 000", callback_data="gadd:90000")],
        [InlineKeyboardButton(text="🥇 +180 000", callback_data="gadd:180000")],
        [InlineKeyboardButton(text="✏️ Другое", callback_data="gadd:custom")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def confirm_bc_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="bc:send")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:back")]
    ])
