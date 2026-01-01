from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def agree_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принимаю", callback_data="agree_yes")],
        [InlineKeyboardButton(text="❌ Отказываюсь", callback_data="agree_no")]
    ])


def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Боты", callback_data="bots"),
         InlineKeyboardButton(text="👤 Кабинет", callback_data="cabinet")],
        [InlineKeyboardButton(text="💰 Пополнить", callback_data="topup")]
    ])


async def get_bots_kb():
    from database import db
    luca = await db.get_button("luca")
    silas = await db.get_button("silas")
    titus = await db.get_button("titus")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{luca.get('emoji','📈')} {luca.get('text','Luca')}", callback_data="bot:luca"),
         InlineKeyboardButton(text=f"{silas.get('emoji','🗂')} {silas.get('text','Silas')}", callback_data="bot:silas")],
        [InlineKeyboardButton(text=f"{titus.get('emoji','📋')} {titus.get('text','Titus')}", callback_data="bot:titus"),
         InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])


def bots_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Luca", callback_data="bot:luca"),
         InlineKeyboardButton(text="🗂 Silas", callback_data="bot:silas")],
        [InlineKeyboardButton(text="📋 Titus", callback_data="bot:titus"),
         InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])


def cabinet_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить", callback_data="topup"),
         InlineKeyboardButton(text="📊 История", callback_data="history")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])


def topup_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50K — 50₽", callback_data="pay:50"),
         InlineKeyboardButton(text="150K — 150₽", callback_data="pay:150")],
        [InlineKeyboardButton(text="500K — 450₽", callback_data="pay:500")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])


def help_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Luca", callback_data="help:luca"),
         InlineKeyboardButton(text="🗂 Silas", callback_data="help:silas")],
        [InlineKeyboardButton(text="📋 Titus", callback_data="help:titus"),
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
        [InlineKeyboardButton(text="🎭 Характер", callback_data="luca:char"),
         InlineKeyboardButton(text="📖 Инструкция", callback_data="help:luca")],
        [InlineKeyboardButton(text="◀️ К ботам", callback_data="bots")]
    ])


def luca_char_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💛 Душевный", callback_data="char:душевный"),
         InlineKeyboardButton(text="📋 Серьезный", callback_data="char:серьезный")],
        [InlineKeyboardButton(text="🧑 Человек", callback_data="char:человек")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bot:luca")]
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
        [InlineKeyboardButton(text="😊 Хорошо", callback_data="mood:good"),
         InlineKeyboardButton(text="😔 Устал", callback_data="mood:tired")],
        [InlineKeyboardButton(text="😰 Больно", callback_data="mood:pain"),
         InlineKeyboardButton(text="✏️ Своё", callback_data="mood:custom")],
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
        [InlineKeyboardButton(text="🚀 10 шагов", callback_data="steps:10"),
         InlineKeyboardButton(text="📘 40 шагов", callback_data="steps:40")],
        [InlineKeyboardButton(text="📖 80 шагов", callback_data="steps:80")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bot:titus")]
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


def admin_bots_kb(l, s, t):
    el = "🟢" if l else "🔴"
    es = "🟢" if s else "🔴"
    et = "🟢" if t else "🔴"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{el} Luca", callback_data="botcfg:luca"),
         InlineKeyboardButton(text=f"{es} Silas", callback_data="botcfg:silas")],
        [InlineKeyboardButton(text=f"{et} Titus", callback_data="botcfg:titus")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])


def bot_cfg_kb(bot: str, enabled: bool, current_model: str = ""):
    e = "🔴 Выключить" if enabled else "🟢 Включить"
    is_gpt = current_model.startswith("gpt") if current_model else True
    gpt_mark = "🟢" if is_gpt else "⚪"
    claude_mark = "🟢" if not is_gpt else "⚪"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=e, callback_data=f"tog:{bot}")],
        [InlineKeyboardButton(text=f"{gpt_mark} GPT", callback_data=f"prov:{bot}:gpt"),
         InlineKeyboardButton(text=f"{claude_mark} Claude", callback_data=f"prov:{bot}:claude")],
        [InlineKeyboardButton(text="📝 Версия", callback_data=f"ver:{bot}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:bots")]
    ])


def gpt_models_kb(bot: str, current: str = ""):
    def mark(m):
        return "✅" if current == m else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"o4-mini {mark('o4-mini-2025-04-16')}", callback_data=f"setm:{bot}:o4-mini-2025-04-16")],
        [InlineKeyboardButton(text=f"o3 {mark('o3-2025-04-16')}", callback_data=f"setm:{bot}:o3-2025-04-16"),
         InlineKeyboardButton(text=f"o3-mini {mark('o3-mini-2025-01-31')}", callback_data=f"setm:{bot}:o3-mini-2025-01-31")],
        [InlineKeyboardButton(text=f"o3-pro {mark('o3-pro-2025-06-10')}", callback_data=f"setm:{bot}:o3-pro-2025-06-10"),
         InlineKeyboardButton(text=f"o1 {mark('o1-2024-12-17')}", callback_data=f"setm:{bot}:o1-2024-12-17")],
        [InlineKeyboardButton(text=f"gpt-5.2 {mark('gpt-5.2-chat-latest')}", callback_data=f"setm:{bot}:gpt-5.2-chat-latest"),
         InlineKeyboardButton(text=f"gpt-5.1 {mark('gpt-5.1-chat-latest')}", callback_data=f"setm:{bot}:gpt-5.1-chat-latest")],
        [InlineKeyboardButton(text=f"gpt-5 {mark('gpt-5-chat-latest')}", callback_data=f"setm:{bot}:gpt-5-chat-latest"),
         InlineKeyboardButton(text=f"gpt-5-mini {mark('gpt-5-mini-2025-08-07')}", callback_data=f"setm:{bot}:gpt-5-mini-2025-08-07")],
        [InlineKeyboardButton(text=f"gpt-4.1 {mark('gpt-4.1-2025-04-14')}", callback_data=f"setm:{bot}:gpt-4.1-2025-04-14"),
         InlineKeyboardButton(text=f"gpt-4.1-mini {mark('gpt-4.1-mini-2025-04-14')}", callback_data=f"setm:{bot}:gpt-4.1-mini-2025-04-14")],
        [InlineKeyboardButton(text=f"gpt-4o {mark('gpt-4o')}", callback_data=f"setm:{bot}:gpt-4o"),
         InlineKeyboardButton(text=f"gpt-4o-mini {mark('gpt-4o-mini')}", callback_data=f"setm:{bot}:gpt-4o-mini")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"botcfg:{bot}")]
    ])


def claude_models_kb(bot: str, current: str = ""):
    def mark(m):
        return "✅" if current == m else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"claude-sonnet-4.5 {mark('claude-sonnet-4-5-20250929')}", callback_data=f"setm:{bot}:claude-sonnet-4-5-20250929")],
        [InlineKeyboardButton(text=f"claude-opus-4.5 {mark('claude-opus-4-5-20251101')}", callback_data=f"setm:{bot}:claude-opus-4-5-20251101")],
        [InlineKeyboardButton(text=f"claude-opus-4.1 {mark('claude-opus-4-1-20250805')}", callback_data=f"setm:{bot}:claude-opus-4-1-20250805")],
        [InlineKeyboardButton(text=f"claude-opus-4 {mark('claude-opus-4-20250514')}", callback_data=f"setm:{bot}:claude-opus-4-20250514")],
        [InlineKeyboardButton(text=f"claude-sonnet-4 {mark('claude-sonnet-4-20250514')}", callback_data=f"setm:{bot}:claude-sonnet-4-20250514")],
        [InlineKeyboardButton(text=f"claude-3.7-sonnet {mark('claude-3-7-sonnet-20250219')}", callback_data=f"setm:{bot}:claude-3-7-sonnet-20250219")],
        [InlineKeyboardButton(text=f"claude-haiku-4.5 {mark('claude-haiku-4-5-20251001')}", callback_data=f"setm:{bot}:claude-haiku-4-5-20251001")],
        [InlineKeyboardButton(text=f"claude-3.5-haiku {mark('claude-3-5-haiku-20241022')}", callback_data=f"setm:{bot}:claude-3-5-haiku-20241022")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"botcfg:{bot}")]
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
        [InlineKeyboardButton(text="✅ Отправить", callback_data="bc:send"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="adm:back")]
    ])


def user_manage_kb(uid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"block:{uid}"),
         InlineKeyboardButton(text="💎 Выдать токены", callback_data="adm:give")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])


def editor_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Тексты", callback_data="edit:texts"),
         InlineKeyboardButton(text="🔘 Кнопки", callback_data="edit:buttons")],
        [InlineKeyboardButton(text="🖼 Медиа", callback_data="edit:media"),
         InlineKeyboardButton(text="💾 Git бэкап", callback_data="edit:git")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])


def texts_list_kb(texts: list):
    kb = []
    for t in texts[:10]:
        kb.append([InlineKeyboardButton(text=f"📝 {t['key'][:20]}", callback_data=f"txt:{t['key'][:30]}")])
    kb.append([InlineKeyboardButton(text="➕ Добавить", callback_data="txt:add")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:editor")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def buttons_list_kb(buttons: list):
    kb = []
    for b in buttons[:10]:
        kb.append([InlineKeyboardButton(text=f"{b['emoji']} {b['text'][:15]}", callback_data=f"btn:{b['key'][:30]}")])
    kb.append([InlineKeyboardButton(text="➕ Добавить", callback_data="btn:add")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:editor")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def media_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 Приветствие /start", callback_data="media:start")],
        [InlineKeyboardButton(text="🖼 Luca", callback_data="media:luca"),
         InlineKeyboardButton(text="🖼 Silas", callback_data="media:silas")],
        [InlineKeyboardButton(text="🖼 Titus", callback_data="media:titus")],
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
        [InlineKeyboardButton(text="✅ Сохранить", callback_data="git:save"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="adm:editor")]
    ])


def text_edit_kb(key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить", callback_data=f"txte:{key}"),
         InlineKeyboardButton(text="🗑 Удалить", callback_data=f"txtd:{key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="edit:texts")]
    ])


def button_edit_kb(key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😀 Эмодзи", callback_data=f"btne:{key}"),
         InlineKeyboardButton(text="✏️ Текст", callback_data=f"btnt:{key}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"btnd:{key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="edit:buttons")]
    ])
