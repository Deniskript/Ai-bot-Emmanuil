#!/bin/bash

mkdir -p database handlers keyboards utils

# ========== .env ==========
cat > .env << 'EOF'
BOT_TOKEN=ВАШ_ТОКЕН
OPENAI_API_KEY=ВАШ_КЛЮЧ
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
OPENAI_CHAT_MODEL=gpt-4o-mini
ADMIN_IDS=ВАШ_ID
CHANNEL_URL=https://t.me/channel
SUPPORT_URL=https://t.me/support
EOF

# ========== config.py ==========
cat > config.py << 'EOF'
import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/channel")
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/support")

SYSTEM_PROMPT = """Ты полезный AI-ассистент. Отвечай на русском языке."""
MAX_MESSAGE_LENGTH = 3500
PREVIEW_LENGTH = 800
MEMORY_REFRESH_INTERVAL = 17
MAX_HISTORY_WITH_MEMORY = 20
NEW_USER_BONUS = 5000
MIN_TOKENS_FOR_REQUEST = 100
DATABASE_PATH = "database/bot.db"
EOF

# ========== loader.py ==========
cat > loader.py << 'EOF'
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
EOF

# ========== main.py ==========
cat > main.py << 'EOF'
import asyncio
import logging
import sys
from loader import bot, dp
from database.db import init_db
from handlers import user, chat, admin

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    await init_db()
    dp.include_router(admin.router)
    dp.include_router(user.router)
    dp.include_router(chat.router)
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
EOF

# ========== database/__init__.py ==========
cat > database/__init__.py << 'EOF'
from . import db
EOF

# ========== database/db.py ==========
cat > database/db.py << 'EOF'
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
EOF

# ========== handlers/__init__.py ==========
cat > handlers/__init__.py << 'EOF'
from . import user, chat, admin
EOF

# ========== handlers/user.py ==========
cat > handlers/user.py << 'EOF'
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from database import db
from keyboards import reply, inline

router = Router()

def fmt(n): return f"{n:,}".replace(",", " ")

@router.message(CommandStart())
async def cmd_start(msg: Message):
    u = await db.get_user(msg.from_user.id)
    if not u:
        u = await db.create_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
        txt = f"👋 Добро пожаловать!\n\n🎁 Вам начислено <b>{fmt(u['tokens'])}</b> токенов!"
    else:
        txt = f"👋 С возвращением!\n\n💎 Баланс: <b>{fmt(u['tokens'])}</b> токенов"
    await msg.answer(txt, reply_markup=reply.main_keyboard())

@router.message(F.text == "✨ Начать диалог")
async def new_dialog(msg: Message):
    await db.clear_message_history(msg.from_user.id)
    await msg.answer("✨ Диалог начат! Напишите вопрос.", reply_markup=reply.main_keyboard())

@router.message(F.text == "👤 Мой кабинет")
async def cabinet(msg: Message):
    u = await db.get_user(msg.from_user.id)
    if not u: u = await db.create_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    m = await db.get_user_memory(msg.from_user.id)
    mem_st = "🟢 ВКЛ" if m['memory_enabled'] else "🔴 ВЫКЛ"
    txt = f"👤 <b>КАБИНЕТ</b>\n\n🆔 {msg.from_user.id}\n💎 Баланс: <b>{fmt(u['tokens'])}</b>\n📉 Потрачено: {fmt(u['total_tokens_used'])}\n💬 Запросов: {u['total_requests']}\n🧠 Память: {mem_st}"
    await msg.answer(txt, reply_markup=inline.cabinet_keyboard(m['memory_enabled']))

@router.callback_query(F.data == "topup_balance")
async def topup_cb(cb: CallbackQuery):
    u = await db.get_user(cb.from_user.id)
    await cb.message.edit_text(f"💰 Баланс: <b>{fmt(u['tokens'])}</b>\n\n🥉 45 000 — 300₽\n🥈 90 000 — 600₽\n🥇 180 000 — 900₽", reply_markup=inline.topup_keyboard())

@router.callback_query(F.data == "toggle_memory")
async def toggle_mem(cb: CallbackQuery):
    new = await db.toggle_memory(cb.from_user.id)
    await cb.answer("🟢 Память ВКЛ" if new else "🔴 Память ВЫКЛ")
    await cb.message.edit_reply_markup(reply_markup=inline.cabinet_keyboard(new))

@router.callback_query(F.data == "clear_memory")
async def clear_mem(cb: CallbackQuery):
    await cb.message.edit_text("🗑 Очистить память?", reply_markup=inline.confirm_clear_keyboard())

@router.callback_query(F.data == "confirm_clear")
async def confirm_clear(cb: CallbackQuery):
    await db.clear_memory(cb.from_user.id)
    await cb.answer("✅ Очищено")
    await cabinet(cb.message)

@router.callback_query(F.data == "cancel_clear")
async def cancel_clear(cb: CallbackQuery):
    await cb.answer("Отменено")
    await cabinet(cb.message)

@router.message(F.text == "💰 Пополнить")
async def topup(msg: Message):
    u = await db.get_user(msg.from_user.id)
    await msg.answer(f"💰 Баланс: <b>{fmt(u['tokens'])}</b>\n\n🥉 45 000 — 300₽\n🥈 90 000 — 600₽\n🥇 180 000 — 900₽", reply_markup=inline.topup_keyboard())

@router.message(F.text == "💡 Помощь")
async def help_cmd(msg: Message):
    await msg.answer("💡 <b>Помощь</b>\n\n💬 Текст\n📷 Фото\n🎤 Голос", reply_markup=inline.help_keyboard())
EOF

# ========== handlers/chat.py ==========
cat > handlers/chat.py << 'EOF'
import asyncio, base64
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from loader import bot
from database import db
from keyboards import inline
from utils.ai_client import get_ai_response, get_vision_response
from utils.voice import transcribe_voice
from utils.telegraph import create_telegraph_page
from utils.memory import get_messages_with_memory, update_memory
from config import ADMIN_IDS, MIN_TOKENS_FOR_REQUEST, MAX_MESSAGE_LENGTH, PREVIEW_LENGTH, SYSTEM_PROMPT

router = Router()
def fmt(n): return f"{n:,}".replace(",", " ")

async def check(msg):
    uid = msg.from_user.id
    if await db.get_setting('maintenance_mode') == '1' and uid not in ADMIN_IDS:
        return False, "⚙️ Тех. работы"
    u = await db.get_user(uid)
    if not u: u = await db.create_user(uid, msg.from_user.username, msg.from_user.first_name)
    if u['is_blocked']: return False, "🚫 Заблокированы"
    if u['tokens'] < MIN_TOKENS_FOR_REQUEST: return False, f"❌ Мало токенов: {fmt(u['tokens'])}"
    return True, None

async def send_resp(msg, uid, txt):
    if len(txt) <= MAX_MESSAGE_LENGTH:
        await msg.answer(txt)
    else:
        preview = txt[:PREVIEW_LENGTH] + "..."
        url = await create_telegraph_page("Ответ", txt)
        sent = await msg.answer(preview)
        rid = await db.save_long_response(uid, sent.message_id, txt, url)
        await msg.answer("📄 Полный:", reply_markup=inline.long_resp_keyboard(url, rid))

@router.message(F.text & ~F.text.startswith("/"))
async def on_text(msg: Message):
    if msg.text in ["✨ Начать диалог", "👤 Мой кабинет", "💰 Пополнить", "💡 Помощь"]: return
    ok, err = await check(msg)
    if not ok: await msg.answer(err); return
    uid = msg.from_user.id
    st = await msg.answer("✍️ Печатаю...")
    try:
        msgs = await get_messages_with_memory(uid)
        full = [{"role":"system","content":SYSTEM_PROMPT}] + msgs + [{"role":"user","content":msg.text}]
        resp, tok = await get_ai_response(full)
        await db.update_user_tokens(uid, tok)
        await db.add_message(uid, "user", msg.text)
        await db.add_message(uid, "assistant", resp)
        await db.update_user_stats(uid)
        m = await db.get_user_memory(uid)
        if m['memory_enabled']: asyncio.create_task(update_memory(uid, msg.text, resp))
    except Exception as e: resp = f"❌ {e}"
    try: await st.delete()
    except: pass
    await send_resp(msg, uid, resp)

@router.message(F.photo)
async def on_photo(msg: Message):
    ok, err = await check(msg)
    if not ok: await msg.answer(err); return
    uid = msg.from_user.id
    st = await msg.answer("🔍 Анализирую...")
    try:
        photo = msg.photo[-1]
        file = await bot.get_file(photo.file_id)
        data = await bot.download_file(file.file_path)
        b64 = base64.b64encode(data.read()).decode()
        cap = msg.caption or "Что на фото?"
        resp, tok = await get_vision_response(b64, cap)
        await db.update_user_tokens(uid, tok)
        await db.add_message(uid, "user", f"[Фото] {cap}")
        await db.add_message(uid, "assistant", resp)
        await db.update_user_stats(uid)
    except Exception as e: resp = f"❌ {e}"
    try: await st.delete()
    except: pass
    await send_resp(msg, uid, resp)

@router.message(F.voice)
async def on_voice(msg: Message):
    ok, err = await check(msg)
    if not ok: await msg.answer(err); return
    uid = msg.from_user.id
    st = await msg.answer("🎧 Слушаю...")
    try:
        file = await bot.get_file(msg.voice.file_id)
        data = await bot.download_file(file.file_path)
        text = await transcribe_voice(data)
        msgs = await get_messages_with_memory(uid)
        full = [{"role":"system","content":SYSTEM_PROMPT}] + msgs + [{"role":"user","content":text}]
        resp, tok = await get_ai_response(full)
        await db.update_user_tokens(uid, tok)
        await db.add_message(uid, "user", f"[Голос] {text}")
        await db.add_message(uid, "assistant", resp)
        await db.update_user_stats(uid)
        m = await db.get_user_memory(uid)
        if m['memory_enabled']: asyncio.create_task(update_memory(uid, text, resp))
        await msg.answer(f"🎤 <i>{text}</i>")
    except Exception as e: resp = f"❌ {e}"
    try: await st.delete()
    except: pass
    await send_resp(msg, uid, resp)

@router.callback_query(F.data.startswith("filter:"))
async def filter_resp(cb: CallbackQuery):
    rid = int(cb.data.split(":")[1])
    r = await db.get_long_response(rid)
    if not r: await cb.message.answer("❌"); return
    await cb.answer("Фильтрую...")
    resp, tok = await get_ai_response([{"role":"system","content":"Сократи до ключевых мыслей"},{"role":"user","content":r['full_response']}])
    await db.update_user_tokens(cb.from_user.id, tok)
    await cb.message.answer(f"📝 <b>Кратко:</b>\n\n{resp}")
EOF

# ========== handlers/admin.py ==========
cat > handlers/admin.py << 'EOF'
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loader import bot
from database import db
from keyboards import inline
from config import ADMIN_IDS

router = Router()

class St(StatesGroup):
    user_id = State()
    tokens = State()
    broadcast = State()
    find = State()

def adm(uid): return uid in ADMIN_IDS
def fmt(n): return f"{n:,}".replace(",", " ")

@router.message(Command("admin"))
async def panel(msg: Message, state: FSMContext):
    if not adm(msg.from_user.id): return
    await state.clear()
    await msg.answer("👑 <b>АДМИН</b>", reply_markup=inline.admin_keyboard())

@router.callback_query(F.data == "admin_close")
async def close(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    await state.clear()
    await cb.message.delete()

@router.callback_query(F.data == "admin_back")
async def back(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    await state.clear()
    await cb.message.edit_text("👑 <b>АДМИН</b>", reply_markup=inline.admin_keyboard())

@router.callback_query(F.data == "admin_give")
async def give_start(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    await cb.message.edit_text("💎 Введите ID:", reply_markup=inline.admin_cancel())
    await state.set_state(St.user_id)

@router.message(St.user_id)
async def got_id(msg: Message, state: FSMContext):
    if not adm(msg.from_user.id): return
    try: uid = int(msg.text)
    except: await msg.answer("❌ Число!"); return
    u = await db.get_user(uid)
    if not u: await msg.answer("❌ Не найден", reply_markup=inline.admin_cancel()); return
    await state.update_data(target=uid)
    await msg.answer(f"👤 {uid}\n💎 {fmt(u['tokens'])}", reply_markup=inline.give_keyboard())

@router.callback_query(F.data.startswith("give:"))
async def give(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    amt = int(cb.data.split(":")[1])
    d = await state.get_data()
    t = d.get('target')
    if not t: await cb.answer("Err"); return
    await db.add_tokens(t, amt)
    try: await bot.send_message(t, f"🎉 +{fmt(amt)} токенов!")
    except: pass
    await cb.message.edit_text(f"✅ +{fmt(amt)} для {t}", reply_markup=inline.admin_back())
    await state.clear()

@router.callback_query(F.data == "give_custom")
async def give_cust(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    await cb.message.edit_text("✏️ Сколько токенов?", reply_markup=inline.admin_cancel())
    await state.set_state(St.tokens)

@router.message(St.tokens)
async def got_tokens(msg: Message, state: FSMContext):
    if not adm(msg.from_user.id): return
    try: amt = int(msg.text)
    except: await msg.answer("❌ Число!"); return
    d = await state.get_data()
    t = d.get('target')
    if not t: await msg.answer("Err /admin"); await state.clear(); return
    await db.add_tokens(t, amt)
    try: await bot.send_message(t, f"🎉 +{fmt(amt)} токенов!")
    except: pass
    await msg.answer(f"✅ +{fmt(amt)}", reply_markup=inline.admin_back())
    await state.clear()

@router.callback_query(F.data == "admin_find")
async def find_start(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    await cb.message.edit_text("👤 ID:", reply_markup=inline.admin_cancel())
    await state.set_state(St.find)

@router.message(St.find)
async def found(msg: Message, state: FSMContext):
    if not adm(msg.from_user.id): return
    try: uid = int(msg.text)
    except: await msg.answer("❌"); return
    u = await db.get_user(uid)
    if not u: await msg.answer("❌", reply_markup=inline.admin_back()); await state.clear(); return
    m = await db.get_user_memory(uid)
    await msg.answer(f"👤 {uid}\n@{u['username'] or '-'}\n💎 {fmt(u['tokens'])}\n🧠 {'ВКЛ' if m['memory_enabled'] else 'ВЫКЛ'}", reply_markup=inline.user_keyboard(uid))
    await state.clear()

@router.callback_query(F.data.startswith("adm_give:"))
async def adm_give(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    uid = int(cb.data.split(":")[1])
    await state.update_data(target=uid)
    await cb.message.edit_text("Токены:", reply_markup=inline.give_keyboard())

@router.callback_query(F.data.startswith("adm_block:"))
async def block(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    uid = int(cb.data.split(":")[1])
    await db.block_user(uid)
    await cb.message.edit_text(f"🚫 {uid} заблокирован", reply_markup=inline.admin_back())

@router.callback_query(F.data.startswith("adm_mem:"))
async def mem(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    uid = int(cb.data.split(":")[1])
    m = await db.get_user_memory(uid)
    await cb.message.edit_text(f"🧠 {uid}\n\n{m['personal_prompt'] or 'Пусто'}", reply_markup=inline.admin_back())

@router.callback_query(F.data == "admin_broadcast")
async def bc_start(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    await cb.message.edit_text("📢 Текст:", reply_markup=inline.admin_cancel())
    await state.set_state(St.broadcast)

@router.message(St.broadcast)
async def bc_text(msg: Message, state: FSMContext):
    if not adm(msg.from_user.id): return
    await state.update_data(bc=msg.text)
    await msg.answer(f"📢 Превью:\n\n{msg.text}", reply_markup=inline.bc_keyboard())

@router.callback_query(F.data == "bc_confirm")
async def bc_send(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    d = await state.get_data()
    txt = d.get('bc')
    if not txt: await cb.answer("Err"); return
    await cb.message.edit_text("📤...")
    users = await db.get_all_users()
    ok, err = 0, 0
    for u in users:
        try: await bot.send_message(u['user_id'], txt); ok += 1
        except: err += 1
    await cb.message.edit_text(f"✅ {ok} / ❌ {err}", reply_markup=inline.admin_back())
    await state.clear()

@router.callback_query(F.data == "admin_maint")
async def maint(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    st = await db.get_setting('maintenance_mode')
    on = st == '1'
    await cb.message.edit_text(f"🔧 {'🔴 ВКЛ' if on else '🟢 ВЫКЛ'}", reply_markup=inline.maint_keyboard(on))

@router.callback_query(F.data == "toggle_maint")
async def tog_maint(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    st = await db.get_setting('maintenance_mode')
    new = '0' if st == '1' else '1'
    await db.set_setting('maintenance_mode', new)
    on = new == '1'
    await cb.message.edit_text(f"🔧 {'🔴 ВКЛ' if on else '🟢 ВЫКЛ'}", reply_markup=inline.maint_keyboard(on))

@router.callback_query(F.data == "admin_stats")
async def stats(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    s = await db.get_statistics()
    await cb.message.edit_text(f"📊 Юзеров: {s['total_users']}\nАктивных: {s['active_today']}\nНовых/нед: {s['new_this_week']}\n\n💬 Сегодня: {s['requests_today']}\nМесяц: {s['requests_month']}\nВсего: {s['total_requests']}\n\n💎 Токенов: {fmt(s['total_tokens_used'])}", reply_markup=inline.admin_back())
EOF

# ========== keyboards/__init__.py ==========
cat > keyboards/__init__.py << 'EOF'
from . import reply, inline
EOF

# ========== keyboards/reply.py ==========
cat > keyboards/reply.py << 'EOF'
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✨ Начать диалог"), KeyboardButton(text="👤 Мой кабинет")],
        [KeyboardButton(text="💰 Пополнить"), KeyboardButton(text="💡 Помощь")]
    ], resize_keyboard=True)
EOF

# ========== keyboards/inline.py ==========
cat > keyboards/inline.py << 'EOF'
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CHANNEL_URL, SUPPORT_URL

def cabinet_keyboard(mem_on):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить", callback_data="topup_balance")],
        [InlineKeyboardButton(text=f"🧠 Память: {'ВКЛ' if mem_on else 'ВЫКЛ'}", callback_data="toggle_memory")],
        [InlineKeyboardButton(text="🗑 Очистить память", callback_data="clear_memory")]
    ])

def confirm_clear_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="confirm_clear"), InlineKeyboardButton(text="❌ Нет", callback_data="cancel_clear")]
    ])

def topup_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥉 45 000 — 300₽", callback_data="buy:45000")],
        [InlineKeyboardButton(text="🥈 90 000 — 600₽", callback_data="buy:90000")],
        [InlineKeyboardButton(text="🥇 180 000 — 900₽", callback_data="buy:180000")],
        [InlineKeyboardButton(text="💬 Оплата", url=SUPPORT_URL)]
    ])

def help_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Канал", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="🆘 Поддержка", url=SUPPORT_URL)]
    ])

def long_resp_keyboard(url, rid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Полный", url=url)],
        [InlineKeyboardButton(text="📝 Кратко", callback_data=f"filter:{rid}")]
    ])

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Выдать", callback_data="admin_give")],
        [InlineKeyboardButton(text="👤 Найти", callback_data="admin_find")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔧 Тех.работы", callback_data="admin_maint")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")]
    ])

def admin_cancel():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]])

def admin_back():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]])

def give_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥉 +45 000", callback_data="give:45000")],
        [InlineKeyboardButton(text="🥈 +90 000", callback_data="give:90000")],
        [InlineKeyboardButton(text="🥇 +180 000", callback_data="give:180000")],
        [InlineKeyboardButton(text="✏️ Вручную", callback_data="give_custom")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
    ])

def maint_keyboard(on):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Выкл" if on else "🔴 Вкл", callback_data="toggle_maint")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])

def bc_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="bc_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
    ])

def user_keyboard(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Выдать", callback_data=f"adm_give:{uid}")],
        [InlineKeyboardButton(text="🧠 Память", callback_data=f"adm_mem:{uid}")],
        [InlineKeyboardButton(text="🚫 Бан", callback_data=f"adm_block:{uid}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])
EOF

# ========== utils/__init__.py ==========
cat > utils/__init__.py << 'EOF'
from . import ai_client, voice, telegraph, memory
EOF

# ========== utils/ai_client.py ==========
cat > utils/ai_client.py << 'EOF'
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_CHAT_MODEL

client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

async def get_ai_response(messages):
    try:
        r = await client.chat.completions.create(model=OPENAI_CHAT_MODEL, messages=messages, max_tokens=4000)
        return r.choices[0].message.content, r.usage.total_tokens if r.usage else 0
    except Exception as e:
        return f"❌ {e}", 0

async def get_vision_response(b64, prompt):
    try:
        r = await client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}], max_tokens=2000)
        return r.choices[0].message.content, r.usage.total_tokens if r.usage else 0
    except Exception as e:
        return f"❌ {e}", 0
EOF

# ========== utils/voice.py ==========
cat > utils/voice.py << 'EOF'
import tempfile, os
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL

client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

async def transcribe_voice(data):
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(data.read())
            path = f.name
        with open(path, "rb") as a:
            t = await client.audio.transcriptions.create(model="whisper-1", file=a, language="ru")
        os.unlink(path)
        return t.text
    except Exception as e:
        return f"[Ошибка: {e}]"
EOF

# ========== utils/telegraph.py ==========
cat > utils/telegraph.py << 'EOF'
import asyncio
from telegraph import Telegraph

tg = Telegraph()
tg.create_account(short_name="AIBot")

async def create_telegraph_page(title, content):
    try:
        html = "".join(f"<p>{p}</p>" for p in content.split('\n\n') if p.strip()) or f"<p>{content}</p>"
        loop = asyncio.get_event_loop()
        r = await loop.run_in_executor(None, lambda: tg.create_page(title=title, html_content=html))
        return f"https://telegra.ph/{r['path']}"
    except:
        return "https://telegra.ph/error"
EOF

# ========== utils/memory.py ==========
cat > utils/memory.py << 'EOF'
import json
from database import db
from utils.ai_client import get_ai_response
from config import MEMORY_REFRESH_INTERVAL, MAX_HISTORY_WITH_MEMORY

async def get_messages_with_memory(uid):
    m = await db.get_user_memory(uid)
    if not m['memory_enabled']:
        return await db.get_message_history(uid, MAX_HISTORY_WITH_MEMORY)
    new_c = (m['request_counter'] + 1) % MEMORY_REFRESH_INTERVAL
    await db.update_memory_counter(uid, new_c)
    msgs = []
    if new_c == 0 and m['personal_prompt']:
        msgs.append({"role":"system","content":f"[ПАМЯТЬ]\n{m['personal_prompt']}"})
    msgs.extend(await db.get_message_history(uid, MAX_HISTORY_WITH_MEMORY))
    return msgs

async def update_memory(uid, user_msg, ai_resp):
    m = await db.get_user_memory(uid)
    if not m['memory_enabled']: return
    prompt = f"""Извлеки новую инфо о человеке из диалога. 
Текущая память: {m['personal_prompt'] or 'Пусто'}
Диалог:
User: {user_msg}
AI: {ai_resp[:500]}
JSON: {{"name":"или null","interest":"или null","problem":"или null","fact":"или null"}}
Если ничего: {{"nothing":true}}
Только JSON!"""
    try:
        r, _ = await get_ai_response([{"role":"system","content":"JSON only"},{"role":"user","content":prompt}])
        r = r.strip()
        if r.startswith("```"): r = r.split("\n",1)[1]
        if r.endswith("```"): r = r.rsplit("\n",1)[0]
        d = json.loads(r)
        if d.get("nothing"): return
        interests = m['interests']
        problems = m['problems']
        facts = m['important_facts']
        if d.get("interest") and d["interest"] not in interests: interests.append(d["interest"])
        if d.get("problem") and d["problem"] not in problems: problems.append(d["problem"])
        if d.get("fact") and d["fact"] not in facts: facts.append(d["fact"])
        parts = ["[ПАМЯТЬ]"]
        if d.get("name"): parts.append(f"Имя: {d['name']}")
        if interests: parts.append(f"Интересы: {', '.join(interests[-5:])}")
        if problems: parts.append(f"Проблемы: {', '.join(problems[-3:])}")
        if facts: parts.append(f"Факты: {', '.join(facts[-3:])}")
        await db.update_user_memory(uid, {'personal_prompt':'\n'.join(parts),'interests':interests,'problems':problems,'lessons_completed':m['lessons_completed'],'important_facts':facts})
    except: pass
EOF

# ========== requirements.txt ==========
cat > requirements.txt << 'EOF'
aiogram==3.4.1
openai==1.30.0
aiosqlite==0.19.0
python-dotenv==1.0.1
telegraph==2.2.0
aiohttp==3.9.3
EOF

echo "✅ Все файлы созданы!"
echo ""
echo "Теперь:"
echo "1. nano .env  - заполните токены"
echo "2. python3 -m venv venv"
echo "3. source venv/bin/activate"
echo "4. pip install -r requirements.txt"
echo "5. python main.py"
