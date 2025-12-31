from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def agree_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принимаю", callback_data="agree_yes")],
        [InlineKeyboardButton(text="❌ Отказываюсь", callback_data="agree_no")]
    ])

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Боты", callback_data="bots")],
        [InlineKeyboardButton(text="👤 Кабинет", callback_data="cabinet")],
        [InlineKeyboardButton(text="💰 Пополнить", callback_data="topup")]
    ])

async def get_bots_kb():
    from database import db
    luca = await db.get_button("luca")
    silas = await db.get_button("silas") 
    titus = await db.get_button("titus")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{luca.get('emoji','🧑')} {luca.get('text','Luca')}", callback_data="bot:luca")],
        [InlineKeyboardButton(text=f"{silas.get('emoji','🧠')} {silas.get('text','Silas')}", callback_data="bot:silas")],
        [InlineKeyboardButton(text=f"{titus.get('emoji','📚')} {titus.get('text','Titus')}", callback_data="bot:titus")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def bots_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑 Luca — друг", callback_data="bot:luca")],
        [InlineKeyboardButton(text="🧠 Silas — эксперт", callback_data="bot:silas")],
        [InlineKeyboardButton(text="📚 Titus — учитель", callback_data="bot:titus")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def cabinet_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить", callback_data="topup")],
        [InlineKeyboardButton(text="📊 История", callback_data="history")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def topup_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50K — 50₽", callback_data="pay:50")],
        [InlineKeyboardButton(text="150K — 150₽", callback_data="pay:150")],
        [InlineKeyboardButton(text="500K — 450₽", callback_data="pay:500")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def help_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑 Luca", callback_data="help:luca"),
         InlineKeyboardButton(text="🧠 Silas", callback_data="help:silas")],
        [InlineKeyboardButton(text="📚 Titus", callback_data="help:titus"),
         InlineKeyboardButton(text="💳 Оплата", callback_data="help:pay")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def back_kb(cb_data: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=cb_data)]
    ])

def luca_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Начать диалог", callback_data="luca:start")],
        [InlineKeyboardButton(text="🎭 Характер", callback_data="luca:char")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="help:luca")],
        [InlineKeyboardButton(text="◀️ К ботам", callback_data="bots")]
    ])

def luca_char_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 Душевный", callback_data="char:душевный")],
        [InlineKeyboardButton(text="📋 Серьезный", callback_data="char:серьезный")],
        [InlineKeyboardButton(text="🧑 Человек", callback_data="char:человек")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bot:luca")]
    ])

def silas_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Начать диалог", callback_data="silas:start")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="help:silas")],
        [InlineKeyboardButton(text="◀️ К ботам", callback_data="bots")]
    ])

def titus_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Начать диалог", callback_data="titus:start")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="help:titus")],
        [InlineKeyboardButton(text="◀️ К ботам", callback_data="bots")]
    ])


def admin_bots_kb(l, s, t):
    el = "🟢" if l else "🔴"
    es = "🟢" if s else "🔴"
    et = "🟢" if t else "🔴"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{el} Luca", callback_data="botcfg:luca")],
        [InlineKeyboardButton(text=f"{es} Silas", callback_data="botcfg:silas")],
        [InlineKeyboardButton(text=f"{et} Titus", callback_data="botcfg:titus")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def spam_kb(interval: int, max_pm: int, blocked: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⏱ Интервал: {interval} сек", callback_data="sp:info")],
        [InlineKeyboardButton(text="➖", callback_data="sp:int:-1"),
         InlineKeyboardButton(text="➕", callback_data="sp:int:+1")],
        [InlineKeyboardButton(text=f"📨 Макс/мин: {max_pm}", callback_data="sp:info")],
        [InlineKeyboardButton(text="➖", callback_data="sp:rpm:-1"),
         InlineKeyboardButton(text="➕", callback_data="sp:rpm:+1")],
        [InlineKeyboardButton(text=f"🚫 Заблокировано: {blocked}", callback_data="spam:list")],
        [InlineKeyboardButton(text="🔓 Разблокировать", callback_data="spam:unblock")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def bot_cfg_kb(bot: str, enabled: bool):
    e = "🔴 Выключить" if enabled else "🟢 Включить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=e, callback_data=f"tog:{bot}")],
        [InlineKeyboardButton(text="🔄 Модель", callback_data=f"model:{bot}")],
        [InlineKeyboardButton(text="📝 Версия", callback_data=f"ver:{bot}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:bots")]
    ])

def give_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="10K", callback_data="gadd:10000"),
         InlineKeyboardButton(text="50K", callback_data="gadd:50000")],
        [InlineKeyboardButton(text="100K", callback_data="gadd:100000"),
         InlineKeyboardButton(text="500K", callback_data="gadd:500000")],
        [InlineKeyboardButton(text="✏️ Своё", callback_data="gadd:custom")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def confirm_bc_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="bc:send")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:back")]
    ])

def user_manage_kb(uid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"block:{uid}")],
        [InlineKeyboardButton(text="💎 Выдать токены", callback_data="adm:give")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def silas_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📔 Дневник настроения", callback_data="silas:diary")],
        [InlineKeyboardButton(text="🎯 Начать сеанс", callback_data="silas:session")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="help:silas")],
        [InlineKeyboardButton(text="◀️ К ботам", callback_data="bots")]
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

def silas_dur_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="15 мин", callback_data="ses:15"),
         InlineKeyboardButton(text="30 мин", callback_data="ses:30")],
        [InlineKeyboardButton(text="45 мин", callback_data="ses:45"),
         InlineKeyboardButton(text="60 мин", callback_data="ses:60")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bot:silas")]
    ])

def titus_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Новый курс", callback_data="titus:new")],
        [InlineKeyboardButton(text="📂 Мои курсы", callback_data="titus:list")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="help:titus")],
        [InlineKeyboardButton(text="◀️ К ботам", callback_data="bots")]
    ])

def titus_steps_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 10 шагов (обзор)", callback_data="steps:10")],
        [InlineKeyboardButton(text="📘 40 шагов (стандарт)", callback_data="steps:40")],
        [InlineKeyboardButton(text="📖 80 шагов (глубокий)", callback_data="steps:80")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bot:titus")]
    ])

def models_kb(bot: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="GPT-4o", callback_data=f"setm:{bot}:gpt-4o")],
        [InlineKeyboardButton(text="GPT-4o mini", callback_data=f"setm:{bot}:gpt-4o-mini")],
        [InlineKeyboardButton(text="GPT-4 Turbo", callback_data=f"setm:{bot}:gpt-4-turbo")],
        [InlineKeyboardButton(text="Claude 3 Opus", callback_data=f"setm:{bot}:claude-3-opus")],
        [InlineKeyboardButton(text="Claude 3 Sonnet", callback_data=f"setm:{bot}:claude-3-sonnet")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"botcfg:{bot}")]
    ])

def editor_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Тексты", callback_data="edit:texts")],
        [InlineKeyboardButton(text="🔘 Кнопки", callback_data="edit:buttons")],
        [InlineKeyboardButton(text="🖼 Медиа", callback_data="edit:media")],
        [InlineKeyboardButton(text="💾 Git бэкап", callback_data="edit:git")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def texts_list_kb(texts: list):
    kb = []
    for t in texts[:10]:
        kb.append([InlineKeyboardButton(
            text=f"📝 {t['key'][:20]}", 
            callback_data=f"txt:{t['key'][:30]}")])
    kb.append([InlineKeyboardButton(text="➕ Добавить", callback_data="txt:add")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:editor")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def buttons_list_kb(buttons: list):
    kb = []
    for b in buttons[:10]:
        kb.append([InlineKeyboardButton(
            text=f"{b['emoji']} {b['text'][:15]}", 
            callback_data=f"btn:{b['key'][:30]}")])
    kb.append([InlineKeyboardButton(text="➕ Добавить", callback_data="btn:add")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:editor")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def media_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 Приветствие /start", callback_data="media:start")],
        [InlineKeyboardButton(text="🖼 Luca приветствие", callback_data="media:luca")],
        [InlineKeyboardButton(text="🖼 Silas приветствие", callback_data="media:silas")],
        [InlineKeyboardButton(text="🖼 Titus приветствие", callback_data="media:titus")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:editor")]
    ])

def media_edit_kb(key: str, has_media: bool):
    kb = [[InlineKeyboardButton(text="📤 Загрузить", callback_data=f"mup:{key}")]]
    if has_media:
        kb.append([InlineKeyboardButton(text="🗑 Удалить", callback_data=f"mdel:{key}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="edit:media")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def confirm_git_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сохранить", callback_data="git:save")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:editor")]
    ])

def text_edit_kb(key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить", callback_data=f"txte:{key}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"txtd:{key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="edit:texts")]
    ])

def button_edit_kb(key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😀 Эмодзи", callback_data=f"btne:{key}")],
        [InlineKeyboardButton(text="✏️ Текст", callback_data=f"btnt:{key}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"btnd:{key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="edit:buttons")]
    ])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats"),
         InlineKeyboardButton(text="📈 Нагрузка", callback_data="adm:load")],
        [InlineKeyboardButton(text="🤖 Боты", callback_data="adm:bots"),
         InlineKeyboardButton(text="🛡 Антифлуд", callback_data="adm:spam")],
        [InlineKeyboardButton(text="👥 Юзеры", callback_data="adm:users"),
         InlineKeyboardButton(text="🔍 Поиск", callback_data="adm:find")],
        [InlineKeyboardButton(text="💎 Выдать", callback_data="adm:give"),
         InlineKeyboardButton(text="📢 Рассылка", callback_data="adm:bc")],
        [InlineKeyboardButton(text="✏️ Редактор", callback_data="adm:editor")],
        [InlineKeyboardButton(text="🔧 Тех.работы", callback_data="adm:maint")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm:close")]
    ])
