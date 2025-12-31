from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import reply
from utils.ai_client import ask
from utils.memory import update_memory, build_memory_context
from utils.voice import download_voice, transcribe_voice
from prompts.all_prompts import LUCA_BASE, LUCA_SOUL, LUCA_SER, LUCA_HUM
from config import MIN_TOKENS
from loader import bot
import asyncio
import base64

router = Router()

class LucaSt(StatesGroup):
    menu = State()
    chat = State()
    char = State()

CHARS = {'душевный': LUCA_SOUL, 'серьезный': LUCA_SER, 'человек': LUCA_HUM}

# === ВХОД В LUCA ===
@router.message(F.text == "💭Luca")
async def luca_enter(msg: Message, state: FSMContext):
    cfg = await db.get_bot_cfg('luca')
    if not cfg['enabled']:
        await msg.answer("🔴 Luca временно недоступен")
        return
    await state.set_state(LucaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    await msg.answer(
        f"📝 <b>Luca — универсальный помощник</b>\n\n"
        f"🎚️ Характер: {s['character']}\n"
        f"🤖 Модель: {cfg['model']}",
        reply_markup=reply.luca_kb()
    )

# === МЕНЮ LUCA ===
@router.message(LucaSt.menu, F.text == "💬 Начать диалог")
async def luca_start_chat(msg: Message, state: FSMContext):
    await db.clear_msgs(msg.from_user.id, 'luca')
    await db.reset_msg_counter(msg.from_user.id, 'luca')
    await state.set_state(LucaSt.chat)
    await msg.answer(
        "💬 <b>Диалог с Luca начат!</b>\n\nПиши что угодно:",
        reply_markup=reply.luca_chat_kb()
    )

@router.message(LucaSt.menu, F.text == "🎚️ Характер")
async def luca_char_menu(msg: Message, state: FSMContext):
    await state.set_state(LucaSt.char)
    await msg.answer("🎭 Выбери характер Luca:", reply_markup=reply.luca_char_kb())

@router.message(LucaSt.menu, F.text == "🗑 Очистить")
async def luca_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'luca')
    await msg.answer("🗑 История очищена!")

@router.message(LucaSt.menu, F.text == "❓ Помощь")
async def luca_help(msg: Message):
    text = await db.get_text('help_luca')
    if not text:
        text = "📝 <b>Luca</b> — универсальный AI-помощник для любых задач"
    await msg.answer(text)

@router.message(LucaSt.menu, F.text == "◀️ Назад")
async def luca_back(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("🤖 Выбери бота:", reply_markup=reply.bots_menu_kb())

# === ВЫБОР ХАРАКТЕРА ===
@router.message(LucaSt.char, F.text == "🙏 Душевный")
async def char_soul(msg: Message, state: FSMContext):
    await db.set_char(msg.from_user.id, 'душевный')
    await state.set_state(LucaSt.menu)
    await msg.answer("✅ Характер: Душевный", reply_markup=reply.luca_kb())

@router.message(LucaSt.char, F.text == "💯 Серьезный")
async def char_ser(msg: Message, state: FSMContext):
    await db.set_char(msg.from_user.id, 'серьезный')
    await state.set_state(LucaSt.menu)
    await msg.answer("✅ Характер: Серьезный", reply_markup=reply.luca_kb())

@router.message(LucaSt.char, F.text == "❤️ Человек")
async def char_hum(msg: Message, state: FSMContext):
    await db.set_char(msg.from_user.id, 'человек')
    await state.set_state(LucaSt.menu)
    await msg.answer("✅ Характер: Человек", reply_markup=reply.luca_kb())

@router.message(LucaSt.char, F.text == "◀️ Назад к Luca")
async def char_back(msg: Message, state: FSMContext):
    await state.set_state(LucaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    cfg = await db.get_bot_cfg('luca')
    await msg.answer(
        f"📝 <b>Luca</b>\n\n🎚️ Характер: {s['character']}\n🤖 Модель: {cfg['model']}",
        reply_markup=reply.luca_kb()
    )

# === ЧАТ ===
@router.message(LucaSt.chat, F.text == "🛑 Завершить")
async def luca_stop(msg: Message, state: FSMContext):
    await state.set_state(LucaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    cfg = await db.get_bot_cfg('luca')
    await msg.answer(
        f"👋 Диалог завершён!\n\n📝 <b>Luca</b>\n🎚️ Характер: {s['character']}",
        reply_markup=reply.luca_kb()
    )

@router.message(LucaSt.chat, F.text == "🗑 Очистить")
async def luca_chat_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'luca')
    await msg.answer("🗑 История очищена! Продолжай:")

async def process_luca_message(msg: Message, text: str, image_b64: str = None):
    u = await db.get_user(msg.from_user.id)
    if not u or u['tokens'] < MIN_TOKENS:
        await msg.answer("❌ Недостаточно токенов!")
        return
    start_time = asyncio.get_event_loop().time()
    status_msg = await msg.answer("🔎 Обрабатываю...")

    async def update_status():
        while True:
            await asyncio.sleep(1)
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            try:
                await status_msg.edit_text(f"✍️ Luca печатает... {elapsed} сек")
            except:
                break

    status_task = asyncio.create_task(update_status())
    try:
        cfg = await db.get_bot_cfg('luca')
        s = await db.get_user_bot(msg.from_user.id, 'luca')
        char = CHARS.get(s['character'], LUCA_SOUL)
        mem = await db.get_memory(msg.from_user.id, 'luca')
        hist = await db.get_msgs(msg.from_user.id, 'luca')
        cnt = await db.inc_msg_counter(msg.from_user.id, 'luca')
        sys = LUCA_BASE + "\n" + char + build_memory_context(mem)
        if cnt >= 20:
            sys += "\n\n⚡ Упомяни что-то из памяти!"
            await db.reset_msg_counter(msg.from_user.id, 'luca')
        msgs = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": text}]
        resp, tok = await ask(msgs, cfg['model'], image_b64)
        await db.update_tokens(msg.from_user.id, tok)
        await db.add_msg(msg.from_user.id, 'luca', 'user', text)
        await db.add_msg(msg.from_user.id, 'luca', 'assistant', resp)
        asyncio.create_task(update_memory(msg.from_user.id, 'luca', text, resp))
    finally:
        status_task.cancel()
        try:
            await status_msg.delete()
        except:
            pass
    elapsed = int(asyncio.get_event_loop().time() - start_time)
    await msg.answer(f"{resp}\n\n<i>💭Luca | ⏱ {elapsed} сек</i>")

@router.message(LucaSt.chat, F.text)
async def luca_chat_text(msg: Message):
    await process_luca_message(msg, msg.text)

@router.message(LucaSt.chat, F.voice)
async def luca_chat_voice(msg: Message):
    status = await msg.answer("🎤 Распознаю голос...")
    try:
        file_path = await download_voice(bot, msg.voice.file_id)
        text = await transcribe_voice(file_path)
        if not text:
            await status.edit_text("❌ Не распознано")
            return
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ {e}")
        return
    await process_luca_message(msg, text)

@router.message(LucaSt.chat, F.photo)
async def luca_chat_photo(msg: Message):
    status = await msg.answer("📷 Анализирую...")
    try:
        photo = msg.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_data = await bot.download_file(file.file_path)
        image_b64 = base64.b64encode(file_data.read()).decode()
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ {e}")
        return
    text = msg.caption or "Что на изображении?"
    await process_luca_message(msg, text, image_b64)
