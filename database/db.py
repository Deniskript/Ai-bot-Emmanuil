import aiosqlite
import json
from datetime import datetime
from typing import Optional, Dict, List
import os
from config import DATABASE_PATH, NEW_USER_BONUS

os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            tokens INTEGER DEFAULT 5000, total_used INTEGER DEFAULT 0,
            total_requests INTEGER DEFAULT 0, is_blocked INTEGER DEFAULT 0,
            agreement INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS user_bots (
            user_id INTEGER, bot TEXT, character TEXT DEFAULT 'душевный',
            mood TEXT, custom_mood TEXT, msg_counter INTEGER DEFAULT 0,
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

async def get_user(uid: int) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM users WHERE user_id=?", (uid,))
        r = await c.fetchone()
        return dict(r) if r else None

async def create_user(uid: int, uname: str=None, fname: str=None) -> Dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT INTO users (user_id,username,first_name,tokens) VALUES (?,?,?,?)",
                        (uid, uname, fname, NEW_USER_BONUS))
        await db.commit()
    return await get_user(uid)

async def accept_agreement(uid: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET agreement=1 WHERE user_id=?", (uid,))
        await db.commit()

async def update_tokens(uid: int, used: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET tokens=tokens-?, total_used=total_used+?, total_requests=total_requests+1 WHERE user_id=?",
                        (used, used, uid))
        await db.commit()

async def add_tokens(uid: int, amt: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE users SET tokens=tokens+? WHERE user_id=?", (amt, uid))
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
        return {'user_id':uid,'bot':bot,'character':'душевный','mood':None,'custom_mood':None,'msg_counter':0}

async def set_char(uid: int, char: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE user_bots SET character=? WHERE user_id=? AND bot='luca'", (char, uid))
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
