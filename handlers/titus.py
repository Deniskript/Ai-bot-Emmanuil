from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import reply
from utils.ai_client import ask
from utils.memory import update_memory, build_memory_context
from utils.voice import download_voice, transcribe_voice
from prompts.all_prompts import TITUS_BASE
from config import MIN_TOKENS
from loader import bot
import asyncio
import base64

router = Router()

class TitusSt(StatesGroup):
    menu = State()
    chat = State()

@router.message(F.text == "📓 Titus")
async def titus_enter(msg: Message, state: FSMContext):
    cfg = await db.get_bot_cfg('titus')
    if not cfg['enabled']:
        await msg.answer("🔴 Titus временно недоступен")
        return
    await state.set_state(TitusSt.menu)
    await msg.answer(
        f"📚 <b>Titus — эксперт</b>\n\n🤖 Модель: {cfg['model']}",
        reply_markup=reply.titus_kb()
    )

@router.message(TitusSt.menu, F.text == "💬 Начать диалог")
async def titus_start_chat(msg: Message, state: FSMContext):
    await db.clear_msgs(msg.from_user.id, 'titus')
    await state.set_state(TitusSt.chat)
    await msg.answer("💬 <b>Диалог с Titus начат!</b>", reply_markup=reply.titus_chat_kb())

@router.message(TitusSt.menu, F.text == "🗑 Очистить")
async def titus_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'titus')
    await msg.answer("🗑 История очищена!")

@router.message(TitusSt.menu, F.text == "❓ Помощь")
async def titus_help(msg: Message):
    text = await db.get_text('help_titus')
    if not text:
        text = "📚 <b>Titus</b> — AI-эксперт"
    await msg.answer(text)

@router.message(TitusSt.menu, F.text == "◀️ Назад")
async def titus_back(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("🤖 Выбери бота:", reply_markup=reply.bots_menu_kb())

@router.message(TitusSt.chat, F.text == "🛑 Завершить")
async def titus_stop(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.menu)
    cfg = await db.get_bot_cfg('titus')
    await msg.answer(f"👋 Диалог завершён!", reply_markup=reply.titus_kb())

@router.message(TitusSt.chat, F.text == "🗑 Очистить")
async def titus_chat_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'titus')
    await msg.answer("🗑 История очищена!")

async def process_titus_message(msg: Message, text: str, image_b64: str = None):
    u = await db.get_user(msg.from_user.id)
    if not u or u['tokens'] < MIN_TOKENS:
        await msg.answer("❌ Недостаточно токенов!")
        return
    start_time = asyncio.get_event_loop().time()
    status_msg = await msg.answer("🔎 Исследую...")
    async def update_status():
        while True:
            await asyncio.sleep(1)
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            try:
                await status_msg.edit_text(f"📓 Titus изучает... {elapsed} сек")
            except:
                break
    status_task = asyncio.create_task(update_status())
    try:
        cfg = await db.get_bot_cfg('titus')
        mem = await db.get_memory(msg.from_user.id, 'titus')
        hist = await db.get_msgs(msg.from_user.id, 'titus')
        sys = TITUS_BASE + build_memory_context(mem)
        msgs = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": text}]
        resp, tok = await ask(msgs, cfg['model'], image_b64)
        await db.update_tokens(msg.from_user.id, tok)
        await db.add_msg(msg.from_user.id, 'titus', 'user', text)
        await db.add_msg(msg.from_user.id, 'titus', 'assistant', resp)
        asyncio.create_task(update_memory(msg.from_user.id, 'titus', text, resp))
    finally:
        status_task.cancel()
        try:
            await status_msg.delete()
        except:
            pass
    elapsed = int(asyncio.get_event_loop().time() - start_time)
    await msg.answer(f"{resp}\n\n<i>📓 Titus | ⏱ {elapsed} сек</i>")

@router.message(TitusSt.chat, F.text)
async def titus_chat_text(msg: Message):
    await process_titus_message(msg, msg.text)

@router.message(TitusSt.chat, F.voice)
async def titus_chat_voice(msg: Message):
    status = await msg.answer("🎤 Распознаю...")
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
    await process_titus_message(msg, text)

@router.message(TitusSt.chat, F.photo)
async def titus_chat_photo(msg: Message):
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
    await process_titus_message(msg, text, image_b64)
