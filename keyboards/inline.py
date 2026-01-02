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


def bots_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💭 Диалог", callback_data="bot:dialog"),
         InlineKeyboardButton(text="🛋️ Психолог", callback_data="bot:psycho")],
        [InlineKeyboardButton(text="📓 Обучение", callback_data="bot:study"),
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
        [InlineKeyboardButton(text="💭 Диалог", callback_data="help:dialog"),
         InlineKeyboardButton(text="🛋️ Психолог", callback_data="help:psycho")],
        [InlineKeyboardButton(text="📓 Обучение", callback_data="help:study"),
         InlineKeyboardButton(text="💳 Оплата", callback_data="help:pay")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])


def back_kb(cb_data: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=cb_data)]
    ])


# === АДМИНКА ===

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
        [InlineKeyboardButton(text="✏️ Редактор", callback_data="adm:editor"),
         InlineKeyboardButton(text="🧠 Память", callback_data="adm:memory")],
        [InlineKeyboardButton(text="🔧 Тех.работы", callback_data="adm:maint")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm:close")]
    ])



def admin_bots_kb(d, p, s):
    ed = "🟢" if d else "🔴"
    ep = "🟢" if p else "🔴"
    es = "🟢" if s else "🔴"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{ed} Диалог", callback_data="botcfg:luca"),
         InlineKeyboardButton(text=f"{ep} Психолог", callback_data="botcfg:silas")],
        [InlineKeyboardButton(text=f"{es} Обучение", callback_data="botcfg:titus")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])


def bot_cfg_kb(bot: str, enabled: bool, current_model: str = ""):
    e = "🔴 Выключить" if enabled else "🟢 Включить"
    is_gpt = current_model.startswith("gpt") or current_model.startswith("o") if current_model else True
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
        [InlineKeyboardButton(text=f"claude-sonnet-4 {mark('claude-sonnet-4-20250514')}", callback_data=f"setm:{bot}:claude-sonnet-4-20250514")],
        [InlineKeyboardButton(text=f"claude-opus-4 {mark('claude-opus-4-20250514')}", callback_data=f"setm:{bot}:claude-opus-4-20250514")],
        [InlineKeyboardButton(text=f"claude-3.7-sonnet {mark('claude-3-7-sonnet-20250219')}", callback_data=f"setm:{bot}:claude-3-7-sonnet-20250219")],
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
        [InlineKeyboardButton(text="🖼 Диалог", callback_data="media:luca"),
         InlineKeyboardButton(text="🖼 Психолог", callback_data="media:silas")],
        [InlineKeyboardButton(text="🖼 Обучение", callback_data="media:titus")],
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


# === TITUS кнопки под сообщениями ===

def titus_msg_kb(user_id: int, has_telegraph: bool = False):
    """Кнопки под сообщением Titus: Конспект + Telegraph"""
    kb = [[InlineKeyboardButton(text="📝 Конспект", callback_data=f"titus:summary:{user_id}")]]
    if has_telegraph:
        kb[0].append(InlineKeyboardButton(text="📖 Telegraph", callback_data=f"titus:tg:{user_id}"))
    return InlineKeyboardMarkup(inline_keyboard=kb)


def titus_telegraph_kb(url: str):
    """Кнопка для открытия Telegraph страницы"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Telegraph", url=url)]
    ])


# === LUCA кнопки под сообщениями ===

def luca_msg_kb(has_telegraph: bool = False):
    """Кнопка Telegraph под сообщением Luca"""
    if has_telegraph:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Telegraph", callback_data="luca:tg")]
        ])
    return None


# === SILAS кнопки под сообщениями ===

def silas_msg_kb(has_telegraph: bool = False):
    """Кнопка Telegraph под сообщением Silas"""
    if has_telegraph:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Telegraph", callback_data="silas:tg")]
        ])
    return None


# === ПАМЯТЬ АДМИН ===
def memory_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Память пользователей", callback_data="mem:list:0")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def memory_users_kb(users: list, page: int, total_pages: int):
    kb = []
    for u in users:
        name = f"@{u['username']}" if u.get('username') else str(u['user_id'])
        kb.append([InlineKeyboardButton(
            text=f"👤 {name} — {u.get('mem_count', 0)} ботов",
            callback_data=f"mem:user:{u['user_id']}"
        )])
    
    # Пагинация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"mem:list:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="mem:info"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"mem:list:{page+1}"))
    if nav:
        kb.append(nav)
    
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def memory_user_bots_kb(uid: int, bots: dict):
    kb = []
    bot_names = {'luca': '💭 Диалог', 'silas': '🧘 Психолог', 'titus': '📚 Репетитор'}
    for bot, facts in bots.items():
        name = bot_names.get(bot, bot)
        kb.append([InlineKeyboardButton(
            text=f"{name} — {len(facts)} фактов",
            callback_data=f"mem:bot:{uid}:{bot}"
        )])
    kb.append([InlineKeyboardButton(text="🗑 Очистить всё", callback_data=f"mem:clearall:{uid}")])
    kb.append([InlineKeyboardButton(text="◀️ К списку", callback_data="mem:list:0")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def memory_facts_kb(uid: int, bot: str, facts: list, page: int = 0):
    kb = []
    per_page = 5
    start = page * per_page
    end = min(start + per_page, len(facts))
    total_pages = (len(facts) + per_page - 1) // per_page
    
    for i in range(start, end):
        fact_short = facts[i][:30] + "..." if len(facts[i]) > 30 else facts[i]
        kb.append([
            InlineKeyboardButton(text=f"{i+1}. {fact_short}", callback_data=f"mem:view:{uid}:{bot}:{i}"),
            InlineKeyboardButton(text="🗑", callback_data=f"mem:del:{uid}:{bot}:{i}")
        ])
    
    # Пагинация фактов
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"mem:facts:{uid}:{bot}:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="mem:info"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"mem:facts:{uid}:{bot}:{page+1}"))
        kb.append(nav)
    
    kb.append([InlineKeyboardButton(text="➕ Добавить факт", callback_data=f"mem:add:{uid}:{bot}")])
    kb.append([InlineKeyboardButton(text="🗑 Очистить бота", callback_data=f"mem:clear:{uid}:{bot}")])
    kb.append([InlineKeyboardButton(text="◀️ К пользователю", callback_data=f"mem:user:{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def memory_fact_view_kb(uid: int, bot: str, idx: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"mem:edit:{uid}:{bot}:{idx}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"mem:del:{uid}:{bot}:{idx}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"mem:bot:{uid}:{bot}")]
    ])
