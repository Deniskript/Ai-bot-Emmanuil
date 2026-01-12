import aiosqlite
import json
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List
import os
from config import DATABASE_PATH, NEW_USER_BONUS, MODEL as config_MODEL


# Создаём директорию только если путь содержит папку
if os.path.dirname(DATABASE_PATH):
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)


async def migrate_token_usage_table():
    """Миграция таблицы token_usage - добавление колонки bot_name"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Проверяем есть ли колонка bot_name
        cursor = await db.execute("PRAGMA table_info(token_usage)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'bot_name' not in column_names:
            print("🔄 Миграция: добавление колонки bot_name в token_usage...")
            # Добавляем колонку bot_name со значением по умолчанию
            await db.execute("ALTER TABLE token_usage ADD COLUMN bot_name TEXT DEFAULT 'unknown'")
            # Создаём индекс для новой колонки
            await db.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_bot ON token_usage(user_id, bot_name)")
            await db.commit()
            print("✅ Миграция завершена успешно!")


async def migrate_referral_system():
    """Миграция для реферальной системы"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Проверяем есть ли колонка referred_by
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'referred_by' not in column_names:
            print("🔄 Миграция: добавление реферальной системы...")
            await db.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_referred ON users(referred_by)")
            await db.commit()
            print("✅ Реферальная система добавлена!")
        
        # Создаём таблицу рефералов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                tokens_earned INTEGER DEFAULT 0,
                subscription_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(referred_id)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)")
        await db.commit()


async def migrate_voice_mode():
    """Миграция для голосового режима"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Проверяем есть ли колонка voice_gender
        cursor = await db.execute("PRAGMA table_info(user_bots)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'voice_gender' not in column_names:
            print("🔄 Миграция: добавление голосового режима...")
            await db.execute("ALTER TABLE user_bots ADD COLUMN voice_gender TEXT DEFAULT NULL")
            await db.commit()
            print("✅ Голосовой режим добавлен!")


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bot TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, created_at DESC);
        
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            model TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, timestamp);
        
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            tokens INTEGER DEFAULT 25000, total_used INTEGER DEFAULT 0,
            total_requests INTEGER DEFAULT 0, is_blocked INTEGER DEFAULT 0,
            agreement INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_users_blocked ON users(is_blocked);
        CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at);
        CREATE TABLE IF NOT EXISTS user_bots (
            user_id INTEGER, bot TEXT, character TEXT DEFAULT 'душевный',
            mood TEXT, custom_mood TEXT, msg_counter INTEGER DEFAULT 0,
            voice_gender TEXT DEFAULT NULL,
            PRIMARY KEY(user_id, bot)
        );
        CREATE TABLE IF NOT EXISTS bot_memory (
            user_id INTEGER, bot TEXT, facts TEXT DEFAULT '[]',
            PRIMARY KEY(user_id, bot)
        );
        CREATE TABLE IF NOT EXISTS bot_msgs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, bot TEXT,
            role TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_bot_msgs_user_bot ON bot_msgs(user_id, bot, created_at);
        CREATE TABLE IF NOT EXISTS mood_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, mood TEXT,
            at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            started TIMESTAMP, duration INTEGER, ended TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT,
            total INTEGER, current INTEGER DEFAULT 1, done INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_courses_user ON courses(user_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS user_profile (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER,
            gender TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tokens_used INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_token_usage_user_date ON token_usage(user_id, created_at);
        CREATE TABLE IF NOT EXISTS bot_cfg (
            bot TEXT PRIMARY KEY, enabled INTEGER DEFAULT 1,
            model TEXT, version TEXT DEFAULT '1.0.0'
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS server_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active_users INTEGER, rpm INTEGER, avg_time REAL, load_pct INTEGER
        );
        INSERT OR IGNORE INTO settings VALUES ('maintenance', '0');
        INSERT OR IGNORE INTO settings VALUES ('warn_threshold', '70');
        INSERT OR IGNORE INTO settings VALUES ('crit_threshold', '90');
        INSERT OR IGNORE INTO bot_cfg VALUES ('luca',1,'gpt-4o-mini','1.0.0');
        INSERT OR IGNORE INTO bot_cfg VALUES ('silas',1,'gpt-4o','1.0.0');
        INSERT OR IGNORE INTO bot_cfg VALUES ('titus',1,'gpt-4o-mini','1.0.0');
        """)
        await db.commit()
    
    # Запускаем миграции для существующих БД
    await migrate_token_usage_table()
    await migrate_referral_system()
    await migrate_voice_mode()


async def get_user(uid: int) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        r = await c.fetchone()
        return dict(r) if r else None


async def create_user(uid: int, uname: str=None, fname: str=None, referred_by: int=None) -> Dict:
    """Создаём пользователя с бонусными токенами, БЕЗ подписки"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT INTO users (user_id,username,first_name,tokens,referred_by) VALUES (?,?,?,?,?)",
                        (uid, uname, fname, NEW_USER_BONUS, referred_by))
        await db.commit()
        
        # Если есть реферер, создаём запись в таблице referrals
        if referred_by:
            await db.execute("""
                INSERT INTO referrals (referrer_id, referred_id, tokens_earned) 
                VALUES (?, ?, 0)
            """, (referred_by, uid))
            await db.commit()
    
    return await get_user(uid)


async def accept_agreement(uid: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET agreement=1 WHERE user_id=?", (uid,))
        await db.commit()


async def update_tokens(uid: int, used: int):
    """Списываем токены из users.tokens"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET tokens=tokens-?, total_used=total_used+?, total_requests=total_requests+1 WHERE user_id=?",
                        (used, used, uid))
        await db.commit()


async def add_tokens(uid: int, amt: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET tokens=tokens+? WHERE user_id=?", (amt, uid))
        await db.commit()


async def subtract_tokens(uid: int, amount: int):
    """Простое вычитание токенов из users.tokens"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET tokens=tokens-?, total_used=total_used+? WHERE user_id=?", (amount, amount, uid))
        await db.commit()


async def get_bot_cfg(bot: str) -> Dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM bot_cfg WHERE bot=?", (bot,))
        r = await c.fetchone()
        return dict(r) if r else {'enabled':1,'model':'gpt-4o-mini','version':'1.0.0'}


async def set_bot_enabled(bot: str, en: bool):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE bot_cfg SET enabled=? WHERE bot=?", (1 if en else 0, bot))
        await db.commit()


async def set_bot_model(bot: str, model: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE bot_cfg SET model=? WHERE bot=?", (model, bot))
        await db.commit()


async def set_bot_version(bot: str, ver: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE bot_cfg SET version=? WHERE bot=?", (ver, bot))
        await db.commit()


async def get_user_bot(uid: int, bot: str) -> Dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM user_bots WHERE user_id=? AND bot=?", (uid, bot))
        r = await c.fetchone()
        if r: return dict(r)
        await db.execute("INSERT INTO user_bots (user_id,bot) VALUES (?,?)", (uid, bot))
        await db.commit()
        return {'user_id':uid,'bot':bot,'character':'душевный','mood':None,'custom_mood':None,'msg_counter':0,'voice_gender':None}


async def set_char(uid: int, char: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE user_bots SET character=? WHERE user_id=? AND bot='luca'", (char, uid))
        await db.commit()


async def get_voice_gender(uid: int, bot: str = 'voice') -> str:
    """Получить выбранный голос пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT voice_gender FROM user_bots WHERE user_id=? AND bot=?", (uid, bot))
        r = await c.fetchone()
        return r[0] if r and r[0] else None


async def set_voice_gender(uid: int, gender: str, bot: str = 'voice'):
    """Установить выбранный голос"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Проверяем существует ли запись
        c = await db.execute("SELECT 1 FROM user_bots WHERE user_id=? AND bot=?", (uid, bot))
        exists = await c.fetchone()
        
        if exists:
            await db.execute("UPDATE user_bots SET voice_gender=? WHERE user_id=? AND bot=?", (gender, uid, bot))
        else:
            await db.execute("INSERT INTO user_bots (user_id, bot, voice_gender) VALUES (?, ?, ?)", (uid, bot, gender))
        await db.commit()


async def set_mood(uid: int, mood: str, custom: str=None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE user_bots SET mood=?, custom_mood=? WHERE user_id=? AND bot='silas'",
                        (mood, custom, uid))
        if mood != 'custom':
            await db.execute("INSERT INTO mood_stats (user_id,mood) VALUES (?,?)", (uid, mood))
        await db.commit()


async def get_mood_stats(uid: int) -> Dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        s = {'good':0,'tired':0,'pain':0}
        for m in s:
            c = await db.execute("SELECT COUNT(*) FROM mood_stats WHERE user_id=? AND mood=? AND at>datetime('now','-30 days')", (uid, m))
            s[m] = (await c.fetchone())[0]
        return s


async def inc_msg_counter(uid: int, bot: str) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT msg_counter FROM user_bots WHERE user_id=? AND bot=?", (uid, bot))
        r = await c.fetchone()
        cnt = (r[0] if r else 0) + 1
        await db.execute("UPDATE user_bots SET msg_counter=? WHERE user_id=? AND bot=?", (cnt, uid, bot))
        await db.commit()
        return cnt


async def reset_msg_counter(uid: int, bot: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE user_bots SET msg_counter=0 WHERE user_id=? AND bot=?", (uid, bot))
        await db.commit()


async def get_memory(uid: int, bot: str) -> List:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT facts FROM bot_memory WHERE user_id=? AND bot=?", (uid, bot))
        r = await c.fetchone()
        if r: return json.loads(r[0] or '[]')
        await db.execute("INSERT INTO bot_memory (user_id,bot) VALUES (?,?)", (uid, bot))
        await db.commit()
        return []


async def save_memory(uid: int, bot: str, facts: List):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE bot_memory SET facts=? WHERE user_id=? AND bot=?",
                        (json.dumps(facts, ensure_ascii=False), uid, bot))
        await db.commit()


async def add_msg(uid: int, bot: str, role: str, content: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT INTO bot_msgs (user_id,bot,role,content) VALUES (?,?,?,?)",
                        (uid, bot, role, content))
        await db.execute("DELETE FROM bot_msgs WHERE id IN (SELECT id FROM bot_msgs WHERE user_id=? AND bot=? ORDER BY created_at DESC LIMIT -1 OFFSET 20)", (uid, bot))
        await db.commit()


async def get_msgs(uid: int, bot: str, lim: int=20) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT role,content FROM bot_msgs WHERE user_id=? AND bot=? ORDER BY created_at DESC LIMIT ?", (uid, bot, lim))
        return [{"role":r['role'],"content":r['content']} for r in reversed(await c.fetchall())]


async def clear_msgs(uid: int, bot: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM bot_msgs WHERE user_id=? AND bot=?", (uid, bot))
        await db.commit()


async def create_course(uid: int, name: str, steps: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("INSERT INTO courses (user_id,name,total) VALUES (?,?,?)", (uid, name, steps))
        await db.commit()
        return c.lastrowid


async def get_courses(uid: int) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM courses WHERE user_id=? ORDER BY created_at DESC", (uid,))
        return [dict(r) for r in await c.fetchall()]


async def get_course(cid: int) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM courses WHERE id=?", (cid,))
        r = await c.fetchone()
        return dict(r) if r else None


async def update_step(cid: int, step: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE courses SET current=? WHERE id=?", (step, cid))
        await db.commit()


async def start_session(uid: int, dur: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("INSERT INTO sessions (user_id,started,duration) VALUES (?,?,?)",
                            (uid, datetime.now().isoformat(), dur))
        await db.commit()
        return c.lastrowid


async def end_session(sid: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE sessions SET ended=? WHERE id=?", (datetime.now().isoformat(), sid))
        await db.commit()


async def get_setting(k: str) -> Optional[str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT value FROM settings WHERE key=?", (k,))
        r = await c.fetchone()
        return r[0] if r else None


async def set_setting(k: str, v: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (k, v))
        await db.commit()


async def get_all_users() -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM users WHERE is_blocked=0")
        return [dict(r) for r in await c.fetchall()]


async def get_stats() -> Dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        r = {}
        c = await db.execute("SELECT COUNT(*) FROM users"); r['users'] = (await c.fetchone())[0]
        c = await db.execute("SELECT COALESCE(SUM(total_requests),0) FROM users"); r['reqs'] = (await c.fetchone())[0]
        c = await db.execute("SELECT COALESCE(SUM(total_used),0) FROM users"); r['tokens'] = (await c.fetchone())[0]
        return r


async def block_user(uid: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET is_blocked=1 WHERE user_id=?", (uid,))
        await db.commit()


async def unblock_user(uid: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET is_blocked=0 WHERE user_id=?", (uid,))
        await db.commit()


async def save_metrics(active: int, rpm: int, avg_time: float, load: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT INTO server_metrics (active_users,rpm,avg_time,load_pct) VALUES (?,?,?,?)",
                        (active, rpm, avg_time, load))
        await db.commit()


async def get_metrics() -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM server_metrics ORDER BY ts DESC LIMIT 1")
        r = await c.fetchone()
        return dict(r) if r else None


async def get_blocked_count() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_blocked_users():
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT user_id, username FROM users WHERE is_blocked = 1")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def init_metrics_table():
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY,
                load_pct INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0,
                rpm INTEGER DEFAULT 0,
                avg_time REAL DEFAULT 0,
                updated_at TEXT
            )
        """)
        await conn.commit()


async def init_texts_tables():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS bot_texts (
            key TEXT PRIMARY KEY,
            value TEXT,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS bot_buttons (
            key TEXT PRIMARY KEY,
            emoji TEXT,
            text TEXT,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS bot_media (
            key TEXT PRIMARY KEY,
            type TEXT,
            file_id TEXT
        );
        """)
        await db.commit()


async def get_text(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT value FROM bot_texts WHERE key=?", (key,))
        r = await c.fetchone()
        return r[0] if r else default


async def set_text(key: str, value: str, desc: str = ""):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO bot_texts (key,value,description) VALUES (?,?,?)",
            (key, value, desc))
        await db.commit()


async def get_all_texts() -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM bot_texts ORDER BY key")
        return [dict(r) for r in await c.fetchall()]


async def get_button(key: str) -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM bot_buttons WHERE key=?", (key,))
        r = await c.fetchone()
        return dict(r) if r else {'emoji': '', 'text': key}


async def set_button(key: str, emoji: str, text: str, desc: str = ""):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO bot_buttons (key,emoji,text,description) VALUES (?,?,?,?)",
            (key, emoji, text, desc))
        await db.commit()


async def get_all_buttons() -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM bot_buttons ORDER BY key")
        return [dict(r) for r in await c.fetchall()]


async def get_media(key: str) -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM bot_media WHERE key=?", (key,))
        r = await c.fetchone()
        return dict(r) if r else None


async def set_media(key: str, media_type: str, file_id: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO bot_media (key,type,file_id) VALUES (?,?,?)",
            (key, media_type, file_id))
        await db.commit()


async def delete_media(key: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM bot_media WHERE key=?", (key,))
        await db.commit()


async def get_msg_count(uid: int, bot: str) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT COUNT(*) FROM bot_msgs WHERE user_id=? AND bot=?", (uid, bot))
        return (await c.fetchone())[0]


async def get_history_window(uid: int, bot: str, limit: int = 20) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT role, content FROM bot_msgs WHERE user_id=? AND bot=? ORDER BY id DESC LIMIT ?", (uid, bot, limit))
        rows = await c.fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


async def add_message(uid: int, bot: str, role: str, content: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT INTO bot_msgs (user_id, bot, role, content) VALUES (?,?,?,?)", (uid, bot, role, content))
        await db.commit()


async def cleanup_old_messages(uid: int, bot: str, keep: int = 20):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM bot_msgs WHERE user_id=? AND bot=? AND id NOT IN (SELECT id FROM bot_msgs WHERE user_id=? AND bot=? ORDER BY id DESC LIMIT ?)", (uid, bot, uid, bot, keep))
        await db.commit()


async def use_tokens(uid: int, amount: int):
    await update_tokens(uid, amount)


async def get_user_courses(uid: int) -> list:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT name, current, total, done FROM courses WHERE user_id=? ORDER BY id DESC", (uid,))
        rows = await c.fetchall()
        return [{"topic": r[0], "step": r[1], "total": r[2], "completed": r[3]} for r in rows]


async def update_course_step(course_id: int, step: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE courses SET current=? WHERE id=?", (step, course_id))
        await db.commit()


async def complete_course(course_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE courses SET done=1 WHERE id=?", (course_id,))
        await db.commit()


async def save_mood(uid: int, mood: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT INTO mood_stats (user_id, mood) VALUES (?,?)", (uid, mood))
        await db.commit()


async def delete_course(course_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM course_memory WHERE course_id=?", (course_id,))
        await db.execute("DELETE FROM courses WHERE id=?", (course_id,))
        await db.commit()


async def init_course_memory_table():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS course_memory (
            course_id INTEGER PRIMARY KEY,
            summary TEXT DEFAULT '',
            problem_zones TEXT DEFAULT '[]',
            completed_topics TEXT DEFAULT '[]',
            last_context TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        await db.commit()


async def get_course_memory(course_id: int) -> Dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM course_memory WHERE course_id=?", (course_id,))
        r = await c.fetchone()
        if r:
            return {
                'course_id': r['course_id'],
                'summary': r['summary'] or '',
                'problem_zones': json.loads(r['problem_zones'] or '[]'),
                'completed_topics': json.loads(r['completed_topics'] or '[]'),
                'last_context': r['last_context'] or ''
            }
        await db.execute("INSERT INTO course_memory (course_id) VALUES (?)", (course_id,))
        await db.commit()
        return {'course_id': course_id, 'summary': '', 'problem_zones': [], 'completed_topics': [], 'last_context': ''}


async def save_course_memory(course_id: int, summary: str = None, problem_zones: List = None, 
                             completed_topics: List = None, last_context: str = None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        mem = await get_course_memory(course_id)
        await db.execute("""
            UPDATE course_memory SET 
                summary = ?,
                problem_zones = ?,
                completed_topics = ?,
                last_context = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE course_id = ?
        """, (
            summary if summary is not None else mem['summary'],
            json.dumps(problem_zones if problem_zones is not None else mem['problem_zones'], ensure_ascii=False),
            json.dumps(completed_topics if completed_topics is not None else mem['completed_topics'], ensure_ascii=False),
            last_context if last_context is not None else mem['last_context'],
            course_id
        ))
        await db.commit()


async def add_problem_zone(course_id: int, step: int, topic: str, question: str):
    mem = await get_course_memory(course_id)
    zones = mem['problem_zones']
    zones.append({'step': step, 'topic': topic, 'question': question[:200]})
    await save_course_memory(course_id, problem_zones=zones[-20:])


async def add_completed_topic(course_id: int, step: int, topic: str, key_points: list, difficulty: str = "medium"):
    mem = await get_course_memory(course_id)
    topics = mem['completed_topics']
    topics.append({'step': step, 'topic': topic, 'key_points': key_points[:5], 'difficulty': difficulty})
    await save_course_memory(course_id, completed_topics=topics)


async def delete_course_memory(course_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM course_memory WHERE course_id=?", (course_id,))
        await db.commit()


async def get_users_with_memory(limit: int = 20, offset: int = 0) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT DISTINCT u.user_id, u.username, u.tokens,
                   (SELECT COUNT(*) FROM bot_memory WHERE user_id=u.user_id AND facts != '[]') as mem_count
            FROM users u
            JOIN bot_memory m ON u.user_id = m.user_id
            WHERE m.facts != '[]'
            ORDER BY u.user_id DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        return [dict(r) for r in await c.fetchall()]


async def count_users_with_memory() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT COUNT(DISTINCT user_id) FROM bot_memory WHERE facts != '[]'")
        r = await c.fetchone()
        return r[0] if r else 0


async def get_user_all_memory(uid: int) -> Dict[str, List]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT bot, facts FROM bot_memory WHERE user_id=?", (uid,))
        rows = await c.fetchall()
        result = {}
        for r in rows:
            facts = json.loads(r['facts'] or '[]')
            if facts:
                result[r['bot']] = facts
        return result


async def delete_memory_fact(uid: int, bot: str, fact_index: int) -> bool:
    facts = await get_memory(uid, bot)
    if 0 <= fact_index < len(facts):
        facts.pop(fact_index)
        await save_memory(uid, bot, facts)
        return True
    return False


async def update_memory_fact(uid: int, bot: str, fact_index: int, new_text: str) -> bool:
    facts = await get_memory(uid, bot)
    if 0 <= fact_index < len(facts):
        facts[fact_index] = new_text
        await save_memory(uid, bot, facts)
        return True
    return False


async def clear_user_memory(uid: int, bot: str = None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if bot:
            await db.execute("UPDATE bot_memory SET facts='[]' WHERE user_id=? AND bot=?", (uid, bot))
        else:
            await db.execute("UPDATE bot_memory SET facts='[]' WHERE user_id=?", (uid,))
        await db.commit()


async def init_subscription_tables():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            type TEXT,
            tokens_limit INTEGER DEFAULT 0,
            tokens_used INTEGER DEFAULT 0,
            started_at TIMESTAMP,
            expires_at TIMESTAMP,
            is_active INTEGER DEFAULT 0
        );
        
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            tokens INTEGER,
            type TEXT,
            status TEXT DEFAULT 'pending',
            robokassa_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        
        INSERT OR IGNORE INTO bot_settings VALUES ('model_mini', 'anthropic/claude-sonnet-4');
        INSERT OR IGNORE INTO bot_settings VALUES ('model_standard', 'anthropic/claude-opus-4');
        """)
        await db.commit()


async def init_health_tables():
    """Инициализация таблиц для раздела Здоровье"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS calories_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date DATE DEFAULT (date('now')),
            time TIME DEFAULT (time('now')),
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
        
        CREATE TABLE IF NOT EXISTS user_nutrition_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
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
        """)
        await db.commit()


async def get_subscription(uid: int) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM subscriptions WHERE user_id=?", (uid,))
        r = await c.fetchone()
        return dict(r) if r else None


async def create_subscription(uid: int, sub_type: str, tokens: int, days: int = 30):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO subscriptions (user_id, type, tokens_limit, tokens_used, started_at, expires_at, is_active)
            VALUES (?, ?, ?, 0, datetime('now'), datetime('now', '+' || ? || ' days'), 1)
            ON CONFLICT(user_id) DO UPDATE SET
                type = excluded.type,
                tokens_limit = excluded.tokens_limit,
                tokens_used = 0,
                started_at = datetime('now'),
                expires_at = datetime('now', '+' || ? || ' days'),
                is_active = 1
        """, (uid, sub_type, tokens, days, days))
        await db.commit()


async def add_subscription_tokens(uid: int, tokens: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE subscriptions SET tokens_limit = tokens_limit + ? WHERE user_id = ?", (tokens, uid))
        await db.commit()


async def use_subscription_tokens(uid: int, amount: int) -> bool:
    """Списать токены из подписки (разрешаем уход в минус)"""
    sub = await get_subscription(uid)
    if not sub or not sub['is_active']:
        return False
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE subscriptions SET tokens_used = tokens_used + ? WHERE user_id = ?", (amount, uid))
        await db.execute("UPDATE users SET total_used = total_used + ?, total_requests = total_requests + 1 WHERE user_id = ?", (amount, uid))
        await db.commit()
    return True


async def check_subscription_active(uid: int) -> bool:
    """Проверка активности подписки"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT is_active, expires_at FROM subscriptions WHERE user_id = ?", (uid,))
        r = await c.fetchone()
        if not r or not r[0]:
            return False
        if r[1] is None:
            return True
        try:
            return datetime.fromisoformat(r[1]) > datetime.now()
        except:
            return True


async def deactivate_expired_subscriptions():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE subscriptions SET is_active = 0 WHERE expires_at < datetime('now') AND is_active = 1")
        await db.commit()


async def create_transaction(uid: int, amount: float, tokens: int, tx_type: str) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("INSERT INTO transactions (user_id, amount, tokens, type, status) VALUES (?, ?, ?, ?, 'pending')", (uid, amount, tokens, tx_type))
        await db.commit()
        return c.lastrowid


async def complete_transaction(tx_id: int, robokassa_id: int = None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE transactions SET status = 'completed', robokassa_id = ?, completed_at = datetime('now') WHERE id = ?", (robokassa_id, tx_id))
        await db.commit()


async def get_transaction(tx_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM transactions WHERE id=?", (tx_id,))
        r = await c.fetchone()
        return dict(r) if r else None


async def get_user_transactions(uid: int, limit: int = 20) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (uid, limit))
        return [dict(r) for r in await c.fetchall()]


async def get_bot_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT value FROM bot_settings WHERE key=?", (key,))
        r = await c.fetchone()
        return r[0] if r else default


async def set_bot_setting(key: str, value: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()


async def get_model_for_subscription(sub_type: str) -> str:
    if sub_type == "standard":
        return await get_bot_setting("model_standard", config_MODEL)
    elif sub_type == "mini":
        return await get_bot_setting("model_mini", config_MODEL)
    return config_MODEL


# ================== ГЛАВНЫЕ ФУНКЦИИ ТОКЕНОВ ==================


async def get_available_tokens(uid: int) -> int:
    """
    Получить доступные токены:
    - Если есть активная подписка -> токены из подписки
    - Если нет подписки -> бонусные токены из users.tokens
    """
    sub = await get_subscription(uid)
    
    # Есть активная подписка
    if sub and sub['is_active'] and await check_subscription_active(uid):
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
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                "INSERT INTO token_usage (user_id, bot_name, tokens_used) VALUES (?, ?, ?)",
                (uid, bot_name, amount)
            )
            await db.commit()
    
    # Есть активная подписка
    if sub and sub['is_active'] and await check_subscription_active(uid):
        return await use_subscription_tokens(uid, amount)
    
    # Нет подписки - списываем бонусные (разрешаем уход в минус)
    user = await get_user(uid)
    if not user:
        return False
    await update_tokens(uid, amount)
    return True


async def has_active_subscription(uid: int) -> bool:
    """Есть ли у пользователя активная ПЛАТНАЯ подписка"""
    sub = await get_subscription(uid)
    if not sub or not sub['is_active']:
        return False
    return await check_subscription_active(uid)


async def is_gift_subscription(uid: int) -> bool:
    """
    Проверяет, является ли подписка подарочной/админской
    Подарочная подписка = длительность > 365 дней
    """
    sub = await get_subscription(uid)
    if not sub or not sub['is_active']:
        return False
    
    # Проверяем длительность подписки
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT julianday(expires_at) - julianday(started_at) as duration FROM subscriptions WHERE user_id = ?",
            (uid,)
        )
        row = await cursor.fetchone()
        if row and row[0]:
            # Если подписка на 365+ дней - это подарочная/админская
            return row[0] >= 365
    
    return False


# ================== ФУНКЦИИ ДЛЯ АДМИНКИ ==================


async def get_user_facts(uid: int) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT rowid as id, user_id, bot, facts FROM bot_memory WHERE user_id=?", (uid,))
        rows = await c.fetchall()
        result = []
        for r in rows:
            facts = json.loads(r['facts'] or '[]')
            for i, f in enumerate(facts):
                result.append({'id': f"{r['bot']}:{i}", 'bot': r['bot'], 'fact': f, 'index': i})
        return result


async def add_fact(uid: int, fact: str, bot: str = 'luca'):
    facts = await get_memory(uid, bot)
    facts.append(fact)
    await save_memory(uid, bot, facts)


async def update_fact(fact_id: str, new_text: str):
    parts = fact_id.split(':')
    if len(parts) != 2:
        return False
    bot, idx = parts[0], int(parts[1])
    return True


async def give_subscription(uid: int, days: int, sub_type: str = "mini"):
    from config import SUBSCRIPTIONS
    tokens = SUBSCRIPTIONS.get(sub_type, {}).get('tokens', 400000)
    await create_subscription(uid, sub_type, tokens, days)


async def get_subscribers() -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT user_id, type, expires_at as sub_until, tokens_limit, tokens_used 
            FROM subscriptions 
            WHERE is_active = 1 
            ORDER BY expires_at DESC
        """)
        return [dict(r) for r in await c.fetchall()]


async def get_today_users() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')")
        r = await c.fetchone()
        return r[0] if r else 0


async def get_today_requests() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT COUNT(*) FROM bot_msgs WHERE date(created_at) = date('now') AND role='user'")
        r = await c.fetchone()
        return r[0] if r else 0


async def get_active_users_24h() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("""
            SELECT COUNT(DISTINCT user_id) FROM bot_msgs 
            WHERE created_at > datetime('now', '-24 hours')
        """)
        r = await c.fetchone()
        return r[0] if r else 0


async def increment_requests(uid: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET total_requests = total_requests + 1 WHERE user_id = ?", (uid,))
        await db.commit()


async def count_users() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT COUNT(*) FROM users")
        r = await c.fetchone()
        return r[0] if r else 0


async def count_subscribers_by_type(sub_type: str) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE type = ? AND is_active = 1 AND expires_at > datetime('now')",
            (sub_type,))
        r = await c.fetchone()
        return r[0] if r else 0


async def get_total_tokens_used() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT COALESCE(SUM(tokens_used), 0) FROM subscriptions")
        r = await c.fetchone()
        return r[0] if r else 0


async def get_all_subscribers() -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT s.user_id, s.type, s.tokens_limit, s.tokens_used, s.expires_at,
                   u.username
            FROM subscriptions s
            LEFT JOIN users u ON s.user_id = u.user_id
            WHERE s.is_active = 1 AND s.expires_at > datetime('now')
            ORDER BY s.expires_at DESC
        """)
        return [dict(r) for r in await c.fetchall()]


async def get_subscribers_by_type(sub_type: str) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT s.user_id, s.type, s.tokens_limit, s.tokens_used, s.expires_at,
                   u.username
            FROM subscriptions s
            LEFT JOIN users u ON s.user_id = u.user_id
            WHERE s.type = ? AND s.is_active = 1 AND s.expires_at > datetime('now')
            ORDER BY s.expires_at DESC
        """, (sub_type,))
        return [dict(r) for r in await c.fetchall()]


async def get_users_without_subscription() -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT u.user_id, u.username
            FROM users u
            LEFT JOIN subscriptions s ON u.user_id = s.user_id AND s.is_active = 1 AND s.expires_at > datetime('now')
            WHERE s.user_id IS NULL AND u.is_blocked = 0
        """)
        return [dict(r) for r in await c.fetchall()]


async def get_tokens_by_model(sub_type: str) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute(
            "SELECT COALESCE(SUM(tokens_used), 0) FROM subscriptions WHERE type = ?",
            (sub_type,))
        r = await c.fetchone()
        return r[0] if r else 0


async def get_user_model(uid: int) -> str:
    """Получить модель для пользователя (по подписке или дефолтную)"""
    sub = await get_subscription(uid)
    if sub and sub['type']:
        return await get_model_for_subscription(sub['type'])
    return "anthropic/claude-sonnet-4"  # дефолтная модель для бонусных токенов


async def get_profile(uid: int) -> Dict:
    """Получить профиль пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM user_profile WHERE user_id=?", (uid,))
        r = await c.fetchone()
        return dict(r) if r else None

async def save_profile(uid: int, name: str = None, age: int = None, gender: str = None):
    """Сохранить профиль"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO user_profile (user_id, name, age, gender) VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
            name = COALESCE(excluded.name, name),
            age = COALESCE(excluded.age, age),
            gender = COALESCE(excluded.gender, gender)
        """, (uid, name, age, gender))
        await db.commit()

async def get_today_tokens(uid: int) -> int:
    """Токены потраченные сегодня"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("""
            SELECT COALESCE(SUM(tokens_used), 0) FROM token_usage 
            WHERE user_id=? AND date(created_at)=date('now')
        """, (uid,))
        r = await c.fetchone()
        return r[0] if r else 0

async def get_month_tokens(uid: int) -> int:
    """Токены потраченные за месяц"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("""
            SELECT COALESCE(SUM(tokens_used), 0) FROM token_usage 
            WHERE user_id=? AND strftime('%Y-%m', created_at)=strftime('%Y-%m', 'now')
        """, (uid,))
        r = await c.fetchone()
        return r[0] if r else 0


async def get_tokens_by_bot(uid: int, bot_name: str) -> int:
    """Получить токены использованные конкретным ботом"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("""
            SELECT COALESCE(SUM(tokens_used), 0) FROM token_usage 
            WHERE user_id=? AND bot_name=?
        """, (uid, bot_name))
        r = await c.fetchone()
        return r[0] if r else 0


async def get_all_bots_tokens(uid: int) -> Dict[str, int]:
    """Получить статистику использования токенов по всем ботам"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT bot_name, SUM(tokens_used) as total
            FROM token_usage 
            WHERE user_id=?
            GROUP BY bot_name
        """, (uid,))
        rows = await c.fetchall()
        return {row['bot_name']: row['total'] for row in rows}


# ================== ФУНКЦИИ ДЛЯ ДИАЛОГОВ ==================


async def create_conversation(uid: int, bot: str) -> int:
    """Создать новый диалог"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute(
            "INSERT INTO conversations (user_id, bot) VALUES (?, ?)",
            (uid, bot)
        )
        await db.commit()
        return c.lastrowid


async def save_conversation_message(conv_id: int, role: str, content: str, model: str = None):
    """Сохранить сообщение в диалоге"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO messages (conversation_id, role, content, model) VALUES (?, ?, ?, ?)",
            (conv_id, role, content, model)
        )
        await db.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conv_id,)
        )
        await db.commit()


async def get_conversation(conv_id: int) -> Optional[Dict]:
    """Получить информацию о диалоге"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM conversations WHERE id=?", (conv_id,))
        r = await c.fetchone()
        return dict(r) if r else None


async def get_conversation_messages(conv_id: int) -> List[Dict]:
    """Получить все сообщения диалога"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT role, content, model, timestamp 
            FROM messages 
            WHERE conversation_id=? 
            ORDER BY timestamp ASC
        """, (conv_id,))
        return [dict(r) for r in await c.fetchall()]


async def get_user_conversations(uid: int, bot: str = None, limit: int = 50) -> List[Dict]:
    """Получить диалоги пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if bot:
            c = await db.execute("""
                SELECT * FROM conversations 
                WHERE user_id=? AND bot=? 
                ORDER BY updated_at DESC 
                LIMIT ?
            """, (uid, bot, limit))
        else:
            c = await db.execute("""
                SELECT * FROM conversations 
                WHERE user_id=? 
                ORDER BY updated_at DESC 
                LIMIT ?
            """, (uid, limit))
        return [dict(r) for r in await c.fetchall()]


# ================== РЕФЕРАЛЬНАЯ СИСТЕМА ==================


async def get_referrer_id(uid: int) -> Optional[int]:
    """Получить ID реферера пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("SELECT referred_by FROM users WHERE user_id=?", (uid,))
        r = await c.fetchone()
        return r[0] if r and r[0] else None


async def add_referral_reward(referrer_id: int, referred_id: int, tokens: int, sub_type: str):
    """Начислить награду рефереру"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Начисляем токены рефереру
        await db.execute("UPDATE users SET tokens = tokens + ? WHERE user_id = ?", (tokens, referrer_id))
        
        # Обновляем запись в referrals
        await db.execute("""
            UPDATE referrals 
            SET tokens_earned = tokens_earned + ?, subscription_type = ?
            WHERE referrer_id = ? AND referred_id = ?
        """, (tokens, sub_type, referrer_id, referred_id))
        
        await db.commit()


async def get_referral_stats(uid: int) -> Dict:
    """Получить статистику рефералов"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Всего рефералов
        c = await db.execute("SELECT COUNT(*) as total FROM referrals WHERE referrer_id=?", (uid,))
        total = (await c.fetchone())['total']
        
        # Всего заработано токенов
        c = await db.execute("SELECT COALESCE(SUM(tokens_earned), 0) as earned FROM referrals WHERE referrer_id=?", (uid,))
        earned = (await c.fetchone())['earned']
        
        # Рефералы с подпиской
        c = await db.execute("""
            SELECT COUNT(*) as with_sub FROM referrals 
            WHERE referrer_id=? AND subscription_type IS NOT NULL
        """, (uid,))
        with_sub = (await c.fetchone())['with_sub']
        
        return {
            'total_referrals': total,
            'tokens_earned': earned,
            'referrals_with_subscription': with_sub
        }


async def get_user_referrals(uid: int, limit: int = 50) -> List[Dict]:
    """Получить список рефералов пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT r.referred_id, r.tokens_earned, r.subscription_type, r.created_at,
                   u.username, u.first_name
            FROM referrals r
            LEFT JOIN users u ON r.referred_id = u.user_id
            WHERE r.referrer_id=?
            ORDER BY r.created_at DESC
            LIMIT ?
        """, (uid, limit))
        return [dict(row) for row in await c.fetchall()]


# ============================================
# === ЗДОРОВЬЕ И КАЛОРИИ ===
# ============================================

async def save_calories_log(user_id: int, food_name: str, portion: str, 
                            calories: int, protein: float, fat: float, carbs: float):
    """Сохранить запись о еде в журнал"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO calories_log (user_id, food_name, portion, calories, protein, fat, carbs)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, food_name, portion, calories, protein, fat, carbs))
        await db.commit()


async def get_today_calories(user_id: int) -> Dict:
    """Получить статистику калорий за сегодня"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT 
                COALESCE(SUM(calories), 0) as calories,
                COALESCE(SUM(protein), 0) as protein,
                COALESCE(SUM(fat), 0) as fat,
                COALESCE(SUM(carbs), 0) as carbs
            FROM calories_log
            WHERE user_id=? AND date=date('now')
        """, (user_id,))
        row = await c.fetchone()
        return dict(row) if row else {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}


async def get_calories_logs(user_id: int, days: int = 0) -> List[Dict]:
    """Получить логи за указанный день (0=сегодня, 1=вчера)"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT * FROM calories_log
            WHERE user_id=? AND date=date('now', ?)
            ORDER BY time DESC
        """, (user_id, f'-{days} days' if days > 0 else ''))
        return [dict(row) for row in await c.fetchall()]


async def get_weekly_calories(user_id: int) -> List[Dict]:
    """Получить статистику за неделю"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT 
                date,
                SUM(calories) as calories,
                SUM(protein) as protein,
                SUM(fat) as fat,
                SUM(carbs) as carbs
            FROM calories_log
            WHERE user_id=? AND date >= date('now', '-7 days')
            GROUP BY date
            ORDER BY date DESC
        """, (user_id,))
        return [dict(row) for row in await c.fetchall()]


async def get_monthly_calories(user_id: int) -> List[Dict]:
    """Получить статистику за месяц"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT 
                date,
                SUM(calories) as calories,
                SUM(protein) as protein,
                SUM(fat) as fat,
                SUM(carbs) as carbs
            FROM calories_log
            WHERE user_id=? AND date >= date('now', '-30 days')
            GROUP BY date
            ORDER BY date DESC
        """, (user_id,))
        return [dict(row) for row in await c.fetchall()]


async def save_nutrition_goal(user_id: int, goal: str, daily_calories: int,
                              daily_protein: int, daily_fat: int, daily_carbs: int,
                              weight: float, height: int, age: int, gender: str, activity: str):
    """Сохранить цель питания пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO user_nutrition_goals 
            (user_id, goal, daily_calories, daily_protein, daily_fat, daily_carbs, 
             weight, height, age, gender, activity, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, goal, daily_calories, daily_protein, daily_fat, daily_carbs,
              weight, height, age, gender, activity))
        await db.commit()


async def get_nutrition_goal(user_id: int) -> Optional[Dict]:
    """Получить цель питания пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT * FROM user_nutrition_goals WHERE user_id=?
        """, (user_id,))
        row = await c.fetchone()
        return dict(row) if row else None


# ============================================
# === ТРЕКЕР ЦЕЛЕЙ ===
# ============================================

async def init_goals_tables():
    """Инициализация таблиц для трекера целей"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS user_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
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
        
        CREATE TABLE IF NOT EXISTS goal_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            is_done INTEGER DEFAULT 1,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (goal_id) REFERENCES user_goals(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_goal_checkins_goal ON goal_checkins(goal_id, date);
        CREATE INDEX IF NOT EXISTS idx_goal_checkins_user ON goal_checkins(user_id, date);
        
        CREATE TABLE IF NOT EXISTS user_streaks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
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
        """)
        await db.commit()


async def get_active_goals(user_id: int) -> List[Dict]:
    """Получает активные цели пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT * FROM user_goals
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC
        """, (user_id,))
        return [dict(row) for row in await c.fetchall()]


async def get_goal_by_id(goal_id: int) -> Optional[Dict]:
    """Получает цель по ID"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM user_goals WHERE id = ?", (goal_id,))
        row = await c.fetchone()
        return dict(row) if row else None


async def create_goal(user_id: int, title: str, frequency: str, target_count: int, 
                      period_days: int, reminder_time: Optional[str] = None) -> int:
    """Создаёт новую цель"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("""
            INSERT INTO user_goals (user_id, title, frequency, target_count, period_days, reminder_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, title, frequency, target_count, period_days, reminder_time))
        await db.commit()
        return c.lastrowid


async def create_streak(user_id: int, goal_id: int):
    """Создаёт запись streak для цели"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO user_streaks (user_id, goal_id, current_streak, best_streak)
            VALUES (?, ?, 0, 0)
        """, (user_id, goal_id))
        await db.commit()


async def get_goal_streak(goal_id: int, user_id: int) -> Dict:
    """Получает streak для цели"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT * FROM user_streaks
            WHERE goal_id = ? AND user_id = ?
        """, (goal_id, user_id))
        row = await c.fetchone()
        if row:
            return dict(row)
        # Если нет - создаём
        await create_streak(user_id, goal_id)
        return {'current_streak': 0, 'best_streak': 0, 'last_checkin': None}


async def get_checkin_today(goal_id: int, user_id: int) -> Optional[Dict]:
    """Проверяет есть ли отметка за сегодня"""
    from datetime import date
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT * FROM goal_checkins
            WHERE goal_id = ? AND user_id = ? AND date = ?
        """, (goal_id, user_id, date.today().isoformat()))
        row = await c.fetchone()
        return dict(row) if row else None


async def save_checkin(goal_id: int, user_id: int, is_done: bool = True, note: Optional[str] = None):
    """Сохраняет отметку выполнения"""
    from datetime import date
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO goal_checkins (goal_id, user_id, date, is_done, note)
            VALUES (?, ?, ?, ?, ?)
        """, (goal_id, user_id, date.today().isoformat(), 1 if is_done else 0, note))
        await db.commit()


async def update_streak(goal_id: int, user_id: int, current_streak: int, best_streak: int):
    """Обновляет streak"""
    from datetime import date
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE user_streaks
            SET current_streak = ?, best_streak = ?, last_checkin = ?
            WHERE goal_id = ? AND user_id = ?
        """, (current_streak, best_streak, date.today().isoformat(), goal_id, user_id))
        await db.commit()


async def get_goal_progress(goal_id: int, target: int, period: int) -> Dict:
    """Получает прогресс цели за текущий период"""
    from datetime import date, timedelta
    start_date = (date.today() - timedelta(days=period)).isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT COUNT(*) as done FROM goal_checkins
            WHERE goal_id = ? AND date >= ? AND is_done = 1
        """, (goal_id, start_date))
        row = await c.fetchone()
        done = row['done'] if row else 0
        
        return {
            'done': done,
            'target': target,
            'percent': int(done / target * 100) if target > 0 else 0
        }


async def get_total_streak(user_id: int) -> int:
    """Получает общий streak пользователя (сумма всех активных streak)"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT COALESCE(SUM(current_streak), 0) as total
            FROM user_streaks
            WHERE user_id = ?
        """, (user_id,))
        row = await c.fetchone()
        return row['total'] if row else 0


async def delete_goal(goal_id: int):
    """Деактивирует цель (не удаляет из БД)"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE user_goals SET is_active = 0 WHERE id = ?", (goal_id,))
        await db.commit()


async def get_monthly_stats(user_id: int) -> Dict:
    """Получает статистику за 30 дней"""
    from datetime import date, timedelta
    
    start_date = (date.today() - timedelta(days=30)).isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Всего выполнено
        c = await db.execute("""
            SELECT COUNT(*) as done FROM goal_checkins
            WHERE user_id = ? AND date >= ? AND is_done = 1
        """, (user_id, start_date))
        done = (await c.fetchone())['done']
        
        # Всего пропущено
        c = await db.execute("""
            SELECT COUNT(*) as skipped FROM goal_checkins
            WHERE user_id = ? AND date >= ? AND is_done = 0
        """, (user_id, start_date))
        skipped = (await c.fetchone())['skipped']
        
        total = done + skipped
        percent = int(done / total * 100) if total > 0 else 0
        
        # Статистика по неделям
        weeks = []
        for i in range(4):
            week_start = (date.today() - timedelta(days=(i+1)*7)).isoformat()
            week_end = (date.today() - timedelta(days=i*7)).isoformat()
            
            c = await db.execute("""
                SELECT 
                    COUNT(CASE WHEN is_done = 1 THEN 1 END) as week_done,
                    COUNT(*) as week_total
                FROM goal_checkins
                WHERE user_id = ? AND date >= ? AND date < ?
            """, (user_id, week_start, week_end))
            row = await c.fetchone()
            
            week_total = row['week_total'] if row else 0
            week_done = row['week_done'] if row else 0
            week_percent = int(week_done / week_total * 100) if week_total > 0 else 0
            
            weeks.append({
                'label': f'Неделя {4-i}',
                'percent': week_percent,
                'done': week_done,
                'total': week_total
            })
        
        weeks.reverse()
        
        return {
            'done': done,
            'skipped': skipped,
            'total': total,
            'percent': percent,
            'weeks': weeks
        }


# ============================================
# === РЕЖИМ ДНЯ (РУТИНЫ) ===
# ============================================

async def init_routine_tables():
    """Инициализация таблиц для режима дня"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS user_routines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            routine_type TEXT NOT NULL,
            items TEXT NOT NULL,
            reminder_time TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            UNIQUE(user_id, routine_type)
        );
        CREATE INDEX IF NOT EXISTS idx_user_routines_user ON user_routines(user_id, routine_type);
        
        CREATE TABLE IF NOT EXISTS routine_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
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
        """)
        await db.commit()


async def get_user_routine(user_id: int, routine_type: str) -> Optional[Dict]:
    """Получить рутину пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT * FROM user_routines
            WHERE user_id = ? AND routine_type = ?
        """, (user_id, routine_type))
        row = await c.fetchone()
        if row:
            result = dict(row)
            # Декодируем JSON
            import json
            result['items'] = json.loads(result['items'])
            return result
        return None


async def save_user_routine(user_id: int, routine_type: str, items: List[str], reminder_time: Optional[str] = None):
    """Сохранить рутину пользователя"""
    import json
    items_json = json.dumps(items, ensure_ascii=False)
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO user_routines (user_id, routine_type, items, reminder_time)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, routine_type) 
            DO UPDATE SET items=excluded.items, reminder_time=excluded.reminder_time
        """, (user_id, routine_type, items_json, reminder_time))
        await db.commit()


async def get_today_routine_checkin(user_id: int, routine_type: str) -> Optional[Dict]:
    """Получить отметку рутины за сегодня"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT * FROM routine_checkins
            WHERE user_id = ? AND routine_type = ? AND date = ?
        """, (user_id, routine_type, date.today().isoformat()))
        row = await c.fetchone()
        if row:
            result = dict(row)
            # Декодируем JSON
            import json
            result['completed_items'] = json.loads(result['completed_items'])
            return result
        return None


async def save_routine_checkin(user_id: int, routine_type: str, completed_items: List[str], 
                               total_items: int, completion_percent: int, 
                               reflection: Optional[str] = None, mood: Optional[int] = None):
    """Сохранить отметку рутины"""
    import json
    completed_json = json.dumps(completed_items, ensure_ascii=False)
    today = date.today().isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Проверяем есть ли уже запись
        c = await db.execute("""
            SELECT id FROM routine_checkins
            WHERE user_id = ? AND routine_type = ? AND date = ?
        """, (user_id, routine_type, today))
        existing = await c.fetchone()
        
        if existing:
            # Обновляем
            await db.execute("""
                UPDATE routine_checkins
                SET completed_items = ?, total_items = ?, completion_percent = ?, 
                    reflection = ?, mood = ?
                WHERE user_id = ? AND routine_type = ? AND date = ?
            """, (completed_json, total_items, completion_percent, reflection, mood, 
                  user_id, routine_type, today))
        else:
            # Создаём новую
            await db.execute("""
                INSERT INTO routine_checkins 
                (user_id, routine_type, date, completed_items, total_items, 
                 completion_percent, reflection, mood)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, routine_type, today, completed_json, total_items, 
                  completion_percent, reflection, mood))
        
        await db.commit()


async def get_routine_stats(user_id: int, days: int = 7) -> Dict:
    """Получить статистику рутин за N дней"""
    from datetime import date, timedelta
    start_date = (date.today() - timedelta(days=days)).isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT * FROM routine_checkins
            WHERE user_id = ? AND date >= ?
            ORDER BY date
        """, (user_id, start_date))
        checkins = [dict(row) for row in await c.fetchall()]
    
    # Группируем по типу и дате
    morning_stats = []
    evening_stats = []
    
    for i in range(days):
        day = date.today() - timedelta(days=days-1-i)
        day_str = day.strftime("%d.%m")
        day_iso = day.isoformat()
        
        morning = next((c for c in checkins if c['date'] == day_iso and c['routine_type'] == "morning"), None)
        evening = next((c for c in checkins if c['date'] == day_iso and c['routine_type'] == "evening"), None)
        
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


# ============================================
# === МЕНТАЛЬНОЕ ЗДОРОВЬЕ ===
# ============================================

async def init_mental_tables():
    """Инициализация таблиц для ментального здоровья"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS mood_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            mood INTEGER NOT NULL,
            energy INTEGER NOT NULL,
            note TEXT,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_mood_logs_user ON mood_logs(user_id, date);
        
        CREATE TABLE IF NOT EXISTS meditation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            duration INTEGER NOT NULL,
            type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_meditation_logs_user ON meditation_logs(user_id, date);
        """)
        await db.commit()


async def get_today_mood(user_id: int) -> Optional[Dict]:
    """Получить настроение за сегодня"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT * FROM mood_logs
            WHERE user_id = ? AND date = ?
        """, (user_id, date.today().isoformat()))
        row = await c.fetchone()
        if row:
            result = dict(row)
            # Декодируем JSON теги
            import json
            if result.get('tags'):
                result['tags'] = json.loads(result['tags'])
            return result
        return None


async def save_mood_log(user_id: int, mood: int, energy: int, tags: List[str], note: str = None):
    """Сохранить запись настроения"""
    import json
    tags_json = json.dumps(tags, ensure_ascii=False) if tags else "[]"
    today = date.today().isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Проверяем есть ли уже запись
        c = await db.execute("""
            SELECT id FROM mood_logs
            WHERE user_id = ? AND date = ?
        """, (user_id, today))
        existing = await c.fetchone()
        
        if existing:
            # Обновляем
            await db.execute("""
                UPDATE mood_logs
                SET mood = ?, energy = ?, tags = ?, note = ?
                WHERE user_id = ? AND date = ?
            """, (mood, energy, tags_json, note, user_id, today))
        else:
            # Создаём новую
            await db.execute("""
                INSERT INTO mood_logs (user_id, date, mood, energy, tags, note)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, today, mood, energy, tags_json, note))
        
        await db.commit()


async def save_meditation_log(user_id: int, duration: int, med_type: str):
    """Сохранить запись медитации"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO meditation_logs (user_id, date, duration, type)
            VALUES (?, ?, ?, ?)
        """, (user_id, date.today().isoformat(), duration, med_type))
        await db.commit()


async def get_meditation_streak(user_id: int) -> int:
    """Получить streak медитаций"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT DISTINCT date FROM meditation_logs
            WHERE user_id = ?
            ORDER BY date DESC
        """, (user_id,))
        dates = [row['date'] for row in await c.fetchall()]
    
    if not dates:
        return 0
    
    streak = 0
    expected = date.today().isoformat()
    
    for d in dates:
        if d == expected:
            streak += 1
            expected = (date.fromisoformat(d) - timedelta(days=1)).isoformat()
        elif d < expected:
            break
    
    return streak


async def get_mood_stats(user_id: int, days: int = 14) -> Dict:
    """Получить статистику настроения за N дней"""
    start_date = (date.today() - timedelta(days=days)).isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT * FROM mood_logs
            WHERE user_id = ? AND date >= ?
            ORDER BY date
        """, (user_id, start_date))
        logs = [dict(row) for row in await c.fetchall()]
    
    if not logs:
        return {"logs": [], "avg_mood": 0, "avg_energy": 0, "top_tag": None}
    
    # Собираем статистику
    mood_sum = sum(l['mood'] for l in logs)
    energy_sum = sum(l['energy'] for l in logs)
    
    # Считаем теги
    import json
    from collections import Counter
    all_tags = []
    for l in logs:
        if l.get('tags'):
            tags = json.loads(l['tags'])
            all_tags.extend(tags)
    
    tag_counts = Counter(all_tags)
    top_tag = tag_counts.most_common(1)[0][0] if tag_counts else None
    
    return {
        "logs": [{"date": date.fromisoformat(l['date']).strftime("%d.%m"), "mood": l['mood']} for l in logs],
        "avg_mood": mood_sum / len(logs),
        "avg_energy": energy_sum / len(logs),
        "top_tag": top_tag
    }


# ============================================
# === ФИНАНСЫ ===
# ============================================

# Категории расходов
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


async def init_finance_tables():
    """Инициализация таблиц для финансов"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Создаем таблицу транзакций
        await db.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'RUB',
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Создаем индекс
        await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)
        """)
        
        # Создаем таблицу бюджетов
        await db.execute("""
        CREATE TABLE IF NOT EXISTS user_budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            monthly_limit REAL NOT NULL,
            category_limits TEXT,
            currency TEXT DEFAULT 'RUB',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        await db.commit()


async def save_transaction(user_id: int, trans_type: str, amount: float, category: str, description: str):
    """Сохранить транзакцию"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO transactions (user_id, type, amount, category, description, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, trans_type, amount, category, description, date.today().isoformat()))
        await db.commit()


async def get_month_expenses(user_id: int) -> Dict:
    """Получить расходы за текущий месяц"""
    start_date = date.today().replace(day=1).isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM transactions
            WHERE user_id = ? AND type = 'expense' AND date >= ?
        """, (user_id, start_date))
        row = await c.fetchone()
        return {"total": row['total'] if row else 0}


async def get_month_total(user_id: int) -> float:
    """Получить общую сумму расходов за месяц"""
    stats = await get_month_expenses(user_id)
    return stats["total"]


async def get_expenses_by_period(user_id: int, start_date: date) -> List[Dict]:
    """Получить расходы за период"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT * FROM transactions
            WHERE user_id = ? AND type = 'expense' AND date >= ?
            ORDER BY date DESC
        """, (user_id, start_date.isoformat()))
        return [dict(row) for row in await c.fetchall()]


async def get_user_budget(user_id: int) -> Optional[Dict]:
    """Получить бюджет пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT * FROM user_budgets WHERE user_id = ?
        """, (user_id,))
        row = await c.fetchone()
        return dict(row) if row else None


async def save_user_budget(user_id: int, monthly_limit: float):
    """Сохранить бюджет пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Проверяем существует ли бюджет
        c = await db.execute("SELECT id FROM user_budgets WHERE user_id = ?", (user_id,))
        existing = await c.fetchone()
        
        if existing:
            await db.execute("""
                UPDATE user_budgets
                SET monthly_limit = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (monthly_limit, user_id))
        else:
            await db.execute("""
                INSERT INTO user_budgets (user_id, monthly_limit)
                VALUES (?, ?)
            """, (user_id, monthly_limit))
        
        await db.commit()


async def get_top_categories(user_id: int, limit: int = 5) -> List[tuple]:
    """Получить топ категорий по расходам"""
    start_date = date.today().replace(day=1).isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT category, SUM(amount) as total
            FROM transactions
            WHERE user_id = ? AND type = 'expense' AND date >= ?
            GROUP BY category
            ORDER BY total DESC
            LIMIT ?
        """, (user_id, start_date, limit))
        return [(row['category'], row['total']) for row in await c.fetchall()]


async def get_average_expense(user_id: int) -> float:
    """Получить средний чек"""
    start_date = date.today().replace(day=1).isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("""
            SELECT AVG(amount) as avg_amount
            FROM transactions
            WHERE user_id = ? AND type = 'expense' AND date >= ?
        """, (user_id, start_date))
        row = await c.fetchone()
        return row[0] if row and row[0] else 0


async def get_max_expense(user_id: int) -> Optional[Dict]:
    """Получить максимальную трату"""
    start_date = date.today().replace(day=1).isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT * FROM transactions
            WHERE user_id = ? AND type = 'expense' AND date >= ?
            ORDER BY amount DESC
            LIMIT 1
        """, (user_id, start_date))
        row = await c.fetchone()
        return dict(row) if row else None


async def get_last_month_total(user_id: int) -> float:
    """Получить расходы за прошлый месяц"""
    today = date.today()
    # Первый день прошлого месяца
    last_month_end = today.replace(day=1) - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        c = await db.execute("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM transactions
            WHERE user_id = ? AND type = 'expense' 
            AND date >= ? AND date <= ?
        """, (user_id, last_month_start.isoformat(), last_month_end.isoformat()))
        row = await c.fetchone()
        return row[0] if row else 0


async def get_month_expenses_detailed(user_id: int) -> Dict:
    """Получить детальную статистику расходов за месяц"""
    start_date = date.today().replace(day=1).isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT category, SUM(amount) as total, COUNT(*) as count
            FROM transactions
            WHERE user_id = ? AND type = 'expense' AND date >= ?
            GROUP BY category
            ORDER BY total DESC
        """, (user_id, start_date))
        
        result = {}
        for row in await c.fetchall():
            cat_name = EXPENSE_CATEGORIES.get(row['category'], row['category'])
            result[cat_name] = {
                'total': row['total'],
                'count': row['count']
            }
        
        return result
