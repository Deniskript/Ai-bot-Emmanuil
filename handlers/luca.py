from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import inline
from utils.ai_client import ask
from prompts.all_prompts import LUCA_BASE, LUCA_SOUL, LUCA_SER, LUCA_HUM
from config import MIN_TOKENS

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
    await cb.message.edit_text(f"🧑 <b>Luca — друг</b>\n\nХарактер: {s['character']}", reply_markup=inline.luca_kb())

@router.callback_query(F.data == "luca:char")
async def luca_char(cb: CallbackQuery):
    await cb.message.edit_text("🎭 Выбери характер Luca:", reply_markup=inline.luca_char_kb())

@router.callback_query(F.data.startswith("char:"))
async def set_char(cb: CallbackQuery):
    c = cb.data.split(":")[1]
    await db.set_char(cb.from_user.id, c)
    await cb.answer(f"✅ Характер: {c}")
    s = await db.get_user_bot(cb.from_user.id, 'luca')
    await cb.message.edit_text(f"🧑 <b>Luca — друг</b>\n\nХарактер: {s['character']}", reply_markup=inline.luca_kb())

@router.callback_query(F.data == "luca:start")
async def luca_start(cb: CallbackQuery, state: FSMContext):
    await db.clear_msgs(cb.from_user.id, 'luca')
    await db.reset_msg_counter(cb.from_user.id, 'luca')
    await state.set_state(LucaSt.chat)
    await state.update_data(bot='luca')
    await cb.message.edit_text("💬 Диалог с Luca начат!\n\nПиши что угодно.\n\n/stop — завершить")

@router.message(LucaSt.chat)
async def luca_chat(msg: Message, state: FSMContext):
    if msg.text and msg.text.startswith("/"):
        if msg.text == "/stop":
            await state.clear()
            await msg.answer("👋 Диалог завершён!", reply_markup=inline.bots_kb())
        return
    
    u = await db.get_user(msg.from_user.id)
    if not u or u['tokens'] < MIN_TOKENS:
        await msg.answer("❌ Недостаточно токенов. Пополните баланс.")
        return
    
    st = await msg.answer("✍️ Luca печатает...")
    
    cfg = await db.get_bot_cfg('luca')
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char = CHARS.get(s['character'], LUCA_SOUL)
    mem = await db.get_memory(msg.from_user.id, 'luca')
    hist = await db.get_msgs(msg.from_user.id, 'luca')
    cnt = await db.inc_msg_counter(msg.from_user.id, 'luca')
    
    sys = LUCA_BASE + "\n" + char
    if mem:
        sys += f"\n\nПАМЯТЬ О СОБЕСЕДНИКЕ: {', '.join(mem[-5:])}"
    if cnt >= 20:
        sys += "\n\n⚡ Пора упомянуть что-то из памяти!"
        await db.reset_msg_counter(msg.from_user.id, 'luca')
    
    msgs = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": msg.text}]
    resp, tok = await ask(msgs, cfg['model'])
    
    await db.update_tokens(msg.from_user.id, tok)
    await db.add_msg(msg.from_user.id, 'luca', 'user', msg.text)
    await db.add_msg(msg.from_user.id, 'luca', 'assistant', resp)
    
    try: await st.delete()
    except: pass
    await msg.answer(resp)
