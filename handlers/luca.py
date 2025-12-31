from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import inline
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
    chat = State()

CHARS = {'душевный': LUCA_SOUL, 'серьезный': LUCA_SER, 'человек': LUCA_HUM}

@router.callback_query(F.data == "bot:luca")
async def luca_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    cfg = await db.get_bot_cfg('luca')
    if not cfg['enabled']:
        await cb.answer("🔴 Luca временно недоступен", show_alert=True)
        return
    s = await db.get_user_bot(cb.from_user.id, 'luca')
    await cb.message.edit_text(
        f"🧑 <b>Luca — друг</b>\n\nХарактер: {s['character']}\nМодель: {cfg['model']}",
        reply_markup=inline.luca_kb()
    )

@router.callback_query(F.data == "luca:char")
async def luca_char(cb: CallbackQuery):
    await cb.message.edit_text("🎭 Выбери характер Luca:", reply_markup=inline.luca_char_kb())

@router.callback_query(F.data.startswith("char:"))
async def set_char(cb: CallbackQuery):
    c = cb.data.split(":")[1]
    await db.set_char(cb.from_user.id, c)
    await cb.answer(f"✅ Характер: {c}")
    s = await db.get_user_bot(cb.from_user.id, 'luca')
    cfg = await db.get_bot_cfg('luca')
    await cb.message.edit_text(
        f"🧑 <b>Luca — друг</b>\n\nХарактер: {s['character']}\nМодель: {cfg['model']}",
        reply_markup=inline.luca_kb()
    )

@router.callback_query(F.data == "luca:start")
async def luca_start(cb: CallbackQuery, state: FSMContext):
    await db.clear_msgs(cb.from_user.id, 'luca')
    await db.reset_msg_counter(cb.from_user.id, 'luca')
    await state.set_state(LucaSt.chat)
    await state.update_data(bot='luca')
    await cb.message.edit_text(
        "💬 <b>Диалог с Luca начат!</b>\n\nПиши что угодно.\n\n/stop — завершить"
    )

async def process_luca_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    u = await db.get_user(msg.from_user.id)
    if not u or u['tokens'] < MIN_TOKENS:
        await msg.answer("❌ Недостаточно токенов.")
        return
    start_time = asyncio.get_event_loop().time()
    status_msg = await msg.answer("🔎 Обрабатываю... 0 сек")

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
    await msg.answer(f"{resp}\n\n<i>🧑 Luca | ⏱ {elapsed} сек</i>")

@router.message(LucaSt.chat, F.text)
async def luca_chat_text(msg: Message, state: FSMContext):
    if msg.text.startswith("/"):
        if msg.text == "/stop":
            await state.clear()
            await msg.answer("👋 Диалог завершён!", reply_markup=inline.bots_kb())
        return
    await process_luca_message(msg, state, msg.text)

@router.message(LucaSt.chat, F.voice)
async def luca_chat_voice(msg: Message, state: FSMContext):
    status = await msg.answer("🎤 Распознаю голос...")
    try:
        file_path = await download_voice(bot, msg.voice.file_id)
        if not file_path:
            await status.edit_text("❌ Ошибка скачивания")
            return
        text = await transcribe_voice(file_path)
        if not text:
            await status.edit_text("❌ Не распознано")
            return
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ {e}")
        return
    await process_luca_message(msg, state, text)

@router.message(LucaSt.chat, F.photo)
async def luca_chat_photo(msg: Message, state: FSMContext):
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
    await process_luca_message(msg, state, text, image_b64)
