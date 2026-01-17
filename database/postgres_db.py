"""
PostgreSQL database module for AI Bot
Миграция с SQLite на PostgreSQL
"""

import asyncpg
import json
import os
import secrets
import string
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


async def _init_db_schema():
    """Создание всех таблиц в PostgreSQL (устаревшее, через Alembic)"""
    
    schema = """
    -- Основная таблица пользователей
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        stars INTEGER DEFAULT 250,
        total_used INTEGER DEFAULT 0,
        total_requests INTEGER DEFAULT 0,
        is_blocked INTEGER DEFAULT 0,
        agreement INTEGER DEFAULT 0,
        agreement_accepted INTEGER DEFAULT 1,
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
        voice_enabled BOOLEAN DEFAULT FALSE,
        preferred_duration INTEGER DEFAULT 30,
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
        stars_limit INTEGER DEFAULT 0,
        stars_used INTEGER DEFAULT 0,
        started_at TIMESTAMP,
        expires_at TIMESTAMP,
        is_active INTEGER DEFAULT 0
    );
    
    -- Использование звёзд
    CREATE TABLE IF NOT EXISTS star_usage (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        stars_used INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        bot_name TEXT DEFAULT 'unknown'
    );
    CREATE INDEX IF NOT EXISTS idx_star_usage_user_date ON star_usage(user_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_star_usage_bot ON star_usage(user_id, bot_name);
    
    -- Платёжные транзакции (подписки/звёзды)
    CREATE TABLE IF NOT EXISTS payment_transactions (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        stars INTEGER NOT NULL DEFAULT 0,
        status TEXT DEFAULT 'pending',
        robokassa_id BIGINT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_payment_transactions_user ON payment_transactions(user_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_payment_transactions_status ON payment_transactions(status);
    
    -- Реферальная система
    CREATE TABLE IF NOT EXISTS referrals (
        id SERIAL PRIMARY KEY,
        referrer_id BIGINT NOT NULL,
        referred_id BIGINT NOT NULL,
        stars_earned INTEGER DEFAULT 0,
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

    -- Память курсов (Titus)
    CREATE TABLE IF NOT EXISTS course_memory (
        id SERIAL PRIMARY KEY,
        course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
        user_id BIGINT,
        completed_topics JSONB DEFAULT '[]',
        problem_zones JSONB DEFAULT '[]',
        student_name TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_course_memory_course_id ON course_memory(course_id);
    CREATE INDEX IF NOT EXISTS idx_course_memory_user_id ON course_memory(user_id);
    DO $$
    BEGIN
        ALTER TABLE course_memory
        ADD CONSTRAINT unique_course_memory_course_id UNIQUE (course_id);
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END $$;
    
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
    
    -- Парные сессии Silas
    -- Настройки изображений для пользователей
    CREATE TABLE IF NOT EXISTS user_image_settings (
        user_id BIGINT PRIMARY KEY,
        create_model TEXT DEFAULT 'gpt-image-1-mini',
        create_price INTEGER DEFAULT 50,
        -- Важно: upscale_model должен совпадать с ключами в handlers/images.py (MODEL_CONFIGS)
        upscale_model TEXT DEFAULT 'auto_max',
        upscale_price INTEGER DEFAULT 350,
        edit_model TEXT DEFAULT 'gpt-image-1.5',
        edit_price INTEGER DEFAULT 120,
        -- Расширяемая JSON-настройка под новые функции (видео/обработка/стили/инструменты)
        extra_settings JSONB DEFAULT '{}'::jsonb,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_user_image_settings_user ON user_image_settings(user_id);

    -- Конспекты по анализу видео (YouTube)
    CREATE TABLE IF NOT EXISTS video_notes (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        source TEXT DEFAULT 'YouTube',
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_video_notes_user_date ON video_notes(user_id, created_at DESC);
    
    CREATE TABLE IF NOT EXISTS pair_sessions (
        id SERIAL PRIMARY KEY,
        code VARCHAR(10) UNIQUE NOT NULL,
        topic VARCHAR(50) NOT NULL,
        user1_id BIGINT NOT NULL,
        user1_description TEXT,
        user2_id BIGINT,
        user2_description TEXT,
        status VARCHAR(20) DEFAULT 'waiting',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        ended_at TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_pair_sessions_code ON pair_sessions(code);
    CREATE INDEX IF NOT EXISTS idx_pair_sessions_user1 ON pair_sessions(user1_id);
    CREATE INDEX IF NOT EXISTS idx_pair_sessions_user2 ON pair_sessions(user2_id);
    CREATE INDEX IF NOT EXISTS idx_pair_sessions_status ON pair_sessions(status);
    
    -- Магия: профили и логи
    CREATE TABLE IF NOT EXISTS magic_horoscope_profiles (
        user_id BIGINT PRIMARY KEY,
        birth_date DATE,
        birth_time TEXT,
        birth_place TEXT,
        notify_time TEXT,
        tz_offset INTEGER DEFAULT 0,
        last_sent_date DATE,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_magic_horoscope_notify ON magic_horoscope_profiles(notify_time);
    
    CREATE TABLE IF NOT EXISTS magic_tarot_logs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        spread_type TEXT,
        question TEXT,
        image_used BOOLEAN DEFAULT FALSE,
        result_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_magic_tarot_user ON magic_tarot_logs(user_id, created_at DESC);
    
    CREATE TABLE IF NOT EXISTS magic_divination_logs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        divination_type TEXT,
        question TEXT,
        image_used BOOLEAN DEFAULT FALSE,
        result_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_magic_divination_user ON magic_divination_logs(user_id, created_at DESC);
    
    CREATE TABLE IF NOT EXISTS magic_numerology_profiles (
        user_id BIGINT PRIMARY KEY,
        full_name TEXT,
        birth_date DATE,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS magic_rituals_logs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        ritual_type TEXT,
        result_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_magic_rituals_user ON magic_rituals_logs(user_id, created_at DESC);
    
    CREATE TABLE IF NOT EXISTS magic_horoscope_logs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        forecast_type TEXT,
        result_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_magic_horoscope_user ON magic_horoscope_logs(user_id, created_at DESC);
    
    CREATE TABLE IF NOT EXISTS magic_numerology_logs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        calc_type TEXT,
        result_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_magic_numerology_user ON magic_numerology_logs(user_id, created_at DESC);
    
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
        
        # Миграция: добавление полей для Silas
        try:
            await conn.execute("""
                ALTER TABLE user_bots 
                ADD COLUMN IF NOT EXISTS voice_enabled BOOLEAN DEFAULT FALSE;
            """)
            await conn.execute("""
                ALTER TABLE user_bots 
                ADD COLUMN IF NOT EXISTS preferred_duration INTEGER DEFAULT 30;
            """)
            print("✅ Миграция user_bots: поля voice_enabled и preferred_duration добавлены")
        except Exception as e:
            print(f"⚠️ Миграция user_bots: {e}")

        # Миграции: настройки изображений (совместимость + новые поля)
        try:
            await conn.execute("""
                ALTER TABLE user_image_settings
                ADD COLUMN IF NOT EXISTS extra_settings JSONB DEFAULT '{}'::jsonb;
            """)
            await conn.execute("""
                ALTER TABLE user_image_settings
                ALTER COLUMN upscale_model SET DEFAULT 'auto_max';
            """)
            await conn.execute("""
                ALTER TABLE user_image_settings
                ALTER COLUMN edit_model SET DEFAULT 'gpt-image-1.5';
            """)
            # Чиним старые/несовместимые значения (из прежних версий)
            await conn.execute("""
                UPDATE user_image_settings
                SET upscale_model = 'auto_max'
                WHERE upscale_model = 'hd_2048';
            """)
            print("✅ Миграция user_image_settings: extra_settings + дефолты моделей обновлены")
        except Exception as e:
            print(f"⚠️ Миграция user_image_settings: {e}")
    
    print("✅ Все таблицы PostgreSQL созданы")


async def init_db():
    """Проверка подключения к БД"""
    async with get_connection() as conn:
        await conn.execute("SELECT 1")
        try:
            await conn.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS agreement_accepted INTEGER DEFAULT 1"
            )
            await conn.execute(
                "UPDATE users SET agreement_accepted = 1 WHERE agreement_accepted IS NULL"
            )
        except Exception as e:
            print(f"⚠️ Миграция agreement_accepted: {e}")
    print("✅ PostgreSQL connected")


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


async def create_user(
    uid: int,
    uname: str = None,
    fname: str = None,
    referred_by: int = None,
    stars: int = 0,
    agreement_accepted: int = 0
) -> Dict:
    """Создать нового пользователя (бонус начисляется после принятия соглашения)"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, username, first_name, stars, agreement, agreement_accepted, referred_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (user_id) DO NOTHING
            """,
            uid, uname, fname, stars, agreement_accepted, agreement_accepted, referred_by
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


async def get_or_create_user(
    uid: int,
    uname: str = None,
    fname: str = None,
    referred_by: int = None
) -> Dict:
    """Получить пользователя или создать нового"""
    user = await get_user(uid)
    if user:
        return user

    await create_user(uid, uname, fname, referred_by)
    return await get_user(uid)


async def accept_agreement(uid: int):
    """Принять соглашение"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET agreement = 1, agreement_accepted = 1 WHERE user_id = $1",
            uid
        )


async def update_stars(uid: int, used: int):
    """Обновить звёзды после использования"""
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE users
            SET stars = stars - $2,
                total_used = total_used + $2,
                total_requests = total_requests + 1
            WHERE user_id = $1
            """,
            uid, used
        )


async def add_stars(uid: int, amt: int):
    """Добавить звёзды"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET stars = stars + $2 WHERE user_id = $1",
            uid, amt
        )


async def subtract_stars(uid: int, amount: int):
    """Вычесть звёзды"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET stars = stars - $2 WHERE user_id = $1",
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
        return {
            "user_id": uid, 
            "bot": bot, 
            "character": "душевный", 
            "mood": None, 
            "msg_counter": 0,
            "voice_enabled": False,
            "preferred_duration": 30
        }


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
    """Установить настроение для Silas"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO user_bots (user_id, bot, mood, custom_mood)
            VALUES ($1, 'silas', $2, $3)
            ON CONFLICT (user_id, bot)
            DO UPDATE SET mood = $2, custom_mood = $3
            """,
            uid, mood, custom
        )
        # Сохраняем статистику настроения (если не custom)
        if mood != 'custom':
            await conn.execute(
                "INSERT INTO mood_stats (user_id, mood) VALUES ($1, $2)",
                uid, mood
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


async def get_conversation(conversation_id: int) -> Optional[Dict]:
    """Получить диалог по id"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1",
            conversation_id
        )
        return dict(row) if row else None


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


async def create_subscription(uid: int, sub_type: str, stars_limit: int, days: int):
    """Создать подписку"""
    async with get_connection() as conn:
        started = datetime.now()
        expires = started + timedelta(days=days)
        
        await conn.execute(
            """
            INSERT INTO subscriptions (user_id, type, stars_limit, stars_used, started_at, expires_at, is_active)
            VALUES ($1, $2, $3, 0, $4, $5, 1)
            ON CONFLICT (user_id)
            DO UPDATE SET type = $2, stars_limit = $3, stars_used = 0,
                          started_at = $4, expires_at = $5, is_active = 1
            """,
            uid, sub_type, stars_limit, started, expires
        )


async def add_subscription_stars(uid: int, stars: int):
    """Добавить звёзды к лимиту подписки"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE subscriptions SET stars_limit = stars_limit + $2 WHERE user_id = $1",
            uid, stars
        )


async def update_subscription_stars(uid: int, used: int):
    """Обновить использованные звёзды подписки"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE subscriptions SET stars_used = stars_used + $2 WHERE user_id = $1",
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
# STAR USAGE - Использование звёзд
# ============================================================================

async def log_star_usage(uid: int, stars: int, bot_name: str = 'unknown'):
    """Записать использование звёзд"""
    async with get_connection() as conn:
        await conn.execute(
            "INSERT INTO star_usage (user_id, stars_used, bot_name) VALUES ($1, $2, $3)",
            uid, stars, bot_name
        )


async def get_star_usage_stats(uid: int, days: int = 30) -> Dict:
    """Получить статистику использования звёзд"""
    async with get_connection() as conn:
        since = datetime.now() - timedelta(days=days)
        
        total = await conn.fetchval(
            "SELECT COALESCE(SUM(stars_used), 0) FROM star_usage WHERE user_id = $1 AND created_at >= $2",
            uid, since
        )
        
        by_bot = await conn.fetch(
            """
            SELECT bot_name, SUM(stars_used) as total
            FROM star_usage
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


async def get_total_stars_used() -> int:
    """Получить суммарно использованные звёзды по подпискам"""
    async with get_connection() as conn:
        total = await conn.fetchval(
            "SELECT COALESCE(SUM(stars_used), 0) FROM subscriptions"
        )
        return total or 0


async def get_stars_by_model(sub_type: str) -> int:
    """Получить использованные звёзды по типу подписки"""
    async with get_connection() as conn:
        total = await conn.fetchval(
            "SELECT COALESCE(SUM(stars_used), 0) FROM subscriptions WHERE type = $1",
            sub_type
        )
        return total or 0


async def get_all_bots_stars(uid: int) -> Dict[str, int]:
    """Получить статистику использования звёзд по всем ботам"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT bot_name, COALESCE(SUM(stars_used), 0) as total
            FROM star_usage
            WHERE user_id = $1
            GROUP BY bot_name
            """,
            uid
        )
        return {row['bot_name']: row['total'] for row in rows}


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
        
        total_stars = await conn.fetchval(
            "SELECT COALESCE(SUM(stars_earned), 0) FROM referrals WHERE referrer_id = $1",
            uid
        )
        
        return {"count": count, "total_stars": total_stars}


async def add_referral_stars(referrer_id: int, referred_id: int, stars: int, sub_type: str = None):
    """Добавить звёзды за реферала"""
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE referrals
            SET stars_earned = stars_earned + $3, subscription_type = $4
            WHERE referrer_id = $1 AND referred_id = $2
            """,
            referrer_id, referred_id, stars, sub_type
        )
        
        # Добавляем звёзды рефереру
        await add_stars(referrer_id, stars)


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
# COURSE MEMORY
# ============================================================================

async def get_course_memory(course_id: int) -> Dict:
    """Получить память курса"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM course_memory WHERE course_id = $1",
            course_id
        )
        if not row:
            await conn.execute(
                "INSERT INTO course_memory (course_id) VALUES ($1)",
                course_id
            )
            return {
                "course_id": course_id,
                "user_id": None,
                "completed_topics": [],
                "problem_zones": [],
                "student_name": None,
                "last_updated": None
            }
        completed_topics = row["completed_topics"] or []
        problem_zones = row["problem_zones"] or []
        if isinstance(completed_topics, str):
            completed_topics = json.loads(completed_topics)
        if isinstance(problem_zones, str):
            problem_zones = json.loads(problem_zones)
        return {
            "id": row["id"],
            "course_id": row["course_id"],
            "user_id": row["user_id"],
            "completed_topics": completed_topics,
            "problem_zones": problem_zones,
            "student_name": row["student_name"],
            "last_updated": row["last_updated"]
        }


async def save_course_memory(
    course_id: int,
    summary: str = None,
    problem_zones: List = None,
    completed_topics: List = None,
    last_context: str = None,
    user_id: Optional[int] = None,
    student_name: Optional[str] = None
) -> None:
    """Сохранить/обновить память курса"""
    mem = await get_course_memory(course_id)
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO course_memory (course_id, user_id, completed_topics, problem_zones, student_name, last_updated)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (course_id)
            DO UPDATE SET
                user_id = COALESCE($2, course_memory.user_id),
                completed_topics = $3,
                problem_zones = $4,
                student_name = COALESCE($5, course_memory.student_name),
                last_updated = NOW()
            """,
            course_id,
            user_id,
            json.dumps(
                completed_topics if completed_topics is not None else mem.get("completed_topics", []),
                ensure_ascii=False
            ),
            json.dumps(
                problem_zones if problem_zones is not None else mem.get("problem_zones", []),
                ensure_ascii=False
            ),
            student_name
        )


async def add_problem_zone(course_id: int, step: int, topic: str, question: str) -> None:
    """Добавить проблемную зону"""
    mem = await get_course_memory(course_id)
    zones = mem.get("problem_zones", [])
    zones.append({"step": step, "topic": topic, "question": question[:200]})
    await save_course_memory(course_id, problem_zones=zones[-20:])


async def add_completed_topic(
    course_id: int,
    step: int,
    topic: str,
    key_points: list,
    difficulty: str = "medium"
) -> None:
    """Добавить пройденную тему"""
    mem = await get_course_memory(course_id)
    topics = mem.get("completed_topics", [])
    topics.append({"step": step, "topic": topic, "key_points": key_points[:5], "difficulty": difficulty})
    await save_course_memory(course_id, completed_topics=topics)


async def delete_course_memory(course_id: int) -> None:
    """Удалить память курса"""
    async with get_connection() as conn:
        await conn.execute(
            "DELETE FROM course_memory WHERE course_id = $1",
            course_id
        )


async def update_course_step(course_id: int, step: int) -> None:
    """Обновить текущий шаг курса"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE courses SET current = $1 WHERE id = $2",
            step, course_id
        )


async def complete_course(course_id: int) -> None:
    """Отметить курс как завершённый"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE courses SET done = 1 WHERE id = $1",
            course_id
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


# Алиасы для совместимости с handlers
async def get_active_goals(uid: int) -> List[Dict]:
    """Получить активные цели (алиас для get_user_goals)"""
    return await get_user_goals(uid, active_only=True)


async def get_goal_by_id(goal_id: int) -> Optional[Dict]:
    """Получить цель по ID (алиас для get_goal)"""
    return await get_goal(goal_id)


async def create_streak(uid: int, goal_id: int):
    """Создать streak для цели"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO user_streaks (user_id, goal_id, current_streak, best_streak)
            VALUES ($1, $2, 0, 0)
            ON CONFLICT (user_id, goal_id) DO NOTHING
            """,
            uid, goal_id
        )


async def get_goal_streak(goal_id: int, user_id: int) -> Dict:
    """Получить streak для цели"""
    return await get_streak(user_id, goal_id)


async def get_checkin_today(goal_id: int, user_id: int) -> Optional[Dict]:
    """Проверить есть ли отметка за сегодня"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM goal_checkins WHERE goal_id = $1 AND user_id = $2 AND date = CURRENT_DATE",
            goal_id, user_id
        )
        return dict(row) if row else None


async def save_checkin(goal_id: int, user_id: int, is_done: bool = True, note: str = None):
    """Сохранить отметку выполнения"""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO goal_checkins (goal_id, user_id, date, is_done, note)
            VALUES ($1, $2, CURRENT_DATE, $3, $4)
            ON CONFLICT (goal_id, user_id, date) DO UPDATE SET is_done = $3, note = $4
            """,
            goal_id, user_id, 1 if is_done else 0, note
        )
        await update_streak(user_id, goal_id)


async def get_goal_progress(goal_id: int, target: int, period: int) -> Dict:
    """Получить прогресс цели за текущий период"""
    async with get_connection() as conn:
        since = datetime.now() - timedelta(days=period)
        done = await conn.fetchval(
            """
            SELECT COUNT(*) FROM goal_checkins
            WHERE goal_id = $1 AND date >= $2 AND is_done = 1
            """,
            goal_id, since.date()
        )
        return {
            'done': done or 0,
            'target': target,
            'percent': int((done or 0) / target * 100) if target > 0 else 0
        }


async def get_total_streak(uid: int) -> int:
    """Получить общий streak пользователя"""
    async with get_connection() as conn:
        total = await conn.fetchval(
            "SELECT COALESCE(SUM(current_streak), 0) FROM user_streaks WHERE user_id = $1",
            uid
        )
        return total or 0


async def delete_goal(goal_id: int):
    """Деактивировать цель"""
    await deactivate_goal(goal_id)


async def get_monthly_stats_user(uid: int) -> Dict:
    """Получить статистику за 30 дней (для совместимости)"""
    from datetime import date, timedelta
    today = date.today()
    start_date = (today - timedelta(days=30)).isoformat()
    
    async with get_connection() as conn:
        done = await conn.fetchval(
            """
            SELECT COUNT(*) FROM goal_checkins
            WHERE user_id = $1 AND date >= $2 AND is_done = 1
            """,
            uid, start_date
        )
        
        skipped = await conn.fetchval(
            """
            SELECT COUNT(*) FROM goal_checkins
            WHERE user_id = $1 AND date >= $2 AND is_done = 0
            """,
            uid, start_date
        )
        
        total = (done or 0) + (skipped or 0)
        percent = int((done or 0) / total * 100) if total > 0 else 0
        
        # Статистика по неделям
        weeks = []
        for i in range(4):
            week_start = (today - timedelta(days=(i+1)*7)).isoformat()
            week_end = (today - timedelta(days=i*7)).isoformat()
            
            week_done = await conn.fetchval(
                """
                SELECT COUNT(CASE WHEN is_done = 1 THEN 1 END)
                FROM goal_checkins
                WHERE user_id = $1 AND date >= $2 AND date < $3
                """,
                uid, week_start, week_end
            )
            
            week_total = await conn.fetchval(
                """
                SELECT COUNT(*) FROM goal_checkins
                WHERE user_id = $1 AND date >= $2 AND date < $3
                """,
                uid, week_start, week_end
            )
            
            week_total = week_total or 0
            week_done = week_done or 0
            week_percent = int(week_done / week_total * 100) if week_total > 0 else 0
            
            weeks.append({
                'label': f'Неделя {4-i}',
                'percent': week_percent,
                'done': week_done,
                'total': week_total
            })
        
        weeks.reverse()
        
        return {
            'done': done or 0,
            'skipped': skipped or 0,
            'total': total,
            'percent': percent,
            'weeks': weeks
        }


# Алиас для обратной совместимости
async def get_monthly_stats(uid: int) -> Dict:
    """Получить статистику за 30 дней (алиас)"""
    return await get_monthly_stats_user(uid)


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


# Алиасы для совместимости с handlers
async def get_user_routine(uid: int, routine_type: str) -> Optional[Dict]:
    """Получить рутину пользователя (алиас для get_routine)"""
    return await get_routine(uid, routine_type)


async def save_user_routine(uid: int, routine_type: str, items: List[str], reminder_time: str = None):
    """Сохранить рутину пользователя (алиас для save_routine)"""
    await save_routine(uid, routine_type, items, reminder_time)


async def get_today_routine_checkin(uid: int, routine_type: str) -> Optional[Dict]:
    """Получить отметку рутины за сегодня"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM routine_checkins WHERE user_id = $1 AND routine_type = $2 AND date = CURRENT_DATE",
            uid, routine_type
        )
        if row:
            data = dict(row)
            data['completed_items'] = json.loads(data['completed_items'])
            return data
        return None


async def save_routine_checkin(uid: int, routine_type: str, completed_items: List[str],
                               total_items: int, completion_percent: int = None,
                               reflection: str = None, mood: int = None):
    """Сохранить отметку рутины"""
    if completion_percent is None:
        completion_percent = int((len(completed_items) / total_items) * 100) if total_items > 0 else 0
    await add_routine_checkin(uid, routine_type, completed_items, total_items, reflection, mood)


async def get_routine_stats(uid: int, days: int = 7) -> Dict:
    """Получить статистику рутин за N дней"""
    async with get_connection() as conn:
        since = datetime.now() - timedelta(days=days)
        rows = await conn.fetch(
            """
            SELECT * FROM routine_checkins
            WHERE user_id = $1 AND date >= $2
            ORDER BY date
            """,
            uid, since.date()
        )
        checkins = [dict(row) for row in rows]
    
    # Группируем по типу и дате
    morning_stats = []
    evening_stats = []
    
    for i in range(days):
        day = datetime.now().date() - timedelta(days=days-1-i)
        day_str = day.strftime("%d.%m")
        
        morning = next((c for c in checkins if c['date'] == day and c['routine_type'] == "morning"), None)
        evening = next((c for c in checkins if c['date'] == day and c['routine_type'] == "evening"), None)
        
        morning_stats.append({
            "date": day_str,
            "percent": morning['completion_percent'] if morning else 0
        })
        evening_stats.append({
            "date": day_str,
            "percent": evening['completion_percent'] if evening else 0,
            "mood": evening['mood'] if evening else 0
        })
    
    avg_percent = sum(m['percent'] for m in morning_stats) / len(morning_stats) if morning_stats else 0
    moods = [e['mood'] for e in evening_stats if e['mood'] and e['mood'] > 0]
    avg_mood = sum(moods) / len(moods) if moods else 0
    
    return {
        "morning": morning_stats,
        "evening": evening_stats,
        "avg_percent": int(avg_percent),
        "avg_mood": avg_mood
    }


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


# Алиасы для совместимости с handlers
async def get_today_mood(uid: int) -> Optional[Dict]:
    """Получить настроение за сегодня"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM mood_logs WHERE user_id = $1 AND date = CURRENT_DATE",
            uid
        )
        if row:
            data = dict(row)
            if data.get('tags'):
                data['tags'] = json.loads(data['tags'])
            return data
        return None


async def save_mood_log(uid: int, mood: int, energy: int, tags: List[str], note: str = None):
    """Сохранить запись настроения"""
    await log_mood(uid, mood, energy, note, tags)


async def save_meditation_log(uid: int, duration: int, med_type: str):
    """Сохранить запись медитации"""
    await log_meditation(uid, duration, med_type)


async def get_meditation_streak(uid: int) -> int:
    """Получить streak медитаций"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT date FROM meditation_logs
            WHERE user_id = $1
            ORDER BY date DESC
            """,
            uid
        )
        dates = [row['date'] for row in rows]
    
    if not dates:
        return 0
    
    streak = 0
    expected = datetime.now().date()
    
    for d in dates:
        if d == expected:
            streak += 1
            expected = expected - timedelta(days=1)
        elif d < expected:
            break
    
    return streak


async def get_mood_stats(uid: int, days: int = 14) -> Dict:
    """Получить статистику настроения за N дней"""
    logs = await get_mood_logs(uid, days)
    
    if not logs:
        return {"logs": [], "avg_mood": 0, "avg_energy": 0, "top_tag": None}
    
    mood_sum = sum(l['mood'] for l in logs)
    energy_sum = sum(l['energy'] for l in logs)
    
    # Считаем теги
    from collections import Counter
    all_tags = []
    for l in logs:
        if l.get('tags'):
            all_tags.extend(l['tags'])
    
    tag_counts = Counter(all_tags)
    top_tag = tag_counts.most_common(1)[0][0] if tag_counts else None
    
    return {
        "logs": [{"date": l['date'].strftime("%d.%m") if isinstance(l['date'], date) else str(l['date']), "mood": l['mood']} for l in logs],
        "avg_mood": mood_sum / len(logs),
        "avg_energy": energy_sum / len(logs),
        "top_tag": top_tag
    }


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


# ============================================================================
# ПЛАТЕЖИ - Подписки/звёзды
# ============================================================================

async def create_transaction(uid: int, amount: float, stars: int, tx_type: str) -> int:
    """Создать платёжную транзакцию"""
    async with get_connection() as conn:
        tx_id = await conn.fetchval(
            """
            INSERT INTO payment_transactions (user_id, amount, stars, type, status)
            VALUES ($1, $2, $3, $4, 'pending')
            RETURNING id
            """,
            uid, amount, stars, tx_type
        )
        return int(tx_id)


async def complete_transaction(tx_id: int, robokassa_id: int = None):
    """Подтвердить платёжную транзакцию"""
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE payment_transactions
            SET status = 'completed',
                robokassa_id = $2,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = $1
            """,
            tx_id, robokassa_id
        )


async def get_transaction(tx_id: int) -> Optional[Dict]:
    """Получить платёжную транзакцию"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM payment_transactions WHERE id = $1",
            tx_id
        )
        return dict(row) if row else None


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


# Алиасы для совместимости с handlers
async def get_user_budget(uid: int) -> Optional[Dict]:
    """Получить бюджет пользователя (алиас для get_budget)"""
    return await get_budget(uid)


async def save_user_budget(uid: int, monthly_limit: float):
    """Сохранить бюджет пользователя"""
    await save_budget(uid, monthly_limit, {}, 'RUB')


async def save_transaction(uid: int, trans_type: str, amount: float, category: str, description: str):
    """Сохранить транзакцию"""
    from datetime import date
    await add_transaction(uid, trans_type, amount, category, description, date.today().isoformat())


async def get_month_expenses(uid: int) -> Dict:
    """Получить расходы за текущий месяц"""
    from datetime import date
    today = date.today()
    stats = await get_monthly_stats(uid, today.year, today.month)
    return {"total": stats.get("expense", 0)}


async def get_month_total(uid: int) -> float:
    """Получить общую сумму расходов за месяц"""
    stats = await get_month_expenses(uid)
    return stats.get("total", 0)


async def get_expenses_by_period(uid: int, start_date: date) -> List[Dict]:
    """Получить расходы за период"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM transactions
            WHERE user_id = $1 AND type = 'expense' AND date >= $2
            ORDER BY date DESC
            """,
            uid, start_date.isoformat()
        )
        return [dict(row) for row in rows]


async def get_top_categories(uid: int, limit: int = 5) -> List[tuple]:
    """Получить топ категорий по расходам"""
    from datetime import date
    today = date.today()
    stats = await get_monthly_stats(uid, today.year, today.month)
    by_category = stats.get("by_category", {})
    sorted_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
    return sorted_cats[:limit]


async def get_average_expense(uid: int) -> float:
    """Получить средний чек"""
    from datetime import date
    today = date.today()
    start_date = today.replace(day=1).isoformat()
    
    async with get_connection() as conn:
        avg = await conn.fetchval(
            """
            SELECT AVG(amount) FROM transactions
            WHERE user_id = $1 AND type = 'expense' AND date >= $2
            """,
            uid, start_date
        )
        return float(avg) if avg else 0


async def get_max_expense(uid: int) -> Optional[Dict]:
    """Получить максимальную трату"""
    from datetime import date
    today = date.today()
    start_date = today.replace(day=1).isoformat()
    
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM transactions
            WHERE user_id = $1 AND type = 'expense' AND date >= $2
            ORDER BY amount DESC
            LIMIT 1
            """,
            uid, start_date
        )
        return dict(row) if row else None


async def get_last_month_total(uid: int) -> float:
    """Получить расходы за прошлый месяц"""
    from datetime import date
    today = date.today()
    if today.month == 1:
        last_month = 12
        last_year = today.year - 1
    else:
        last_month = today.month - 1
        last_year = today.year
    
    stats = await get_monthly_stats(uid, last_year, last_month)
    return stats.get("expense", 0)


async def get_month_expenses_detailed(uid: int) -> Dict:
    """Получить детальную статистику расходов за месяц"""
    from datetime import date
    today = date.today()
    start_date = today.replace(day=1).isoformat()
    
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT category, SUM(amount) as total, COUNT(*) as count
            FROM transactions
            WHERE user_id = $1 AND type = 'expense' AND date >= $2
            GROUP BY category
            ORDER BY total DESC
            """,
            uid, start_date
        )
        
        result = {}
        for row in rows:
            cat_name = EXPENSE_CATEGORIES.get(row['category'], row['category'])
            result[cat_name] = {
                'total': float(row['total']),
                'count': row['count']
            }
    
    return result


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


async def get_available_stars(uid: int) -> int:
    """
    Получить доступные звёзды:
    - Если есть активная подписка -> звёзды из подписки
    - Если нет подписки -> бонусные звёзды из users.stars
    """
    sub = await get_subscription(uid)
    
    # Есть активная подписка
    if sub and sub['is_active']:
        # Проверяем не истекла ли подписка
        from datetime import datetime
        if sub['expires_at'] and sub['expires_at'] > datetime.now():
            return sub['stars_limit'] - sub['stars_used']
    
    # Нет подписки - берём бонусные звёзды
    user = await get_user(uid)
    return user['stars'] if user else 0


async def use_stars_smart(uid: int, amount: int, bot_name: str = None) -> bool:
    """
    Списать звёзды:
    - Если есть активная подписка -> из подписки
    - Если нет подписки -> из users.stars (бонусные)
    - Разрешаем уход в минус, но БЛОКИРУЕМ дальнейшее использование при отрицательном балансе
    - Записываем статистику по ботам
    """
    # Проверяем доступный баланс ПЕРЕД списанием
    available = await get_available_stars(uid)
    
    # Если баланс уже отрицательный - БЛОКИРУЕМ
    if available < 0:
        return False
    
    sub = await get_subscription(uid)
    
    # Записываем использование звёзд по ботам
    if bot_name:
        await log_star_usage(uid, amount, bot_name)
    
    # Есть активная подписка
    if sub and sub['is_active']:
        from datetime import datetime
        if sub['expires_at'] and sub['expires_at'] > datetime.now():
            await update_subscription_stars(uid, amount)
            return True
    
    # Нет подписки - списываем бонусные
    await update_stars(uid, amount)
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
    return "anthropic/claude-sonnet-4"  # дефолтная модель для бонусных звёзд


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


# ============================================================================
# MOOD STATS - Статистика настроения
# ============================================================================

async def get_mood_stats(uid: int) -> Dict:
    """Получить статистику настроения за последние 30 дней"""
    async with get_connection() as conn:
        since = datetime.now() - timedelta(days=30)
        
        good = await conn.fetchval(
            "SELECT COUNT(*) FROM mood_stats WHERE user_id = $1 AND mood = 'good' AND at >= $2",
            uid, since
        )
        tired = await conn.fetchval(
            "SELECT COUNT(*) FROM mood_stats WHERE user_id = $1 AND mood = 'tired' AND at >= $2",
            uid, since
        )
        pain = await conn.fetchval(
            "SELECT COUNT(*) FROM mood_stats WHERE user_id = $1 AND mood = 'pain' AND at >= $2",
            uid, since
        )
        
        return {
            'good': good or 0,
            'tired': tired or 0,
            'pain': pain or 0
        }


# ============================================================================
# НАСТРОЙКИ SILAS
# ============================================================================

async def set_silas_settings(uid: int, duration: int = None, voice_enabled: bool = None):
    """Сохранить настройки Silas для пользователя"""
    async with get_connection() as conn:
        # Используем COALESCE для обновления только переданных полей
        # Если параметр None, COALESCE вернёт старое значение (не обновляем)
        await conn.execute('''
            INSERT INTO user_bots (user_id, bot, preferred_duration, voice_enabled)
            VALUES ($1, 'silas', COALESCE($2, 30), COALESCE($3, FALSE))
            ON CONFLICT (user_id, bot) DO UPDATE SET
                preferred_duration = CASE 
                    WHEN $2 IS NOT NULL THEN $2 
                    ELSE user_bots.preferred_duration 
                END,
                voice_enabled = CASE 
                    WHEN $3 IS NOT NULL THEN $3 
                    ELSE user_bots.voice_enabled 
                END
        ''', uid, duration, voice_enabled)


async def get_silas_settings(uid: int) -> dict:
    """Получить настройки Silas для пользователя"""
    async with get_connection() as conn:
        row = await conn.fetchrow('''
            SELECT mood, custom_mood, preferred_duration, voice_enabled
            FROM user_bots
            WHERE user_id = $1 AND bot = 'silas'
        ''', uid)
        
        if row:
            return {
                'mood': row['mood'] or '',
                'custom_mood': row['custom_mood'] or '',
                'duration': row['preferred_duration'] or 30,
                'voice_enabled': row['voice_enabled'] or False
            }
        
        # Если записи нет — возвращаем значения по умолчанию
        return {
            'mood': '',
            'custom_mood': '',
            'duration': 30,
            'voice_enabled': False
        }


# ============================================================================
# ПАРНЫЕ СЕССИИ SILAS
# ============================================================================

def generate_pair_code() -> str:
    """Генерация уникального кода для парной сессии (6 символов)"""
    alphabet = string.ascii_uppercase + string.digits
    # Убираем похожие символы: 0, O, I, 1, L
    alphabet = alphabet.replace('0', '').replace('O', '').replace('I', '').replace('1', '').replace('L', '')
    return ''.join(secrets.choice(alphabet) for _ in range(6))


async def create_pair_session(uid: int, topic: str, description: str = None) -> str:
    """Создать парную сессию и вернуть код приглашения"""
    async with get_connection() as conn:
        # Генерируем уникальный код
        for _ in range(10):  # 10 попыток на случай коллизии
            code = generate_pair_code()
            try:
                await conn.execute('''
                    INSERT INTO pair_sessions (code, topic, user1_id, user1_description, status)
                    VALUES ($1, $2, $3, $4, 'waiting')
                ''', code, topic, uid, description)
                return code
            except Exception:
                continue  # Код уже существует, пробуем другой
        
        raise Exception("Не удалось создать уникальный код")


async def join_pair_session(uid: int, code: str, description: str = None) -> dict:
    """Присоединиться к парной сессии по коду"""
    async with get_connection() as conn:
        # Проверяем существование и статус сессии
        row = await conn.fetchrow('''
            SELECT id, user1_id, status
            FROM pair_sessions
            WHERE code = $1
        ''', code.upper())
        
        if not row:
            return {'success': False, 'error': 'Сессия не найдена'}
        
        if row['status'] != 'waiting':
            return {'success': False, 'error': 'Сессия уже началась или завершена'}
        
        if row['user1_id'] == uid:
            return {'success': False, 'error': 'Нельзя присоединиться к своей сессии'}
        
        # Присоединяемся и активируем сессию
        await conn.execute('''
            UPDATE pair_sessions
            SET user2_id = $1, user2_description = $2, status = 'active', started_at = CURRENT_TIMESTAMP
            WHERE code = $3
        ''', uid, description, code.upper())
        
        return {'success': True, 'session_id': row['id']}


async def get_pair_session(code: str) -> dict:
    """Получить информацию о парной сессии"""
    async with get_connection() as conn:
        row = await conn.fetchrow('''
            SELECT id, code, topic, user1_id, user1_description, user2_id, user2_description,
                   status, created_at, started_at, ended_at
            FROM pair_sessions
            WHERE code = $1
        ''', code.upper())
        
        if not row:
            return None
        
        return dict(row)


async def get_pair_session_with_names(code: str) -> dict:
    """Получить данные парной сессии с именами участников из таблицы users"""
    async with get_connection() as conn:
        row = await conn.fetchrow('''
            SELECT 
                ps.id, ps.code, ps.topic, 
                ps.user1_id, ps.user1_description, 
                ps.user2_id, ps.user2_description,
                ps.status, ps.created_at, ps.started_at, ps.ended_at,
                u1.first_name as user1_name,
                u1.username as user1_username,
                u2.first_name as user2_name,
                u2.username as user2_username
            FROM pair_sessions ps
            LEFT JOIN users u1 ON ps.user1_id = u1.user_id
            LEFT JOIN users u2 ON ps.user2_id = u2.user_id
            WHERE ps.code = $1
        ''', code.upper())
        
        if not row:
            return None
        
        data = dict(row)
        
        # Fallback если имя пустое или None
        data['user1_name'] = data.get('user1_name') or data.get('user1_username') or 'Участник 1'
        if data.get('user2_id'):
            data['user2_name'] = data.get('user2_name') or data.get('user2_username') or 'Участник 2'
        else:
            data['user2_name'] = None
        
        return data


async def get_user_pair_session(uid: int) -> dict:
    """Получить активную парную сессию пользователя"""
    async with get_connection() as conn:
        row = await conn.fetchrow('''
            SELECT id, code, topic, user1_id, user1_description, user2_id, user2_description,
                   status, created_at, started_at, ended_at
            FROM pair_sessions
            WHERE (user1_id = $1 OR user2_id = $1) AND status IN ('waiting', 'active')
            ORDER BY created_at DESC
            LIMIT 1
        ''', uid)
        
        if not row:
            return None
        
        return dict(row)


async def end_pair_session(code: str):
    """Завершить парную сессию"""
    async with get_connection() as conn:
        await conn.execute('''
            UPDATE pair_sessions
            SET status = 'ended', ended_at = CURRENT_TIMESTAMP
            WHERE code = $1
        ''', code.upper())


async def cancel_pair_session(code: str, uid: int) -> bool:
    """Отменить парную сессию (только создатель, только в статусе waiting)"""
    async with get_connection() as conn:
        result = await conn.execute('''
            UPDATE pair_sessions
            SET status = 'ended', ended_at = CURRENT_TIMESTAMP
            WHERE code = $1 AND user1_id = $2 AND status = 'waiting'
        ''', code.upper(), uid)
        
        return 'UPDATE 1' in result


async def get_all_user_pair_sessions(uid: int) -> list:
    """Получить все парные сессии пользователя (как создателя, так и участника)"""
    async with get_connection() as conn:
        rows = await conn.fetch('''
            SELECT id, code, topic, user1_id, user2_id, status, created_at, started_at, ended_at
            FROM pair_sessions
            WHERE user1_id = $1 OR user2_id = $1
            ORDER BY created_at DESC
        ''', uid)
        
        sessions = []
        for row in rows:
            session = dict(row)
            # Определяем роль пользователя
            if session['user1_id'] == uid:
                session['role'] = 'creator'
            else:
                session['role'] = 'partner'
            sessions.append(session)
        
        return sessions


async def delete_pair_session_by_id(session_id: int, uid: int) -> bool:
    """Удалить парную сессию по ID (только если пользователь является участником)"""
    async with get_connection() as conn:
        # Проверяем что пользователь является участником
        row = await conn.fetchrow('''
            SELECT id FROM pair_sessions
            WHERE id = $1 AND (user1_id = $2 OR user2_id = $2)
        ''', session_id, uid)
        
        if not row:
            return False
        
        # Удаляем сессию
        await conn.execute('DELETE FROM pair_sessions WHERE id = $1', session_id)
        return True


async def delete_all_user_pair_sessions(uid: int) -> int:
    """Удалить все парные сессии пользователя (как создателя, так и участника)"""
    async with get_connection() as conn:
        result = await conn.execute('''
            DELETE FROM pair_sessions
            WHERE user1_id = $1 OR user2_id = $1
        ''', uid)
        
        # Возвращаем количество удалённых строк
        if 'DELETE' in result:
            # Извлекаем число из строки вида "DELETE 5"
            try:
                return int(result.split()[-1])
            except:
                return 0
        return 0


# ============================================================================
# SESSIONS - Сессии психолога
# ============================================================================

async def start_session(uid: int, dur: int) -> int:
    """Создать новую сессию"""
    async with get_connection() as conn:
        session_id = await conn.fetchval(
            """
            INSERT INTO sessions (user_id, started, duration)
            VALUES ($1, CURRENT_TIMESTAMP, $2)
            RETURNING id
            """,
            uid, dur
        )
        return session_id


async def end_session(sid: int):
    """Завершить сессию"""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE sessions SET ended = CURRENT_TIMESTAMP WHERE id = $1",
            sid
        )


# ============================================================================
# НАСТРОЙКИ ИЗОБРАЖЕНИЙ
# ============================================================================

async def get_image_settings(user_id: int) -> dict:
    """Получить настройки изображений пользователя"""
    async with get_connection() as conn:
        row = await conn.fetchrow('''
            SELECT create_model, create_price, upscale_model, upscale_price, edit_model, edit_price, extra_settings
            FROM user_image_settings
            WHERE user_id = $1
        ''', user_id)
        
        if row:
            data = dict(row)
            extra = data.get("extra_settings")
            if extra is None:
                data["extra_settings"] = {}
            elif isinstance(extra, str):
                try:
                    data["extra_settings"] = json.loads(extra)
                except Exception:
                    data["extra_settings"] = {}
            return data
        
        # Возвращаем дефолтные значения если настроек нет
        return {
            "create_model": "gpt-image-1-mini",
            "create_price": 50,
            "upscale_model": "auto_max",
            "upscale_price": 350,
            "edit_model": "gpt-image-1.5",
            "edit_price": 120
            ,
            "extra_settings": {}
        }


async def save_image_settings(user_id: int, settings: dict) -> bool:
    """Сохранить настройки изображений"""
    async with get_connection() as conn:
        extra_settings = settings.get("extra_settings") or {}
        # На всякий случай нормализуем тип (jsonb)
        if isinstance(extra_settings, str):
            try:
                extra_settings = json.loads(extra_settings)
            except Exception:
                extra_settings = {}
        # asyncpg для jsonb ожидает строку JSON (иначе "expected str, got dict")
        extra_settings_json = json.dumps(extra_settings, ensure_ascii=False)

        await conn.execute('''
            INSERT INTO user_image_settings (
                user_id, create_model, create_price, upscale_model, upscale_price, 
                edit_model, edit_price, extra_settings, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                create_model = EXCLUDED.create_model,
                create_price = EXCLUDED.create_price,
                upscale_model = EXCLUDED.upscale_model,
                upscale_price = EXCLUDED.upscale_price,
                edit_model = EXCLUDED.edit_model,
                edit_price = EXCLUDED.edit_price,
                extra_settings = EXCLUDED.extra_settings,
                updated_at = CURRENT_TIMESTAMP
        ''', 
            user_id,
            settings.get("create_model", "gpt-image-1-mini"),
            settings.get("create_price", 50),
            settings.get("upscale_model", "auto_max"),
            settings.get("upscale_price", 350),
            settings.get("edit_model", "gpt-image-1.5"),
            settings.get("edit_price", 120),
            extra_settings_json
        )
        return True


# ===========================
# === VIDEO NOTES (Titus) ===
# ===========================

async def add_video_note(user_id: int, *, title: str, url: str, text: str, source: str = "YouTube") -> int:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO video_notes (user_id, source, title, url, text)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            int(user_id), source, title, url, text
        )
        return int(row["id"]) if row else 0


async def list_video_notes(user_id: int) -> List[Dict]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, source, title, url, text, created_at
            FROM video_notes
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 200
            """,
            int(user_id)
        )
        out: List[Dict] = []
        for r in rows:
            full = r["text"] or ""
            preview = full.replace("\r", "").replace("\n", " ").strip()
            if len(preview) > 90:
                preview = preview[:90].rstrip() + "…"
            out.append({
                "id": int(r["id"]),
                "source": r["source"] or "YouTube",
                "title": r["title"] or "Видео",
                "url": r["url"] or "",
                "text": full,
                "date_label": r["created_at"].strftime("%d %b %Y") if r["created_at"] else "",
                "preview": preview or "—",
            })
        return out


async def get_video_note(user_id: int, note_id: int) -> Optional[Dict]:
    async with get_connection() as conn:
        r = await conn.fetchrow(
            """
            SELECT id, source, title, url, text, created_at
            FROM video_notes
            WHERE user_id = $1 AND id = $2
            """,
            int(user_id), int(note_id)
        )
        if not r:
            return None
        return {
            "id": int(r["id"]),
            "source": r["source"] or "YouTube",
            "title": r["title"] or "Видео",
            "url": r["url"] or "",
            "text": r["text"] or "",
            "date_label": r["created_at"].strftime("%d %B %Y") if r["created_at"] else "",
        }


async def delete_video_note(user_id: int, note_id: int) -> bool:
    async with get_connection() as conn:
        res = await conn.execute(
            "DELETE FROM video_notes WHERE user_id = $1 AND id = $2",
            int(user_id), int(note_id)
        )
        try:
            n = int(str(res).split()[-1])
            return n > 0
        except Exception:
            return False


# ============================================================================
# MAGIC - Гороскопы, Таро, Гадания, Нумерология
# ============================================================================

async def save_magic_horoscope_profile(
    user_id: int,
    birth_date: Optional[date] = None,
    birth_time: str = None,
    birth_place: str = None,
    notify_time: str = None,
    tz_offset: int = 0
) -> bool:
    """Сохранить профиль гороскопа."""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO magic_horoscope_profiles
            (user_id, birth_date, birth_time, birth_place, notify_time, tz_offset, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                birth_date = EXCLUDED.birth_date,
                birth_time = EXCLUDED.birth_time,
                birth_place = EXCLUDED.birth_place,
                notify_time = EXCLUDED.notify_time,
                tz_offset = EXCLUDED.tz_offset,
                updated_at = CURRENT_TIMESTAMP
            """,
            int(user_id), birth_date, birth_time, birth_place, notify_time, int(tz_offset or 0)
        )
        return True


async def get_magic_horoscope_profile(user_id: int) -> Optional[Dict]:
    """Получить профиль гороскопа."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM magic_horoscope_profiles WHERE user_id = $1",
            int(user_id)
        )
        if not row:
            return None
        d = dict(row)
        # Конвертация date объектов в ISO строки
        if d.get("birth_date") and isinstance(d["birth_date"], date):
            d["birth_date"] = d["birth_date"].isoformat()
        if d.get("last_sent_date") and isinstance(d["last_sent_date"], date):
            d["last_sent_date"] = d["last_sent_date"].isoformat()
        if d.get("updated_at"):
            d["updated_at"] = d["updated_at"].strftime("%Y-%m-%d %H:%M")
        return d


async def get_magic_horoscope_profiles() -> List[Dict]:
    """Получить все профили гороскопа для уведомлений."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM magic_horoscope_profiles WHERE notify_time IS NOT NULL"
        )
        items = []
        for r in rows:
            d = dict(r)
            # Конвертация date объектов в ISO строки
            if d.get("birth_date") and isinstance(d["birth_date"], date):
                d["birth_date"] = d["birth_date"].isoformat()
            if d.get("last_sent_date") and isinstance(d["last_sent_date"], date):
                d["last_sent_date"] = d["last_sent_date"].isoformat()
            if d.get("created_at"):
                d["created_at"] = d["created_at"].strftime("%Y-%m-%d %H:%M")
            items.append(d)
        return items


async def update_magic_horoscope_last_sent(user_id: int, sent_date: date) -> bool:
    """Обновить дату последней отправки."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE magic_horoscope_profiles SET last_sent_date = $1 WHERE user_id = $2",
            sent_date, int(user_id)
        )
        return True


async def save_magic_tarot_log(
    user_id: int,
    spread_type: str = None,
    question: str = None,
    image_used: bool = False,
    result_text: str = ""
) -> None:
    """Сохранить лог Таро."""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO magic_tarot_logs
            (user_id, spread_type, question, image_used, result_text)
            VALUES ($1, $2, $3, $4, $5)
            """,
            int(user_id), spread_type, question, bool(image_used), result_text
        )


async def save_magic_divination_log(
    user_id: int,
    divination_type: str = None,
    question: str = None,
    image_used: bool = False,
    result_text: str = ""
) -> None:
    """Сохранить лог гаданий."""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO magic_divination_logs
            (user_id, divination_type, question, image_used, result_text)
            VALUES ($1, $2, $3, $4, $5)
            """,
            int(user_id), divination_type, question, bool(image_used), result_text
        )


async def save_magic_numerology_profile(user_id: int, full_name: str = None, birth_date: Optional[date] = None) -> bool:
    """Сохранить профиль нумерологии."""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO magic_numerology_profiles
            (user_id, full_name, birth_date, updated_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                birth_date = EXCLUDED.birth_date,
                updated_at = CURRENT_TIMESTAMP
            """,
            int(user_id), full_name, birth_date
        )
        return True


async def get_magic_numerology_profile(user_id: int) -> Optional[Dict]:
    """Получить профиль нумерологии."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM magic_numerology_profiles WHERE user_id = $1",
            int(user_id)
        )
        if not row:
            return None
        d = dict(row)
        # Конвертация date объектов в ISO строки
        if d.get("birth_date") and isinstance(d["birth_date"], date):
            d["birth_date"] = d["birth_date"].isoformat()
        if d.get("updated_at"):
            d["updated_at"] = d["updated_at"].strftime("%Y-%m-%d %H:%M")
        return d


async def save_magic_ritual_log(user_id: int, ritual_type: str, result_text: str) -> None:
    """Сохранить лог ритуалов."""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO magic_rituals_logs (user_id, ritual_type, result_text)
            VALUES ($1, $2, $3)
            """,
            int(user_id), ritual_type, result_text
        )


async def save_magic_horoscope_log(user_id: int, forecast_type: str, result_text: str) -> None:
    """Сохранить лог гороскопов."""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO magic_horoscope_logs (user_id, forecast_type, result_text)
            VALUES ($1, $2, $3)
            """,
            int(user_id), forecast_type, result_text
        )


async def save_magic_numerology_log(user_id: int, calc_type: str, result_text: str) -> None:
    """Сохранить лог нумерологии."""
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO magic_numerology_logs (user_id, calc_type, result_text)
            VALUES ($1, $2, $3)
            """,
            int(user_id), calc_type, result_text
        )


async def list_magic_history(
    user_id: int,
    table: str,
    limit: int = 20,
    kind_filter: str = None,
    date_from: date = None,
    date_to: date = None
) -> List[Dict]:
    """Универсальная история магии."""
    allowed = {
        "tarot": "magic_tarot_logs",
        "divination": "magic_divination_logs",
        "rituals": "magic_rituals_logs",
        "horoscope": "magic_horoscope_logs",
        "numerology": "magic_numerology_logs",
    }
    type_columns = {
        "tarot": "spread_type",
        "divination": "divination_type",
        "rituals": "ritual_type",
        "horoscope": "forecast_type",
        "numerology": "calc_type",
    }
    table_name = allowed.get(table)
    if not table_name:
        return []
    where = ["user_id = $1"]
    params = [int(user_id)]
    idx = 2
    if kind_filter:
        col = type_columns.get(table)
        if col:
            where.append(f"{col} = ${idx}")
            params.append(kind_filter)
            idx += 1
    if date_from:
        where.append(f"created_at::date >= ${idx}")
        params.append(date_from)
        idx += 1
    if date_to:
        where.append(f"created_at::date <= ${idx}")
        params.append(date_to)
        idx += 1
    params.append(int(limit))
    async with get_connection() as conn:
        rows = await conn.fetch(
            f"""
            SELECT *
            FROM {table_name}
            WHERE {" AND ".join(where)}
            ORDER BY created_at DESC
            LIMIT ${idx}
            """,
            *params
        )
        items = []
        for r in rows:
            d = dict(r)
            if d.get("created_at"):
                d["created_at"] = d["created_at"].strftime("%Y-%m-%d %H:%M")
            items.append(d)
        return items


# ============================================================================
# REFERRAL SYSTEM - Недостающие функции
# ============================================================================

async def get_referrer_id(uid: int) -> Optional[int]:
    """
    Получить ID реферера пользователя.

    Args:
        uid: ID пользователя

    Returns:
        ID реферера или None если нет реферера
    """
    async with get_connection() as conn:
        return await conn.fetchval(
            "SELECT referred_by FROM users WHERE user_id = $1",
            uid
        )


async def add_referral_reward(referrer_id: int, referred_id: int, stars: int, sub_type: str = None):
    """
    Добавить звёзды за реферала.
    Алиас для add_referral_stars() для совместимости с handlers.

    Args:
        referrer_id: ID реферера (кто получает бонус)
        referred_id: ID приглашённого (кто купил подписку)
        stars: Количество звёзд для начисления
        sub_type: Тип подписки (mini/standard)
    """
    return await add_referral_stars(referrer_id, referred_id, stars, sub_type)


class PostgresDB:
    """
    Класс-заглушка для обратной совместимости.
    Не используется в бизнес-логике, но позволяет импортировать PostgresDB.
    """
    pass
