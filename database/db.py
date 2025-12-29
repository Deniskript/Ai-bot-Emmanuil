import aiosqlite
import json
from datetime import date
from typing import Optional, Dict, List, Any
import os
from config import DATABASE_PATH, NEW_USER_BONUS

os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, tokens INTEGER DEFAULT 5000, total_tokens_received INTEGER DEFAULT 5000, total_tokens_used INTEGER DEFAULT 0, total_requests INTEGER DEFAULT 0, daily_requests INTEGER DEFAULT 0, last_request_date DATE, monthly_requests INTEGER DEFAULT 0, month_start DATE, is_blocked INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        await db.execute("CREATE TABLE IF NOT EXISTS user_memory (user_id INTEGER PRIMARY KEY, memory_enabled INTEGER DEFAULT 1, personal_prompt TEXT DEFAULT '', interests TEXT DEFAULT '[]', problems TEXT DEFAULT '[]', lessons_completed TEXT DEFAULT '[]', important_facts TEXT DEFAULT '[]', request_counter INTEGER DEFAULT 0, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        await db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        await db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS long_responses (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message_id INTEGER, full_response TEXT, telegraph_url TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance_mode', '0')")
        await db.commit()

async def get_user(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def create_user(user_id: int, username: str = None, first_name: str = None) -> Dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        today = date.today().isoformat()
        await db.execute("INSERT INTO users (user_id, username, first_name, tokens, total_tokens_received, last_request_date, month_start) VALUES (?, ?, ?, ?, ?, ?, ?)", (user_id, username, first_name, NEW_USER_BONUS, NEW_USER_BONUS, today, today))
        await db.execute("INSERT INTO user_memory (user_id) VALUES (?)", (user_id,))
        await db.commit()
    return await get_user(user_id)

async def update_user_tokens(user_id: int, tokens_used: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET tokens = tokens - ?, total_tokens_used = total_tokens_used + ? WHERE user_id = ?", (tokens_used, tokens_used, user_id))
        await db.commit()

async def add_tokens(user_id: int, amount: int, desc: str = ""):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET tokens = tokens + ?, total_tokens_received = total_tokens_received + ? WHERE user_id = ?", (amount, amount, user_id))
        await db.commit()

async def get_user_memory(user_id: int) -> Dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM user_memory WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if row:
            r = dict(row)
            r['interests'] = json.loads(r['interests'] or '[]')
            r['problems'] = json.loads(r['problems'] or '[]')
            r['lessons_completed'] = json.loads(r['lessons_completed'] or '[]')
            r['important_facts'] = json.loads(r['important_facts'] or '[]')
            return r
        return {'user_id': user_id, 'memory_enabled': 1, 'personal_prompt': '', 'interests': [], 'problems': [], 'lessons_completed': [], 'important_facts': [], 'request_counter': 0}

async def update_user_memory(user_id: int, data: Dict):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE user_memory SET personal_prompt=?, interests=?, problems=?, lessons_completed=?, important_facts=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (data.get('personal_prompt',''), json.dumps(data.get('interests',[]),ensure_ascii=False), json.dumps(data.get('problems',[]),ensure_ascii=False), json.dumps(data.get('lessons_completed',[]),ensure_ascii=False), json.dumps(data.get('important_facts',[]),ensure_ascii=False), user_id))
        await db.commit()

async def toggle_memory(user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("SELECT memory_enabled FROM user_memory WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        new = 0 if row and row[0]==1 else 1
        await db.execute("UPDATE user_memory SET memory_enabled=? WHERE user_id=?", (new, user_id))
        await db.commit()
        return bool(new)

async def clear_memory(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE user_memory SET personal_prompt='', interests='[]', problems='[]', lessons_completed='[]', important_facts='[]', request_counter=0 WHERE user_id=?", (user_id,))
        await db.commit()

async def update_memory_counter(user_id: int, val: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE user_memory SET request_counter=? WHERE user_id=?", (val, user_id))
        await db.commit()

async def add_message(user_id: int, role: str, content: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT INTO messages (user_id, role, content) VALUES (?,?,?)", (user_id, role, content))
        await db.commit()

async def get_message_history(user_id: int, limit: int = 20) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT role, content FROM messages WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
        rows = await cur.fetchall()
        return [{"role": r['role'], "content": r['content']} for r in reversed(rows)]

async def clear_message_history(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM messages WHERE user_id=?", (user_id,))
        await db.commit()

async def get_setting(key: str) -> Optional[str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
        await db.commit()

async def save_long_response(user_id: int, msg_id: int, full: str, url: str) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("INSERT INTO long_responses (user_id,message_id,full_response,telegraph_url) VALUES (?,?,?,?)", (user_id, msg_id, full, url))
        await db.commit()
        return cur.lastrowid

async def get_long_response(rid: int) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM long_responses WHERE id=?", (rid,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def get_all_users() -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE is_blocked=0")
        return [dict(r) for r in await cur.fetchall()]

async def get_statistics() -> Dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        today = date.today().isoformat()
        r = {}
        cur = await db.execute("SELECT COUNT(*) FROM users"); r['total_users'] = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE last_request_date=?", (today,)); r['active_today'] = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at)>=DATE('now','-7 days')"); r['new_this_week'] = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COALESCE(SUM(daily_requests),0) FROM users WHERE last_request_date=?", (today,)); r['requests_today'] = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COALESCE(SUM(monthly_requests),0) FROM users"); r['requests_month'] = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COALESCE(SUM(total_requests),0) FROM users"); r['total_requests'] = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COALESCE(SUM(total_tokens_used),0) FROM users"); r['total_tokens_used'] = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM user_memory WHERE memory_enabled=1"); r['with_memory'] = (await cur.fetchone())[0]
        return r

async def update_user_stats(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        today = date.today().isoformat()
        month_start = date.today().replace(day=1).isoformat()
        cur = await db.execute("SELECT last_request_date, month_start FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        if row:
            if row[0] != today: await db.execute("UPDATE users SET daily_requests=0 WHERE user_id=?", (user_id,))
            if row[1] != month_start: await db.execute("UPDATE users SET monthly_requests=0, month_start=? WHERE user_id=?", (month_start, user_id))
        await db.execute("UPDATE users SET total_requests=total_requests+1, daily_requests=daily_requests+1, monthly_requests=monthly_requests+1, last_request_date=? WHERE user_id=?", (today, user_id))
        await db.commit()

async def block_user(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET is_blocked=1 WHERE user_id=?", (user_id,))
        await db.commit()

async def unblock_user(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET is_blocked=0 WHERE user_id=?", (user_id,))
        await db.commit()

async def get_messages(user_id: int, limit: int = 10):
    """Получить историю сообщений пользователя"""
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            """SELECT role, content FROM messages 
               WHERE user_id = ? 
               ORDER BY created_at DESC 
               LIMIT ?""",
            (user_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
