from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# === ОСНОВНЫЕ ===


# === ЗДОРОВЬЕ ===

def save_calories_kb():
    """Сохранить в журнал?"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Записать в журнал", callback_data="save_calories")],
        [InlineKeyboardButton(text="❌ Не записывать", callback_data="skip_calories")]
    ])

def goal_select_kb():
    """Выбор цели питания"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔻 Похудеть", callback_data="goal_lose")],
        [InlineKeyboardButton(text="⚖️ Поддержать вес", callback_data="goal_maintain")],
        [InlineKeyboardButton(text="🔺 Набрать массу", callback_data="goal_gain")]
    ])


# === ОСНОВНЫЕ ===

def agree_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принимаю", callback_data="agree_yes")],
        [InlineKeyboardButton(text="❌ Отказываюсь", callback_data="agree_no")]
    ])

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Боты", callback_data="bots"),
         InlineKeyboardButton(text="👤 Кабинет", callback_data="cabinet")],
        [InlineKeyboardButton(text="💎 Подписка", callback_data="subscription")]
    ])

def bots_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💭 Диалог", callback_data="bot:luca"),
         InlineKeyboardButton(text="🛋️ Психолог", callback_data="bot:silas")],
        [InlineKeyboardButton(text="📓 Обучение", callback_data="bot:titus")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def cabinet_kb(has_sub: bool = False):
    kb = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats")]
    ]
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def help_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💭 Диалог", callback_data="help:luca"),
         InlineKeyboardButton(text="🛋️ Психолог", callback_data="help:silas")],
        [InlineKeyboardButton(text="📓 Обучение", callback_data="help:titus"),
         InlineKeyboardButton(text="💳 Оплата", callback_data="help:pay")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def back_kb(cb_data: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=cb_data)]
    ])

# === ПОДПИСКА ===

def subscription_plans_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Mini (Sonnet) — 490₽", callback_data="sub:buy:mini")],
        [InlineKeyboardButton(text="👑 Standard (Opus) — 990₽", callback_data="sub:buy:standard")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def subscription_active_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Докупить токены", callback_data="sub:tokens")],
        [InlineKeyboardButton(text="📋 Сменить тариф", callback_data="sub:plans")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def tokens_packages_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 100K — 149₽", callback_data="tokens:buy:100k")],
        [InlineKeyboardButton(text="📦 200K — 249₽", callback_data="tokens:buy:200k")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="sub:back")]
    ])

def payment_kb(url: str, tx_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=url)],
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"pay:check:{tx_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="subscription")]
    ])

# === БОТЫ ===
# titus_msg_kb удалена - теперь используется get_titus_keyboard из utils/conversations.py

def luca_msg_kb(has_telegraph: bool = False):
    if has_telegraph:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Telegraph", callback_data="luca:tg")]
        ])
    return None

# silas_msg_kb перенесена в handlers/silas/keyboards.py (автономный модуль)

# === АНКЕТА ===

def gender_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Мужской", callback_data="gender:male")],
        [InlineKeyboardButton(text="👩 Женский", callback_data="gender:female")],
        [InlineKeyboardButton(text="🤷 Не указывать", callback_data="gender:skip")]
    ])

def skip_kb(callback: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data=callback)]
    ])

# ============================================
# === LUKA VOICE - ПЕРЕНЕСЕНО В handlers/luka/keyboards.py ===
# ============================================
# Функция voice_gender_kb теперь находится в автономном модуле handlers/luka/

# === АДМИНКА ===

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats"),
         InlineKeyboardButton(text="📈 Нагрузка", callback_data="adm:load")],
        [InlineKeyboardButton(text="💎 Подписки", callback_data="adm:sub"),
         InlineKeyboardButton(text="🛡 Антифлуд", callback_data="adm:spam")],
        [InlineKeyboardButton(text="👥 Юзеры", callback_data="adm:users"),
         InlineKeyboardButton(text="🔍 Поиск", callback_data="adm:find")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm:bc"),
         InlineKeyboardButton(text="🧠 Память", callback_data="adm:memory")],
        [InlineKeyboardButton(text="📝 Промпты", callback_data="adm:prompts"),
         InlineKeyboardButton(text="📊 Мониторинг", callback_data="adm:monitor")],
        [InlineKeyboardButton(text="👑 Моя подписка", callback_data="adm:mysub"),
         InlineKeyboardButton(text="💾 Git", callback_data="adm:git")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm:close")]
    ])

# Антифлуд
def spam_kb(interval: int, max_rpm: int, blocked: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⏱ Интервал: {interval}с", callback_data="sp:info")],
        [InlineKeyboardButton(text="➖", callback_data="sp:int:-1"),
         InlineKeyboardButton(text="➕", callback_data="sp:int:+1")],
        [InlineKeyboardButton(text=f"📨 Макс/мин: {max_rpm}", callback_data="sp:info")],
        [InlineKeyboardButton(text="➖", callback_data="sp:rpm:-1"),
         InlineKeyboardButton(text="➕", callback_data="sp:rpm:+1")],
        [InlineKeyboardButton(text=f"📋 Список ({blocked})", callback_data="spam:list")],
        [InlineKeyboardButton(text="🔓 Разблокировать", callback_data="spam:unblock")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

# Управление юзером
def user_manage_kb(uid: int, is_blocked: bool = False):
    block_btn = InlineKeyboardButton(text="✅ Разблокировать", callback_data=f"unblock:{uid}") if is_blocked else InlineKeyboardButton(text="🚫 Заблокировать", callback_data=f"block:{uid}")
    return InlineKeyboardMarkup(inline_keyboard=[
        [block_btn],
        [InlineKeyboardButton(text="💎 Выдать подписку", callback_data=f"adm:givesub:{uid}")],
        [InlineKeyboardButton(text="💰 Выдать токены", callback_data=f"adm:givetokens:{uid}")],
        [InlineKeyboardButton(text="🧠 Память", callback_data=f"mem:user:{uid}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

# Рассылка с фильтрами
def bc_filter_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Всем", callback_data="bc:filter:all")],
        [InlineKeyboardButton(text="💎 С подпиской", callback_data="bc:filter:sub"),
         InlineKeyboardButton(text="❌ Без подписки", callback_data="bc:filter:nosub")],
        [InlineKeyboardButton(text="🔵 Mini (Sonnet)", callback_data="bc:filter:mini"),
         InlineKeyboardButton(text="🟣 Standard (Opus)", callback_data="bc:filter:standard")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def confirm_bc_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="bc:send"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="adm:back")]
    ])

# Подписки админ
def sub_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Выдать подписку", callback_data="sub:give")],
        [InlineKeyboardButton(text="📋 Mini подписчики", callback_data="sub:list:mini"),
         InlineKeyboardButton(text="📋 Standard", callback_data="sub:list:standard")],
        [InlineKeyboardButton(text="📋 Все подписчики", callback_data="sub:list:all")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def sub_give_type_kb(uid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔵 Mini 7д", callback_data=f"gsub:mini:7:{uid}"),
         InlineKeyboardButton(text="🔵 Mini 30д", callback_data=f"gsub:mini:30:{uid}")],
        [InlineKeyboardButton(text="🟣 Standard 7д", callback_data=f"gsub:standard:7:{uid}"),
         InlineKeyboardButton(text="🟣 Standard 30д", callback_data=f"gsub:standard:30:{uid}")],
        [InlineKeyboardButton(text="🟣 Standard 90д", callback_data=f"gsub:standard:90:{uid}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:sub")]
    ])

# Промпты
def prompts_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💭 Luca (Диалог)", callback_data="prompt:luca")],
        [InlineKeyboardButton(text="🛋️ Silas (Психолог)", callback_data="prompt:silas")],
        [InlineKeyboardButton(text="📓 Titus (Обучение)", callback_data="prompt:titus")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def prompt_edit_kb(bot: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"prompt:edit:{bot}")],
        [InlineKeyboardButton(text="🔄 Сбросить", callback_data=f"prompt:reset:{bot}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:prompts")]
    ])

# Мониторинг
def monitor_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="adm:monitor")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

# Моя подписка админа
def admin_mysub_kb(current: str):
    sonnet_mark = "✅" if current == "mini" else ""
    opus_mark = "✅" if current == "standard" else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{sonnet_mark} 🔵 Sonnet (Mini)", callback_data="adm:setmysub:mini")],
        [InlineKeyboardButton(text=f"{opus_mark} 🟣 Opus (Standard)", callback_data="adm:setmysub:standard")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

# Git
def git_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Push (сохранить)", callback_data="git:push")],
        [InlineKeyboardButton(text="📥 Pull (загрузить)", callback_data="git:pull")],
        [InlineKeyboardButton(text="📋 Статус", callback_data="git:status")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def confirm_git_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="git:confirm"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="adm:git")]
    ])

# === ПАМЯТЬ АДМИН ===

def memory_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск по ID", callback_data="mem:search")],
        [InlineKeyboardButton(text="📋 Список", callback_data="mem:list:0")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])

def memory_users_kb(users: list, page: int, total_pages: int):
    kb = []
    for u in users:
        name = f"@{u['username']}" if u.get('username') else str(u['user_id'])
        kb.append([InlineKeyboardButton(
            text=f"👤 {name}",
            callback_data=f"mem:user:{u['user_id']}"
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"mem:list:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="mem:info"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"mem:list:{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:memory")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def memory_user_bots_kb(uid: int, bots: dict):
    kb = []
    bot_names = {'luca': '💭 Диалог', 'silas': '🛋️ Психолог', 'titus': '📓 Обучение', 'voice': '🎤 Голос'}
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
    total_pages = max(1, (len(facts) + per_page - 1) // per_page)
    for i in range(start, end):
        fact_short = facts[i][:30] + "..." if len(facts[i]) > 30 else facts[i]
        kb.append([
            InlineKeyboardButton(text=f"{i+1}. {fact_short}", callback_data=f"mem:view:{uid}:{bot}:{i}"),
            InlineKeyboardButton(text="🗑", callback_data=f"mem:del:{uid}:{bot}:{i}")
        ])
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"mem:facts:{uid}:{bot}:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="mem:info"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"mem:facts:{uid}:{bot}:{page+1}"))
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="➕ Добавить", callback_data=f"mem:add:{uid}:{bot}")])
    kb.append([InlineKeyboardButton(text="🗑 Очистить", callback_data=f"mem:clear:{uid}:{bot}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"mem:user:{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def memory_fact_view_kb(uid: int, bot: str, idx: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить", callback_data=f"mem:edit:{uid}:{bot}:{idx}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"mem:del:{uid}:{bot}:{idx}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"mem:bot:{uid}:{bot}")]
    ])

# titus_telegraph_kb удалена - Telegraph больше не используется


def course_continue_kb(course_id: int, current_step: int, has_weak_topics: bool = False):
    """Клавиатура выбора при продолжении курса"""
    buttons = []
    if has_weak_topics:
        buttons.append([InlineKeyboardButton(
            text="🔄 Повторить сложные темы",
            callback_data=f"course:repeat:{course_id}"
        )])
    buttons.append([InlineKeyboardButton(
        text=f"▶️ Продолжить с шага {current_step}",
        callback_data=f"course:continue:{course_id}:{current_step}"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================
# === ТРЕКЕР ЦЕЛЕЙ ===
# ============================================

def goal_frequency_kb():
    """Выбор частоты цели"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Каждый день", callback_data="freq_daily")],
        [InlineKeyboardButton(text="📆 Раз в неделю", callback_data="freq_weekly")],
        [InlineKeyboardButton(text="🔢 Своя частота", callback_data="freq_custom")],
    ])


def goal_confirm_kb(goal_id: int):
    """Подтверждение выполнения цели"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, выполнил!", callback_data=f"goal_done_{goal_id}"),
            InlineKeyboardButton(text="❌ Пропустил", callback_data=f"goal_skip_{goal_id}")
        ]
    ])


def goal_actions_kb(goal_id: int):
    """Действия с целью"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отметить выполнение", callback_data=f"checkin_{goal_id}")],
        [InlineKeyboardButton(text="📊 Прогресс", callback_data=f"progress_{goal_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_goal_{goal_id}")]
    ])


# ============================================
# === РЕЖИМ ДНЯ (РУТИНЫ) ===
# ============================================

def checklist_kb(items: list, checked: list, routine_type: str):
    """Чеклист с кнопками"""
    buttons = []
    for i, item in enumerate(items):
        emoji = "✅" if item in checked else "⬜"
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {item}",
            callback_data=f"check_{routine_type}_{i}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="💾 Сохранить",
        callback_data=f"save_{routine_type}"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def mood_kb():
    """Выбор настроения"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="😫 1", callback_data="mood_1"),
            InlineKeyboardButton(text="😕 2", callback_data="mood_2"),
            InlineKeyboardButton(text="😐 3", callback_data="mood_3"),
            InlineKeyboardButton(text="🙂 4", callback_data="mood_4"),
            InlineKeyboardButton(text="😄 5", callback_data="mood_5"),
        ]
    ])


def setup_routine_kb():
    """Настройка рутины"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="☀️ Утренняя рутина", callback_data="setup_morning")],
        [InlineKeyboardButton(text="🌙 Вечерняя рутина", callback_data="setup_evening")],
    ])


# ============================================
# === МЕНТАЛЬНОЕ ЗДОРОВЬЕ ===
# ============================================

def meditation_duration_kb():
    """Выбор длительности медитации"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ 2 минуты", callback_data="med_2")],
        [InlineKeyboardButton(text="⏱ 5 минут", callback_data="med_5")],
        [InlineKeyboardButton(text="⏱ 10 минут", callback_data="med_10")],
    ])


def meditation_type_kb():
    """Тип медитации"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😌 Успокоение", callback_data="type_calm")],
        [InlineKeyboardButton(text="🎯 Фокус", callback_data="type_focus")],
        [InlineKeyboardButton(text="😴 Для сна", callback_data="type_sleep")],
    ])


def mood_scale_kb():
    """Шкала настроения"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="😫", callback_data="mood_m_1"),
            InlineKeyboardButton(text="😕", callback_data="mood_m_2"),
            InlineKeyboardButton(text="😐", callback_data="mood_m_3"),
            InlineKeyboardButton(text="🙂", callback_data="mood_m_4"),
            InlineKeyboardButton(text="😄", callback_data="mood_m_5"),
        ]
    ])


def energy_scale_kb():
    """Шкала энергии"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔋", callback_data="energy_1"),
            InlineKeyboardButton(text="🔋🔋", callback_data="energy_2"),
            InlineKeyboardButton(text="🔋🔋🔋", callback_data="energy_3"),
            InlineKeyboardButton(text="🔋🔋🔋🔋", callback_data="energy_4"),
            InlineKeyboardButton(text="⚡", callback_data="energy_5"),
        ]
    ])


def mood_tags_kb(selected: list = None):
    """Теги настроения"""
    MOOD_TAGS = ["😴 Сон", "💼 Работа", "🏃 Спорт", "👥 Общение", "🍔 Еда", "📱 Соцсети", "😰 Стресс"]
    selected = selected or []
    buttons = []
    
    for i in range(0, len(MOOD_TAGS), 2):
        row = []
        for tag in MOOD_TAGS[i:i+2]:
            emoji = "✅ " if tag in selected else ""
            row.append(InlineKeyboardButton(
                text=f"{emoji}{tag}",
                callback_data=f"mtag_{MOOD_TAGS.index(tag)}"
            ))
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="💾 Сохранить", callback_data="save_mood")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================
# === ФИНАНСЫ ===
# ============================================

def category_kb():
    """Выбор категории расходов"""
    from database.db import EXPENSE_CATEGORIES
    buttons = []
    categories = list(EXPENSE_CATEGORIES.items())
    
    for i in range(0, len(categories), 2):
        row = []
        for key, name in categories[i:i+2]:
            row.append(InlineKeyboardButton(text=name, callback_data=f"cat_{key}"))
        buttons.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def expenses_period_kb():
    """Выбор периода для просмотра"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Сегодня", callback_data="exp_today")],
        [InlineKeyboardButton(text="📅 Неделя", callback_data="exp_week")],
        [InlineKeyboardButton(text="📅 Месяц", callback_data="exp_month")],
    ])
