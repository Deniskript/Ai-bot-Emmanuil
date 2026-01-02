from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import reply, inline
from utils.ai_client import ask
from utils.memory import update_memory, build_memory_context
from utils.voice import download_voice, transcribe_voice
from utils.antiflood import ai_flood
from utils.telegraph import create_telegraph_page, make_preview
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


CHARS = {'support': LUCA_SOUL, 'motivation': LUCA_SER, 'solution': LUCA_HUM}
CHAR_NAMES = {'support': '🙏 Поддержка', 'motivation': '🔥 Мотивация', 'solution': '⚡️ Решение'}

active_requests = {}
last_messages = {}  # {user_id: {"text": str, "char": str}}


@router.message(F.text == "💭 Диалог")
async def luca_enter(msg: Message, state: FSMContext):
    cfg = await db.get_bot_cfg('luca')
    if not cfg['enabled']:
        await msg.answer("🔴 Диалог временно недоступен")
        return
    await state.set_state(LucaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_name = CHAR_NAMES.get(s['character'], '🙏 Поддержка')
    await msg.answer(
        f"💭 <b>Диалог — твой личный помощник</b>\n\n"
        f"🌓 Характер: {char_name}\n"
        f"✨ Готов выслушать и помочь",
        reply_markup=reply.dialog_kb()
    )


@router.message(LucaSt.menu, F.text == "💬 Начать диалог")
async def luca_start_chat(msg: Message, state: FSMContext):
    await db.clear_msgs(msg.from_user.id, 'luca')
    await db.reset_msg_counter(msg.from_user.id, 'luca')
    await state.set_state(LucaSt.chat)
    await msg.answer(
        "💬 <b>Диалог начат!</b>\n\nПиши что угодно — я рядом:",
        reply_markup=reply.dialog_chat_kb()
    )


@router.message(LucaSt.menu, F.text == "🌓 Характер")
async def luca_char_menu(msg: Message, state: FSMContext):
    await state.set_state(LucaSt.char)
    await msg.answer("🌓 <b>Выбери стиль общения:</b>", reply_markup=reply.dialog_char_kb())


@router.message(LucaSt.menu, F.text == "🗑 Очистить")
async def luca_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'luca')
    await msg.answer("🗑 История очищена!")


@router.message(LucaSt.menu, F.text == "❓ Помощь")
async def luca_help(msg: Message):
    text = await db.get_text('help_dialog')
    if not text:
        text = "💭 <b>Диалог</b> — твой личный AI-помощник для любых разговоров"
    await msg.answer(text)


@router.message(LucaSt.menu, F.text == "◀️ Назад")
async def luca_back(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("✨ Выберите помощника:", reply_markup=reply.bots_menu_kb())


@router.message(LucaSt.char, F.text == "🙏 Поддержка")
async def char_support(msg: Message, state: FSMContext):
    await db.set_char(msg.from_user.id, 'support')
    await state.set_state(LucaSt.menu)
    await msg.answer("✅ Характер: 🙏 Поддержка\n\n<i>Мягкий, понимающий, заботливый</i>", reply_markup=reply.dialog_kb())


@router.message(LucaSt.char, F.text == "🔥 Мотивация")
async def char_motivation(msg: Message, state: FSMContext):
    await db.set_char(msg.from_user.id, 'motivation')
    await state.set_state(LucaSt.menu)
    await msg.answer("✅ Характер: 🔥 Мотивация\n\n<i>Энергичный, вдохновляющий, толкающий вперёд</i>", reply_markup=reply.dialog_kb())


@router.message(LucaSt.char, F.text == "⚡️ Решение")
async def char_solution(msg: Message, state: FSMContext):
    await db.set_char(msg.from_user.id, 'solution')
    await state.set_state(LucaSt.menu)
    await msg.answer("✅ Характер: ⚡️ Решение\n\n<i>Конкретный, практичный, по делу</i>", reply_markup=reply.dialog_kb())


@router.message(LucaSt.char, F.text == "◀️ Назад к Диалогу")
async def char_back(msg: Message, state: FSMContext):
    await state.set_state(LucaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_name = CHAR_NAMES.get(s['character'], '🙏 Поддержка')
    await msg.answer(
        f"💭 <b>Диалог</b>\n\n🌓 Характер: {char_name}",
        reply_markup=reply.dialog_kb()
    )


@router.message(LucaSt.chat, F.text == "🛑 Завершить")
async def luca_stop(msg: Message, state: FSMContext):
    await state.set_state(LucaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_name = CHAR_NAMES.get(s['character'], '🙏 Поддержка')
    await msg.answer(
        f"👋 Диалог завершён!\n\n💭 <b>Диалог</b>\n🌓 Характер: {char_name}",
        reply_markup=reply.dialog_kb()
    )


@router.message(LucaSt.chat, F.text == "🗑 Очистить")
async def luca_chat_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'luca')
    await msg.answer("🗑 История очищена! Продолжай:")


@router.message(LucaSt.chat, F.text == "⌛️ Отменить запрос")
async def luca_cancel(msg: Message):
    user_id = msg.from_user.id
    if user_id in active_requests:
        active_requests[user_id]['cancelled'] = True
        await msg.answer("❌ Запрос отменён", reply_markup=reply.dialog_chat_kb())
    else:
        await msg.answer("Нет активного запроса", reply_markup=reply.dialog_chat_kb())


# === TELEGRAPH CALLBACK ===
@router.callback_query(F.data == "luca:tg")
async def luca_telegraph(cb: CallbackQuery):
    user_id = cb.from_user.id
    
    if user_id not in last_messages:
        await cb.answer("❌ Нет текста", show_alert=True)
        return
    
    await cb.answer("📖 Публикую на Telegraph...")
    
    data = last_messages[user_id]
    text = data['text']
    char = data.get('char', 'Диалог')
    
    url = await create_telegraph_page(f"💭 Диалог — {char}", text)
    
    if url:
        await cb.message.answer(
            "📖 <b>Полный текст опубликован</b>",
            reply_markup=inline.titus_telegraph_kb(url)
        )
    else:
        await cb.message.answer("❌ Не удалось опубликовать")


async def process_luca_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    allowed, error_msg = await ai_flood.check(msg.from_user.id)
    if not allowed:
        await msg.answer(error_msg)
        return
    
    u = await db.get_user(msg.from_user.id)
    if not u or u['tokens'] < MIN_TOKENS:
        await msg.answer("❌ Недостаточно токенов!")
        return
    
    user_id = msg.from_user.id
    request_state = {'cancelled': False}
    active_requests[user_id] = request_state
    
    status_msg = await msg.answer("✍️ Печатаю...", reply_markup=reply.cancel_kb())
    
    resp = None
    char_name = ""
    try:
        if request_state['cancelled']:
            return
            
        cfg = await db.get_bot_cfg('luca')
        s = await db.get_user_bot(msg.from_user.id, 'luca')
        char = CHARS.get(s['character'], LUCA_SOUL)
        char_name = CHAR_NAMES.get(s['character'], 'Поддержка')
        mem = await db.get_memory(msg.from_user.id, 'luca')
        hist = await db.get_msgs(msg.from_user.id, 'luca')
        cnt = await db.inc_msg_counter(msg.from_user.id, 'luca')
        sys = LUCA_BASE + "\n" + char + build_memory_context(mem)
        if cnt >= 20:
            sys += "\n\n⚡ Упомяни что-то из памяти!"
            await db.reset_msg_counter(msg.from_user.id, 'luca')
        msgs = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": text}]
        
        if request_state['cancelled']:
            return
            
        resp, tok = await ask(msgs, cfg['model'], image_b64)
        
        if request_state['cancelled']:
            return
            
        await db.update_tokens(msg.from_user.id, tok)
        await db.add_msg(msg.from_user.id, 'luca', 'user', text)
        await db.add_msg(msg.from_user.id, 'luca', 'assistant', resp)
        asyncio.create_task(update_memory(msg.from_user.id, 'luca', text, resp))
        
        # Сохраняем для Telegraph
        last_messages[user_id] = {"text": resp, "char": char_name}
        
    finally:
        try:
            await status_msg.delete()
        except:
            pass
        active_requests.pop(user_id, None)
    
    if resp:
        print(f"DEBUG: len={len(resp)}, has_tg={len(resp) >= 3000}")
        has_tg = len(resp) >= 3000
        
        if has_tg:
            preview = make_preview(resp, 800)
            await msg.answer(
                f"{preview}\n\n<i>💭 Диалог • {char_name}</i>",
                reply_markup=inline.luca_msg_kb(has_telegraph=True)
            )
        else:
            await msg.answer(f"{resp}\n\n<i>💭 Диалог • {char_name}</i>", reply_markup=reply.dialog_chat_kb())


@router.message(LucaSt.chat, F.text)
async def luca_chat_text(msg: Message, state: FSMContext):
    await process_luca_message(msg, state, msg.text)


@router.message(LucaSt.chat, F.voice)
async def luca_chat_voice(msg: Message, state: FSMContext):
    st = await msg.answer("🎧 Слушаю...")
    try:
        fp = await download_voice(bot, msg.voice.file_id)
        text = await transcribe_voice(fp)
        if not text:
            await st.edit_text("❌ Не распознано")
            return
        await st.delete()
    except Exception as e:
        await st.edit_text(f"❌ {e}")
        return
    await process_luca_message(msg, state, text)


@router.message(LucaSt.chat, F.photo)
async def luca_chat_photo(msg: Message, state: FSMContext):
    st = await msg.answer("🔎 Смотрю фото...")
    try:
        photo = msg.photo[-1]
        file = await bot.get_file(photo.file_id)
        data = await bot.download_file(file.file_path)
        b64 = base64.b64encode(data.read()).decode()
        await st.delete()
    except Exception as e:
        await st.edit_text(f"❌ {e}")
        return
    await process_luca_message(msg, state, msg.caption or "Что на изображении?", b64)
