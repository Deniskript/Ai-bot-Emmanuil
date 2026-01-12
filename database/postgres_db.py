"""
PostgreSQL database module for AI Bot
Миграция с SQLite на PostgreSQL
"""

import asyncpg
import json
import os
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List
from contextlib import asynccontextmanager


# Константы для совместимости
EXPENSE_CATEGORIES = {
    "food": "🍔 Еда",
    "transport": "🚗 Транспорт",
    "entertainment": "🎬 Развлечения",
    "shopping": "🛍 Покупки",
    "health": "💊 Здоровье",
    "bills": "🏠 Счета и ЖКХ",
    "education": "📚 Образование",
    "other": "📦 Другое"
}


# Database connection pool
_pool: Optional[asyncpg.Pool] = None


async def init_pool():
    """Инициализация пула соединений PostgreSQL"""
    global _pool
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL не установлен в .env")
    
    _pool = await asyncpg.create_pool(
        database_url,
        min_size=2,
        max_size=10,
        command_timeout=60
    )
    print("✅ PostgreSQL pool создан")


async def close_pool():
    """Закрытие пула соединений"""
    global _pool
    if _pool:
        await _pool.close()
        print("✅ PostgreSQL pool закрыт")


@asynccontextmanager
async def get_connection():
    """Контекстный менеджер для получения соединения из пула"""
    async with _pool.acquire() as conn:
        yield conn


async def init_db():
    """Создание всех таблиц в PostgreSQL"""
    
    schema = """
    -- Основная таблица пользователей
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        tokens INTEGER DEFAULT 5000,
        total_used INTEGER DEFAULT 0,
        total_requests INTEGER DEFAULT 0,
        is_blocked INTEGER DEFAULT 0,
        agreement INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        referred_by BIGINT DEFAULT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_users_blocked ON users(is_blocked);
    CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at);
    CREATE INDEX IF NOT EXISTS idx_users_referred ON users(referred_by);
    
    -- Настройки ботов для пользователей
    CREATE TABLE IF NOT EXISTS user_bots (
        user_id BIGINT,
        bot TEXT,
        character TEXT DEFAULT 'душевный',
        mood TEXT,
        custom_mood TEXT,
        msg_counter INTEGER DEFAULT 0,
        voice_gender TEXT DEFAULT NULL,
        PRIMARY KEY(user_id, bot)
    );
    
    -- 🧠 ДОЛГАЯ ПАМЯТЬ БОТОВ (КРИТИЧНО!)
    CREATE TABLE IF NOT EXISTS bot_memory (
        user_id BIGINT,
        bot TEXT,
        facts TEXT DEFAULT '[]',
        PRIMARY KEY(user_id, bot)
    );
    
    -- Диалоги (новая система)
    CREATE TABLE IF NOT EXISTS conversations (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        bot TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, created_at DESC);
    
    -- Сообщения в диалогах
    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        conversation_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        model TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, timestamp);
    
    -- Подписки
    CREATE TABLE IF NOT EXISTS subscriptions (
        user_id BIGINT PRIMARY KEY,
        type TEXT,
        tokens_limit INTEGER DEFAULT 0,
        tokens_used INTEGER DEFAULT 0,
        started_at TIMESTAMP,
        expires_at TIMESTAMP,
        is_active INTEGER DEFAULT 0
    );
    
    -- Использование токенов
    CREATE TABLE IF NOT EXISTS token_usage (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        tokens_used INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        bot_name TEXT DEFAULT 'unknown'
    );
    CREATE INDEX IF NOT EXISTS idx_token_usage_user_date ON token_usage(user_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_token_usage_bot ON token_usage(user_id, bot_name);
    
    -- Реферальная система
    CREATE TABLE IF NOT EXISTS referrals (
        id SERIAL PRIMARY KEY,
        referrer_id BIGINT NOT NULL,
        referred_id BIGINT NOT NULL,
        tokens_earned INTEGER DEFAULT 0,
        subscription_type TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(referred_id)
    );
    CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
    
    -- Профили пользователей
    CREATE TABLE IF NOT EXISTS user_profile (
        user_id BIGINT PRIMARY KEY,
        name TEXT,
        age INTEGER,
        gender TEXT
    );
    
    -- Курсы обучения
    CREATE TABLE IF NOT EXISTS courses (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        name TEXT,
        total INTEGER,
        current INTEGER DEFAULT 1,
        done INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_courses_user ON courses(user_id, created_at DESC);
    
    -- Цели пользователей
    CREATE TABLE IF NOT EXISTS user_goals (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        frequency TEXT NOT NULL,
        target_count INTEGER DEFAULT 1,
        period_days INTEGER DEFAULT 7,
        reminder_time TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_user_goals_user ON user_goals(user_id, is_active);
    
    -- Отметки выполнения целей
    CREATE TABLE IF NOT EXISTS goal_checkins (
        id SERIAL PRIMARY KEY,
        goal_id INTEGER NOT NULL,
        user_id BIGINT NOT NULL,
        date DATE NOT NULL,
        is_done INTEGER DEFAULT 1,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (goal_id) REFERENCES user_goals(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_goal_checkins_goal ON goal_checkins(goal_id, date);
    CREATE INDEX IF NOT EXISTS idx_goal_checkins_user ON goal_checkins(user_id, date);
    
    -- Серии выполнения целей
    CREATE TABLE IF NOT EXISTS user_streaks (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        goal_id INTEGER NOT NULL,
        current_streak INTEGER DEFAULT 0,
        best_streak INTEGER DEFAULT 0,
        last_checkin DATE,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (goal_id) REFERENCES user_goals(id) ON DELETE CASCADE,
        UNIQUE(user_id, goal_id)
    );
    CREATE INDEX IF NOT EXISTS idx_user_streaks_user ON user_streaks(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_streaks_goal ON user_streaks(goal_id);
    
    -- Рутины пользователей
    CREATE TABLE IF NOT EXISTS user_routines (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        routine_type TEXT NOT NULL,
        items TEXT NOT NULL,
        reminder_time TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        UNIQUE(user_id, routine_type)
    );
    CREATE INDEX IF NOT EXISTS idx_user_routines_user ON user_routines(user_id, routine_type);
    
    -- Отметки выполнения рутин
    CREATE TABLE IF NOT EXISTS routine_checkins (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        routine_type TEXT NOT NULL,
        date DATE NOT NULL,
        completed_items TEXT NOT NULL,
        total_items INTEGER NOT NULL,
        completion_percent INTEGER NOT NULL,
        reflection TEXT,
        mood INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_routine_checkins_user ON routine_checkins(user_id, routine_type, date);
    
    -- Дневник настроения
    CREATE TABLE IF NOT EXISTS mood_logs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        date DATE NOT NULL,
        mood INTEGER NOT NULL,
        energy INTEGER NOT NULL,
        note TEXT,
        tags TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_mood_logs_user ON mood_logs(user_id, date);
    
    -- Логи медитаций
    CREATE TABLE IF NOT EXISTS meditation_logs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        date DATE NOT NULL,
        duration INTEGER NOT NULL,
        type TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_meditation_logs_user ON meditation_logs(user_id, date);
    
    -- Дневник питания
    CREATE TABLE IF NOT EXISTS calories_log (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        date DATE DEFAULT CURRENT_DATE,
        time TIME DEFAULT CURRENT_TIME,
        food_name TEXT,
        portion TEXT,
        calories INTEGER DEFAULT 0,
        protein REAL DEFAULT 0,
        fat REAL DEFAULT 0,
        carbs REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_calories_log_user_date ON calories_log(user_id, date DESC);
    
    -- Цели по питанию
    CREATE TABLE IF NOT EXISTS user_nutrition_goals (
        id SERIAL PRIMARY KEY,
        user_id BIGINT UNIQUE NOT NULL,
        goal TEXT,
        daily_calories INTEGER DEFAULT 2000,
        daily_protein INTEGER DEFAULT 80,
        daily_fat INTEGER DEFAULT 60,
        daily_carbs INTEGER DEFAULT 200,
        weight REAL,
        height INTEGER,
        age INTEGER,
        gender TEXT,
        activity TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_nutrition_goals_user ON user_nutrition_goals(user_id);
    
    -- Финансовые транзакции
    CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'RUB',
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        date TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
    
    -- Бюджеты пользователей
    CREATE TABLE IF NOT EXISTS user_budgets (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL UNIQUE,
        monthly_limit REAL NOT NULL,
        category_limits TEXT,
        currency TEXT DEFAULT 'RUB',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Конфигурация ботов
    CREATE TABLE IF NOT EXISTS bot_cfg (
        bot TEXT PRIMARY KEY,
        enabled INTEGER DEFAULT 1,
        model TEXT,
        version TEXT DEFAULT '1.0.0'
    );
    
    -- Настройки ботов
    CREATE TABLE IF NOT EXISTS bot_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    
    -- Тексты интерфейса
    CREATE TABLE IF NOT EXISTS bot_texts (
        key TEXT PRIMARY KEY,
        value TEXT,
        description TEXT
    );
    
    -- Кнопки интерфейса
    CREATE TABLE IF NOT EXISTS bot_buttons (
        key TEXT PRIMARY KEY,
        emoji TEXT,
        text TEXT,
        description TEXT
    );
    
    -- Медиа файлы
    CREATE TABLE IF NOT EXISTS bot_media (
        key TEXT PRIMARY KEY,
        type TEXT,
        file_id TEXT
    );
    
    -- Общие настройки
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    
    -- Общие тексты
    CREATE TABLE IF NOT EXISTS texts (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    
    -- Статистика настроения (старая)
    CREATE TABLE IF NOT EXISTS mood_stats (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        mood TEXT,
        at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Сессии
    CREATE TABLE IF NOT EXISTS sessions (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        started TIMESTAMP,
        duration INTEGER,
        ended TIMESTAMP
    );
    
    -- Метрики сервера
    CREATE TABLE IF NOT EXISTS server_metrics (
        id SERIAL PRIMARY KEY,
        ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        active_users INTEGER,
        rpm INTEGER,
        avg_time REAL,
        load_pct INTEGER
    );
    """
    
    async with get_connection() as conn:
        await conn.execute(schema)
    
    print("✅ Все таблицы PostgreSQL созданы")


# ============================================================================
# USERS - Управление пользователями
# ============================================================================

async def get_user(uid: int) -> Optional[Dict]:
    """Получить пользователя"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1",
            uid
        )
        return dict(row) if row else None


async def create_user(uid: int, uname: str = None, fname: str = None, referred_by: int = None) -> Dict:
    """Создать нового пользователя"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, username, first_name, tokens, referred_by)
            VALUES ($1, $2, $3, 5000, $4)
            ON CONFLICT (user_id) DO NOTHING
            """,
            uid, uname, fname, referred_by
        )
        
        # Если есть реферер, создаём запись в referrals
        if referred_by:
            await conn.execute(
                """
                INSERT INTO referrals (referrer_id, referred_id)
                VALUES ($1, $2)
                ON CONFLICT (referred_id) DO NOTHING
                """,
                referred_by, uid
            )
        
        return await get_user(uid)


async def accept_agreement(uid: int):
    """Принять соглашение"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET agreement = 1 WHERE user_id = $1",
            uid
        )


async def update_tokens(uid: int, used: int):
    """Обновить токены после использования"""
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE users
            SET tokens = tokens - $2,
                total_used = total_used + $2,
                total_requests = total_requests + 1
            WHERE user_id = $1
            """,
            uid, used
        )


async def add_tokens(uid: int, amt: int):
    """Добавить токены"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET tokens = tokens + $2 WHERE user_id = $1",
            uid, amt
        )


async def subtract_tokens(uid: int, amount: int):
    """Вычесть токены"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET tokens = tokens - $2 WHERE user_id = $1",
            uid, amount
        )


async def block_user(uid: int):
    """Заблокировать пользователя"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET is_blocked = 1 WHERE user_id = $1",
            uid
        )


async def unblock_user(uid: int):
    """Разблокировать пользователя"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET is_blocked = 0 WHERE user_id = $1",
            uid
        )


async def get_all_users() -> List[Dict]:
    """Получить всех пользователей"""
    async with get_connection() as conn:
        rows = await conn.fetch("SELECT * FROM users ORDER BY created_at DESC")
        return [dict(row) for row in rows]


async def get_stats() -> Dict:
    """Получить статистику"""
    async with get_connection() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        active = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_blocked = 0")
        blocked = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
        return {"total": total, "active": active, "blocked": blocked}


async def get_blocked_count() -> int:
    """Количество заблокированных"""
    async with get_connection() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_blocked = 1")


async def get_blocked_users():
    """Получить заблокированных пользователей"""
    async with get_connection() as conn:
        rows = await conn.fetch("SELECT * FROM users WHERE is_blocked = 1")
        return [dict(row) for row in rows]


# ============================================================================
# BOT CONFIGURATION - Конфигурация ботов
# ============================================================================

async def get_bot_cfg(bot: str) -> Dict:
    """Получить конфигурацию бота"""
    async with get_connection() as conn:
        row = await conn.fetchrow("SELECT * FROM bot_cfg WHERE bot = $1", bot)
        return dict(row) if row else {"bot": bot, "enabled": 1, "model": None, "version": "1.0.0"}


async def set_bot_enabled(bot: str, en: bool):
    """Включить/выключить бота"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO bot_cfg (bot, enabled) VALUES ($1, $2)
            ON CONFLICT (bot) DO UPDATE SET enabled = $2
            """,
            bot, 1 if en else 0
        )


async def set_bot_model(bot: str, model: str):
    """Установить модель бота"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO bot_cfg (bot, model) VALUES ($1, $2)
            ON CONFLICT (bot) DO UPDATE SET model = $2
            """,
            bot, model
        )


async def set_bot_version(bot: str, ver: str):
    """Установить версию бота"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO bot_cfg (bot, version) VALUES ($1, $2)
            ON CONFLICT (bot) DO UPDATE SET version = $2
            """,
            bot, ver
        )


# ============================================================================
# USER BOTS - Настройки ботов для пользователей
# ============================================================================

async def get_user_bot(uid: int, bot: str) -> Dict:
    """Получить настройки бота для пользователя"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_bots WHERE user_id = $1 AND bot = $2",
            uid, bot
        )
        if row:
            return dict(row)
        
        # Создаём запись по умолчанию
        await conn.execute(
            "INSERT INTO user_bots (user_id, bot) VALUES ($1, $2)",
            uid, bot
        )
        return {"user_id": uid, "bot": bot, "character": "душевный", "mood": None, "msg_counter": 0}


async def set_char(uid: int, char: str):
    """Установить характер бота"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO user_bots (user_id, bot, character) VALUES ($1, 'luca', $2)
            ON CONFLICT (user_id, bot) DO UPDATE SET character = $2
            """,
            uid, char
        )


async def get_voice_gender(uid: int, bot: str = 'voice') -> str:
    """Получить пол голоса"""
    async with get_connection() as conn:
        gender = await conn.fetchval(
            "SELECT voice_gender FROM user_bots WHERE user_id = $1 AND bot = $2",
            uid, bot
        )
        return gender if gender else 'alloy'


async def set_voice_gender(uid: int, gender: str, bot: str = 'voice'):
    """Установить пол голоса"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO user_bots (user_id, bot, voice_gender)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, bot)
            DO UPDATE SET voice_gender = $3
            """,
            uid, bot, gender
        )


async def set_mood(uid: int, mood: str, custom: str = None):
    """Установить настроение"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO user_bots (user_id, bot, mood, custom_mood)
            VALUES ($1, 'luca', $2, $3)
            ON CONFLICT (user_id, bot)
            DO UPDATE SET mood = $2, custom_mood = $3
            """,
            uid, mood, custom
        )


async def inc_msg_counter(uid: int, bot: str) -> int:
    """Увеличить счётчик сообщений"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO user_bots (user_id, bot, msg_counter)
            VALUES ($1, $2, 1)
            ON CONFLICT (user_id, bot)
            DO UPDATE SET msg_counter = user_bots.msg_counter + 1
            """,
            uid, bot
        )
        counter = await conn.fetchval(
            "SELECT msg_counter FROM user_bots WHERE user_id = $1 AND bot = $2",
            uid, bot
        )
        return counter or 0


async def reset_msg_counter(uid: int, bot: str):
    """Сбросить счётчик сообщений"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE user_bots SET msg_counter = 0 WHERE user_id = $1 AND bot = $2",
            uid, bot
        )


# ============================================================================
# 🧠 BOT MEMORY - ДОЛГАЯ ПАМЯТЬ БОТОВ (КРИТИЧНО!)
# ============================================================================

async def get_memory(uid: int, bot: str) -> List:
    """Получить память бота о пользователе"""
    async with get_connection() as conn:
        facts_json = await conn.fetchval(
            "SELECT facts FROM bot_memory WHERE user_id = $1 AND bot = $2",
            uid, bot
        )
        if facts_json:
            return json.loads(facts_json)
        return []


async def save_memory(uid: int, bot: str, facts: List):
    """Сохранить память бота"""
    async with get_connection() as conn:
        facts_json = json.dumps(facts, ensure_ascii=False)
        await conn.execute(
            """
            INSERT INTO bot_memory (user_id, bot, facts)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, bot)
            DO UPDATE SET facts = $3
            """,
            uid, bot, facts_json
        )


# ============================================================================
# CONVERSATIONS & MESSAGES - Диалоги и сообщения
# ============================================================================

async def create_conversation(uid: int, bot: str) -> int:
    """Создать новый диалог"""
    async with get_connection() as conn:
        conv_id = await conn.fetchval(
            """
            INSERT INTO conversations (user_id, bot)
            VALUES ($1, $2)
            RETURNING id
            """,
            uid, bot
        )
        return conv_id


async def get_or_create_conversation(uid: int, bot: str) -> int:
    """Получить или создать диалог"""
    async with get_connection() as conn:
        conv_id = await conn.fetchval(
            """
            SELECT id FROM conversations
            WHERE user_id = $1 AND bot = $2
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            uid, bot
        )
        
        if not conv_id:
            conv_id = await create_conversation(uid, bot)
        
        return conv_id


async def add_message(conversation_id: int, role: str, content: str, model: str = None):
    """Добавить сообщение в диалог"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content, model)
            VALUES ($1, $2, $3, $4)
            """,
            conversation_id, role, content, model
        )
        
        # Обновляем updated_at диалога
        await conn.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = $1",
            conversation_id
        )


async def get_conversation_messages(conversation_id: int, limit: int = 20) -> List[Dict]:
    """Получить сообщения диалога"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM messages
            WHERE conversation_id = $1
            ORDER BY timestamp DESC
            LIMIT $2
            """,
            conversation_id, limit
        )
        messages = [dict(row) for row in reversed(rows)]
        return messages


async def clear_conversation(conversation_id: int):
    """Очистить диалог"""
    async with get_connection() as conn:
        await conn.execute(
            "DELETE FROM messages WHERE conversation_id = $1",
            conversation_id
        )


async def get_user_conversations(uid: int, bot: str = None) -> List[Dict]:
    """Получить диалоги пользователя"""
    async with get_connection() as conn:
        if bot:
            rows = await conn.fetch(
                """
                SELECT * FROM conversations
                WHERE user_id = $1 AND bot = $2
                ORDER BY updated_at DESC
                """,
                uid, bot
            )
        else:
            rows = await conn.fetch(
                """
                SELECT * FROM conversations
                WHERE user_id = $1
                ORDER BY updated_at DESC
                """,
                uid
            )
        return [dict(row) for row in rows]


# ============================================================================
# SUBSCRIPTIONS - Подписки
# ============================================================================

async def get_subscription(uid: int) -> Optional[Dict]:
    """Получить подписку пользователя"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM subscriptions WHERE user_id = $1",
            uid
        )
        return dict(row) if row else None


async def create_subscription(uid: int, sub_type: str, tokens_limit: int, days: int):
    """Создать подписку"""
    async with get_connection() as conn:
        started = datetime.now()
        expires = started + timedelta(days=days)
        
        await conn.execute(
            """
            INSERT INTO subscriptions (user_id, type, tokens_limit, tokens_used, started_at, expires_at, is_active)
            VALUES ($1, $2, $3, 0, $4, $5, 1)
            ON CONFLICT (user_id)
            DO UPDATE SET type = $2, tokens_limit = $3, tokens_used = 0,
                          started_at = $4, expires_at = $5, is_active = 1
            """,
            uid, sub_type, tokens_limit, started, expires
        )


async def update_subscription_tokens(uid: int, used: int):
    """Обновить использованные токены подписки"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE subscriptions SET tokens_used = tokens_used + $2 WHERE user_id = $1",
            uid, used
        )


async def deactivate_subscription(uid: int):
    """Деактивировать подписку"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE subscriptions SET is_active = 0 WHERE user_id = $1",
            uid
        )


async def get_active_subscriptions() -> List[Dict]:
    """Получить активные подписки"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM subscriptions WHERE is_active = 1 AND expires_at > CURRENT_TIMESTAMP"
        )
        return [dict(row) for row in rows]


# ============================================================================
# TOKEN USAGE - Использование токенов
# ============================================================================

async def log_token_usage(uid: int, tokens: int, bot_name: str = 'unknown'):
    """Записать использование токенов"""
    async with get_connection() as conn:
        await conn.execute(
            "INSERT INTO token_usage (user_id, tokens_used, bot_name) VALUES ($1, $2, $3)",
            uid, tokens, bot_name
        )


async def get_token_usage_stats(uid: int, days: int = 30) -> Dict:
    """Получить статистику использования токенов"""
    async with get_connection() as conn:
        since = datetime.now() - timedelta(days=days)
        
        total = await conn.fetchval(
            "SELECT COALESCE(SUM(tokens_used), 0) FROM token_usage WHERE user_id = $1 AND created_at >= $2",
            uid, since
        )
        
        by_bot = await conn.fetch(
            """
            SELECT bot_name, SUM(tokens_used) as total
            FROM token_usage
            WHERE user_id = $1 AND created_at >= $2
            GROUP BY bot_name
            ORDER BY total DESC
            """,
            uid, since
        )
        
        return {
            "total": total,
            "by_bot": {row['bot_name']: row['total'] for row in by_bot}
        }


# ============================================================================
# REFERRALS - Реферальная система
# ============================================================================

async def get_referrals(uid: int) -> List[Dict]:
    """Получить рефералов пользователя"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM referrals WHERE referrer_id = $1 ORDER BY created_at DESC",
            uid
        )
        return [dict(row) for row in rows]


async def get_referral_stats(uid: int) -> Dict:
    """Получить статистику рефералов"""
    async with get_connection() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = $1",
            uid
        )
        
        total_tokens = await conn.fetchval(
            "SELECT COALESCE(SUM(tokens_earned), 0) FROM referrals WHERE referrer_id = $1",
            uid
        )
        
        return {"count": count, "total_tokens": total_tokens}


async def add_referral_tokens(referrer_id: int, referred_id: int, tokens: int, sub_type: str = None):
    """Добавить токены за реферала"""
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE referrals
            SET tokens_earned = tokens_earned + $3, subscription_type = $4
            WHERE referrer_id = $1 AND referred_id = $2
            """,
            referrer_id, referred_id, tokens, sub_type
        )
        
        # Добавляем токены рефереру
        await add_tokens(referrer_id, tokens)


# ============================================================================
# COURSES - Курсы обучения
# ============================================================================

async def create_course(uid: int, name: str, steps: int) -> int:
    """Создать курс"""
    async with get_connection() as conn:
        course_id = await conn.fetchval(
            """
            INSERT INTO courses (user_id, name, total, current, done)
            VALUES ($1, $2, $3, 1, 0)
            RETURNING id
            """,
            uid, name, steps
        )
        return course_id


async def get_courses(uid: int) -> List[Dict]:
    """Получить курсы пользователя"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM courses WHERE user_id = $1 ORDER BY created_at DESC",
            uid
        )
        return [dict(row) for row in rows]


async def get_course(cid: int) -> Optional[Dict]:
    """Получить курс по ID"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM courses WHERE id = $1",
            cid
        )
        return dict(row) if row else None


async def update_step(cid: int, step: int):
    """Обновить шаг курса"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE courses SET current = $2 WHERE id = $1",
            cid, step
        )


async def mark_course_done(cid: int):
    """Отметить курс как завершённый"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE courses SET done = 1 WHERE id = $1",
            cid
        )


# ============================================================================
# GOALS - Цели пользователей
# ============================================================================

async def create_goal(uid: int, title: str, description: str, frequency: str,
                     target_count: int = 1, period_days: int = 7, reminder_time: str = None) -> int:
    """Создать цель"""
    async with get_connection() as conn:
        goal_id = await conn.fetchval(
            """
            INSERT INTO user_goals (user_id, title, description, frequency, target_count, period_days, reminder_time)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            uid, title, description, frequency, target_count, period_days, reminder_time
        )
        
        # Создаём запись в user_streaks
        await conn.execute(
            "INSERT INTO user_streaks (user_id, goal_id) VALUES ($1, $2)",
            uid, goal_id
        )
        
        return goal_id


async def get_user_goals(uid: int, active_only: bool = True) -> List[Dict]:
    """Получить цели пользователя"""
    async with get_connection() as conn:
        if active_only:
            rows = await conn.fetch(
                "SELECT * FROM user_goals WHERE user_id = $1 AND is_active = 1 ORDER BY created_at DESC",
                uid
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM user_goals WHERE user_id = $1 ORDER BY created_at DESC",
                uid
            )
        return [dict(row) for row in rows]


async def get_goal(goal_id: int) -> Optional[Dict]:
    """Получить цель по ID"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_goals WHERE id = $1",
            goal_id
        )
        return dict(row) if row else None


async def deactivate_goal(goal_id: int):
    """Деактивировать цель"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE user_goals SET is_active = 0 WHERE id = $1",
            goal_id
        )


async def add_goal_checkin(goal_id: int, uid: int, date_str: str, note: str = None):
    """Добавить отметку выполнения цели"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO goal_checkins (goal_id, user_id, date, note)
            VALUES ($1, $2, $3, $4)
            """,
            goal_id, uid, date_str, note
        )
        
        # Обновляем streak
        await update_streak(uid, goal_id)


async def get_goal_checkins(goal_id: int, days: int = 30) -> List[Dict]:
    """Получить отметки выполнения цели"""
    async with get_connection() as conn:
        since = datetime.now() - timedelta(days=days)
        rows = await conn.fetch(
            """
            SELECT * FROM goal_checkins
            WHERE goal_id = $1 AND date >= $2
            ORDER BY date DESC
            """,
            goal_id, since.date()
        )
        return [dict(row) for row in rows]


async def update_streak(uid: int, goal_id: int):
    """Обновить серию выполнения цели"""
    async with get_connection() as conn:
        # Получаем последние отметки
        rows = await conn.fetch(
            """
            SELECT date FROM goal_checkins
            WHERE goal_id = $1 AND user_id = $2
            ORDER BY date DESC
            LIMIT 100
            """,
            goal_id, uid
        )
        
        if not rows:
            return
        
        # Считаем текущую серию
        dates = [row['date'] for row in rows]
        current_streak = 1
        for i in range(len(dates) - 1):
            diff = (dates[i] - dates[i + 1]).days
            if diff == 1:
                current_streak += 1
            else:
                break
        
        # Обновляем streak
        await conn.execute(
            """
            UPDATE user_streaks
            SET current_streak = $3,
                best_streak = GREATEST(best_streak, $3),
                last_checkin = $4
            WHERE user_id = $1 AND goal_id = $2
            """,
            uid, goal_id, current_streak, dates[0]
        )


async def get_streak(uid: int, goal_id: int) -> Dict:
    """Получить серию выполнения цели"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_streaks WHERE user_id = $1 AND goal_id = $2",
            uid, goal_id
        )
        return dict(row) if row else {"current_streak": 0, "best_streak": 0}


# ============================================================================
# ROUTINES - Рутины
# ============================================================================

async def save_routine(uid: int, routine_type: str, items: List[str], reminder_time: str = None):
    """Сохранить рутину"""
    async with get_connection() as conn:
        items_json = json.dumps(items, ensure_ascii=False)
        await conn.execute(
            """
            INSERT INTO user_routines (user_id, routine_type, items, reminder_time)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, routine_type)
            DO UPDATE SET items = $3, reminder_time = $4
            """,
            uid, routine_type, items_json, reminder_time
        )


async def get_routine(uid: int, routine_type: str) -> Optional[Dict]:
    """Получить рутину"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_routines WHERE user_id = $1 AND routine_type = $2 AND is_active = 1",
            uid, routine_type
        )
        if row:
            data = dict(row)
            data['items'] = json.loads(data['items'])
            return data
        return None


async def add_routine_checkin(uid: int, routine_type: str, completed_items: List[str],
                              total_items: int, reflection: str = None, mood: int = None):
    """Добавить отметку выполнения рутины"""
    async with get_connection() as conn:
        completed_json = json.dumps(completed_items, ensure_ascii=False)
        completion_percent = int((len(completed_items) / total_items) * 100) if total_items > 0 else 0
        
        await conn.execute(
            """
            INSERT INTO routine_checkins (user_id, routine_type, date, completed_items, total_items, completion_percent, reflection, mood)
            VALUES ($1, $2, CURRENT_DATE, $3, $4, $5, $6, $7)
            """,
            uid, routine_type, completed_json, total_items, completion_percent, reflection, mood
        )


async def get_routine_checkins(uid: int, routine_type: str, days: int = 30) -> List[Dict]:
    """Получить отметки выполнения рутины"""
    async with get_connection() as conn:
        since = datetime.now() - timedelta(days=days)
        rows = await conn.fetch(
            """
            SELECT * FROM routine_checkins
            WHERE user_id = $1 AND routine_type = $2 AND date >= $3
            ORDER BY date DESC
            """,
            uid, routine_type, since.date()
        )
        result = []
        for row in rows:
            data = dict(row)
            data['completed_items'] = json.loads(data['completed_items'])
            result.append(data)
        return result


# ============================================================================
# NUTRITION - Питание
# ============================================================================

async def log_food(uid: int, food_name: str, portion: str, calories: int,
                  protein: float = 0, fat: float = 0, carbs: float = 0):
    """Записать приём пищи"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO calories_log (user_id, food_name, portion, calories, protein, fat, carbs)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            uid, food_name, portion, calories, protein, fat, carbs
        )


async def get_daily_nutrition(uid: int, date_str: str = None) -> Dict:
    """Получить питание за день"""
    async with get_connection() as conn:
        target_date = date_str if date_str else datetime.now().date()
        
        rows = await conn.fetch(
            "SELECT * FROM calories_log WHERE user_id = $1 AND date = $2 ORDER BY time",
            uid, target_date
        )
        
        total_calories = sum(row['calories'] for row in rows)
        total_protein = sum(row['protein'] for row in rows)
        total_fat = sum(row['fat'] for row in rows)
        total_carbs = sum(row['carbs'] for row in rows)
        
        return {
            "date": target_date,
            "meals": [dict(row) for row in rows],
            "total_calories": total_calories,
            "total_protein": total_protein,
            "total_fat": total_fat,
            "total_carbs": total_carbs
        }


async def save_nutrition_goals(uid: int, goal: str, daily_calories: int, daily_protein: int,
                               daily_fat: int, daily_carbs: int, weight: float = None,
                               height: int = None, age: int = None, gender: str = None, activity: str = None):
    """Сохранить цели по питанию"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO user_nutrition_goals (user_id, goal, daily_calories, daily_protein, daily_fat, daily_carbs,
                                              weight, height, age, gender, activity)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (user_id)
            DO UPDATE SET goal = $2, daily_calories = $3, daily_protein = $4, daily_fat = $5, daily_carbs = $6,
                          weight = $7, height = $8, age = $9, gender = $10, activity = $11, updated_at = CURRENT_TIMESTAMP
            """,
            uid, goal, daily_calories, daily_protein, daily_fat, daily_carbs, weight, height, age, gender, activity
        )


async def get_nutrition_goals(uid: int) -> Optional[Dict]:
    """Получить цели по питанию"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_nutrition_goals WHERE user_id = $1",
            uid
        )
        return dict(row) if row else None


# ============================================================================
# MENTAL HEALTH - Ментальное здоровье
# ============================================================================

async def log_mood(uid: int, mood: int, energy: int, note: str = None, tags: List[str] = None):
    """Записать настроение"""
    async with get_connection() as conn:
        tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
        await conn.execute(
            """
            INSERT INTO mood_logs (user_id, date, mood, energy, note, tags)
            VALUES ($1, CURRENT_DATE, $2, $3, $4, $5)
            """,
            uid, mood, energy, note, tags_json
        )


async def get_mood_logs(uid: int, days: int = 30) -> List[Dict]:
    """Получить логи настроения"""
    async with get_connection() as conn:
        since = datetime.now() - timedelta(days=days)
        rows = await conn.fetch(
            """
            SELECT * FROM mood_logs
            WHERE user_id = $1 AND date >= $2
            ORDER BY date DESC
            """,
            uid, since.date()
        )
        result = []
        for row in rows:
            data = dict(row)
            if data.get('tags'):
                data['tags'] = json.loads(data['tags'])
            result.append(data)
        return result


async def log_meditation(uid: int, duration: int, med_type: str):
    """Записать медитацию"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO meditation_logs (user_id, date, duration, type)
            VALUES ($1, CURRENT_DATE, $2, $3)
            """,
            uid, duration, med_type
        )


async def get_meditation_stats(uid: int, days: int = 30) -> Dict:
    """Получить статистику медитаций"""
    async with get_connection() as conn:
        since = datetime.now() - timedelta(days=days)
        
        total_count = await conn.fetchval(
            "SELECT COUNT(*) FROM meditation_logs WHERE user_id = $1 AND date >= $2",
            uid, since.date()
        )
        
        total_minutes = await conn.fetchval(
            "SELECT COALESCE(SUM(duration), 0) FROM meditation_logs WHERE user_id = $1 AND date >= $2",
            uid, since.date()
        )
        
        return {"total_sessions": total_count, "total_minutes": total_minutes}


# ============================================================================
# FINANCE - Финансы
# ============================================================================

async def add_transaction(uid: int, trans_type: str, amount: float, category: str,
                         description: str, trans_date: str, currency: str = 'RUB'):
    """Добавить транзакцию"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO transactions (user_id, type, amount, currency, category, description, date)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            uid, trans_type, amount, currency, category, description, trans_date
        )


async def get_transactions(uid: int, limit: int = 50) -> List[Dict]:
    """Получить транзакции"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM transactions WHERE user_id = $1 ORDER BY date DESC, created_at DESC LIMIT $2",
            uid, limit
        )
        return [dict(row) for row in rows]


async def get_monthly_stats(uid: int, year: int, month: int) -> Dict:
    """Получить статистику за месяц"""
    async with get_connection() as conn:
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"
        
        income = await conn.fetchval(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE user_id = $1 AND type = 'income' AND date >= $2 AND date < $3
            """,
            uid, start_date, end_date
        )
        
        expense = await conn.fetchval(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE user_id = $1 AND type = 'expense' AND date >= $2 AND date < $3
            """,
            uid, start_date, end_date
        )
        
        by_category = await conn.fetch(
            """
            SELECT category, SUM(amount) as total
            FROM transactions
            WHERE user_id = $1 AND type = 'expense' AND date >= $2 AND date < $3
            GROUP BY category
            ORDER BY total DESC
            """,
            uid, start_date, end_date
        )
        
        return {
            "income": income,
            "expense": expense,
            "balance": income - expense,
            "by_category": {row['category']: row['total'] for row in by_category}
        }


async def save_budget(uid: int, monthly_limit: float, category_limits: Dict, currency: str = 'RUB'):
    """Сохранить бюджет"""
    async with get_connection() as conn:
        limits_json = json.dumps(category_limits, ensure_ascii=False)
        await conn.execute(
            """
            INSERT INTO user_budgets (user_id, monthly_limit, category_limits, currency)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id)
            DO UPDATE SET monthly_limit = $2, category_limits = $3, currency = $4, updated_at = CURRENT_TIMESTAMP
            """,
            uid, monthly_limit, limits_json, currency
        )


async def get_budget(uid: int) -> Optional[Dict]:
    """Получить бюджет"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_budgets WHERE user_id = $1",
            uid
        )
        if row:
            data = dict(row)
            if data.get('category_limits'):
                data['category_limits'] = json.loads(data['category_limits'])
            return data
        return None


# ============================================================================
# SETTINGS - Настройки
# ============================================================================

async def get_setting(k: str) -> Optional[str]:
    """Получить настройку"""
    async with get_connection() as conn:
        return await conn.fetchval(
            "SELECT value FROM settings WHERE key = $1",
            k
        )


async def set_setting(k: str, v: str):
    """Установить настройку"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO settings (key, value) VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = $2
            """,
            k, v
        )


async def get_text(key: str, default: str = "") -> str:
    """Получить текст"""
    async with get_connection() as conn:
        value = await conn.fetchval(
            "SELECT value FROM bot_texts WHERE key = $1",
            key
        )
        return value if value else default


async def set_text(key: str, value: str, desc: str = ""):
    """Установить текст"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO bot_texts (key, value, description) VALUES ($1, $2, $3)
            ON CONFLICT (key) DO UPDATE SET value = $2, description = $3
            """,
            key, value, desc
        )


async def get_all_texts() -> List[Dict]:
    """Получить все тексты"""
    async with get_connection() as conn:
        rows = await conn.fetch("SELECT * FROM bot_texts ORDER BY key")
        return [dict(row) for row in rows]


async def get_button(key: str) -> Dict:
    """Получить кнопку"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM bot_buttons WHERE key = $1",
            key
        )
        return dict(row) if row else {"emoji": "", "text": key}


async def set_button(key: str, emoji: str, text: str, desc: str = ""):
    """Установить кнопку"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO bot_buttons (key, emoji, text, description) VALUES ($1, $2, $3, $4)
            ON CONFLICT (key) DO UPDATE SET emoji = $2, text = $3, description = $4
            """,
            key, emoji, text, desc
        )


async def get_all_buttons() -> List[Dict]:
    """Получить все кнопки"""
    async with get_connection() as conn:
        rows = await conn.fetch("SELECT * FROM bot_buttons ORDER BY key")
        return [dict(row) for row in rows]


async def save_media(key: str, media_type: str, file_id: str):
    """Сохранить медиа"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO bot_media (key, type, file_id) VALUES ($1, $2, $3)
            ON CONFLICT (key) DO UPDATE SET type = $2, file_id = $3
            """,
            key, media_type, file_id
        )


async def get_media(key: str) -> Optional[Dict]:
    """Получить медиа"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM bot_media WHERE key = $1",
            key
        )
        return dict(row) if row else None


# ============================================================================
# METRICS - Метрики
# ============================================================================

async def save_metrics(active: int, rpm: int, avg_time: float, load: int):
    """Сохранить метрики"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO server_metrics (active_users, rpm, avg_time, load_pct)
            VALUES ($1, $2, $3, $4)
            """,
            active, rpm, avg_time, load
        )


async def get_metrics() -> Optional[Dict]:
    """Получить последние метрики"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM server_metrics ORDER BY ts DESC LIMIT 1"
        )
        return dict(row) if row else None


# ============================================================================
# PROFILE - Профили пользователей
# ============================================================================

async def save_profile(uid: int, name: str, age: int, gender: str):
    """Сохранить профиль"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO user_profile (user_id, name, age, gender) VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE SET name = $2, age = $3, gender = $4
            """,
            uid, name, age, gender
        )


async def get_profile(uid: int) -> Optional[Dict]:
    """Получить профиль"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_profile WHERE user_id = $1",
            uid
        )
        return dict(row) if row else None


# ============================================================================
# LEGACY FUNCTIONS - Для совместимости со старым кодом
# ============================================================================

async def clear_msgs(uid: int, bot: str):
    """
    Очистить сообщения (deprecated функция для bot_msgs).
    Теперь очищает текущий диалог в новой системе.
    """
    # Находим текущий диалог
    async with get_connection() as conn:
        conv_id = await conn.fetchval(
            """
            SELECT id FROM conversations
            WHERE user_id = $1 AND bot = $2
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            uid, bot
        )
        
        if conv_id:
            await clear_conversation(conv_id)


async def get_available_tokens(uid: int) -> int:
    """
    Получить доступные токены:
    - Если есть активная подписка -> токены из подписки
    - Если нет подписки -> бонусные токены из users.tokens
    """
    sub = await get_subscription(uid)
    
    # Есть активная подписка
    if sub and sub['is_active']:
        # Проверяем не истекла ли подписка
        from datetime import datetime
        if sub['expires_at'] and sub['expires_at'] > datetime.now():
            return sub['tokens_limit'] - sub['tokens_used']
    
    # Нет подписки - берём бонусные токены
    user = await get_user(uid)
    return user['tokens'] if user else 0


async def use_tokens_smart(uid: int, amount: int, bot_name: str = None) -> bool:
    """
    Списать токены:
    - Если есть активная подписка -> из подписки
    - Если нет подписки -> из users.tokens (бонусные)
    - Разрешаем уход в минус, но БЛОКИРУЕМ дальнейшее использование при отрицательном балансе
    - Записываем статистику по ботам
    """
    # Проверяем доступный баланс ПЕРЕД списанием
    available = await get_available_tokens(uid)
    
    # Если баланс уже отрицательный - БЛОКИРУЕМ
    if available < 0:
        return False
    
    sub = await get_subscription(uid)
    
    # Записываем использование токенов по ботам
    if bot_name:
        await log_token_usage(uid, amount, bot_name)
    
    # Есть активная подписка
    if sub and sub['is_active']:
        from datetime import datetime
        if sub['expires_at'] and sub['expires_at'] > datetime.now():
            await update_subscription_tokens(uid, amount)
            return True
    
    # Нет подписки - списываем бонусные
    await update_tokens(uid, amount)
    return True


async def check_subscription_active(uid: int) -> bool:
    """Проверить активна ли подписка"""
    sub = await get_subscription(uid)
    if not sub or not sub['is_active']:
        return False
    
    from datetime import datetime
    if sub['expires_at'] and sub['expires_at'] > datetime.now():
        return True
    
    # Подписка истекла - деактивируем
    await deactivate_subscription(uid)
    return False


async def add_msg(uid: int, bot: str, role: str, content: str):
    """
    Добавить сообщение (legacy функция).
    Теперь использует новую систему conversations+messages
    """
    conv_id = await get_or_create_conversation(uid, bot)
    await add_message(conv_id, role, content)


async def get_msgs(uid: int, bot: str, lim: int = 20) -> List[Dict]:
    """
    Получить сообщения (legacy функция).
    Теперь использует новую систему conversations+messages
    """
    conv_id = await get_or_create_conversation(uid, bot)
    return await get_conversation_messages(conv_id, limit=lim)


async def get_bot_setting(key: str, default: str = "") -> str:
    """Получить настройку бота"""
    async with get_connection() as conn:
        value = await conn.fetchval(
            "SELECT value FROM bot_settings WHERE key = $1",
            key
        )
        return value if value else default


async def set_bot_setting(key: str, value: str):
    """Установить настройку бота"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO bot_settings (key, value) VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = $2
            """,
            key, value
        )


async def get_model_for_subscription(sub_type: str) -> str:
    """Получить модель для типа подписки"""
    from config import MODEL as config_MODEL
    
    if sub_type == "standard":
        return await get_bot_setting("model_standard", config_MODEL)
    elif sub_type == "mini":
        return await get_bot_setting("model_mini", config_MODEL)
    return config_MODEL


async def get_user_model(uid: int) -> str:
    """Получить модель для пользователя (по подписке или дефолтную)"""
    sub = await get_subscription(uid)
    if sub and sub['type']:
        return await get_model_for_subscription(sub['type'])
    return "anthropic/claude-sonnet-4"  # дефолтная модель для бонусных токенов


async def increment_requests(uid: int):
    """Увеличить счётчик запросов пользователя"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET total_requests = total_requests + 1 WHERE user_id = $1",
            uid
        )


async def count_users() -> int:
    """Подсчитать количество пользователей"""
    async with get_connection() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
        return count if count else 0


async def count_users_with_memory() -> int:
    """Подсчитать пользователей с заполненной памятью"""
    async with get_connection() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM bot_memory WHERE facts != '[]'"
        )
        return count if count else 0


async def count_subscribers_by_type(sub_type: str) -> int:
    """Подсчитать активных подписчиков по типу"""
    async with get_connection() as conn:
        count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM subscriptions 
            WHERE type = $1 AND is_active = TRUE AND expires_at > NOW()
            """,
            sub_type
        )
        return count if count else 0


async def get_bot_cfg(bot: str) -> Dict:
    """Получить конфигурацию бота"""
    async with get_connection() as conn:
        row = await conn.fetchrow("SELECT * FROM bot_cfg WHERE bot = $1", bot)
        if row:
            return dict(row)
        return {'enabled': 1, 'model': 'gpt-4o-mini', 'version': '1.0.0'}


async def get_user_bot(uid: int, bot: str) -> Dict:
    """Получить настройки пользователя для бота"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_bots WHERE user_id = $1 AND bot = $2",
            uid, bot
        )
        if row:
            return dict(row)
        
        # Создаём запись если её нет
        await conn.execute(
            "INSERT INTO user_bots (user_id, bot) VALUES ($1, $2)",
            uid, bot
        )
        return {
            'user_id': uid,
            'bot': bot,
            'character': 'душевный',
            'mood': None,
            'custom_mood': None,
            'msg_counter': 0,
            'voice_gender': None
        }


async def set_char(uid: int, char: str):
    """Установить характер для Luca"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE user_bots SET character = $1 WHERE user_id = $2 AND bot = 'luca'",
            char, uid
        )


async def get_voice_gender(uid: int, bot: str = 'voice') -> str:
    """Получить выбранный голос пользователя"""
    async with get_connection() as conn:
        gender = await conn.fetchval(
            "SELECT voice_gender FROM user_bots WHERE user_id = $1 AND bot = $2",
            uid, bot
        )
        return gender if gender else None


async def set_voice_gender(uid: int, gender: str, bot: str = 'voice'):
    """Установить выбранный голос"""
    async with get_connection() as conn:
        # Проверяем существует ли запись
        exists = await conn.fetchval(
            "SELECT 1 FROM user_bots WHERE user_id = $1 AND bot = $2",
            uid, bot
        )
        
        if exists:
            await conn.execute(
                "UPDATE user_bots SET voice_gender = $1 WHERE user_id = $2 AND bot = $3",
                gender, uid, bot
            )
        else:
            await conn.execute(
                "INSERT INTO user_bots (user_id, bot, voice_gender) VALUES ($1, $2, $3)",
                uid, bot, gender
            )


async def inc_msg_counter(uid: int, bot: str) -> int:
    """Увеличить счётчик сообщений"""
    async with get_connection() as conn:
        counter = await conn.fetchval(
            "SELECT msg_counter FROM user_bots WHERE user_id = $1 AND bot = $2",
            uid, bot
        )
        cnt = (counter if counter else 0) + 1
        await conn.execute(
            "UPDATE user_bots SET msg_counter = $1 WHERE user_id = $2 AND bot = $3",
            cnt, uid, bot
        )
        return cnt


async def reset_msg_counter(uid: int, bot: str):
    """Сбросить счётчик сообщений"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE user_bots SET msg_counter = 0 WHERE user_id = $1 AND bot = $2",
            uid, bot
        )
