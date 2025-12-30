from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import inline
from utils.ai_client import ask
from prompts.all_prompts import SILAS_BASE, SILAS_GOOD, SILAS_TIRED, SILAS_PAIN
from config import MIN_TOKENS
from datetime import datetime

router = Router()

class SilasSt(StatesGroup):
    session = State()
    custom = State()

MOODS = {'good': SILAS_GOOD, 'tired': SILAS_TIRED, 'pain': SILAS_PAIN}

@router.callback_query(F.data == "bot:silas")
async def silas_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    cfg = await db.get_bot_cfg('silas')
    if not cfg['enabled']:
        await cb.answer("🔴 Silas временно недоступен", show_alert=True)
        return
    await cb.message.edit_text("🧠 <b>Silas — психолог</b>\n\nВыберите действие:", reply_markup=inline.silas_kb())

@router.callback_query(F.data == "silas:diary")
async def silas_diary(cb: CallbackQuery):
    await cb.message.edit_text("📔 <b>Дневник настроения</b>\n\nКак ты себя сейчас чувствуешь?", reply_markup=inline.silas_diary_kb())

@router.callback_query(F.data.startswith("mood:"))
async def set_mood(cb: CallbackQuery, state: FSMContext):
    m = cb.data.split(":")[1]
    if m == "custom":
        await cb.message.edit_text("✏️ <b>Своё состояние</b>\n\nНапиши 1-2 слова.\nНапример: «тревожно» или «странно пусто»")
        await state.set_state(SilasSt.custom)
        return
    await db.set_mood(cb.from_user.id, m)
    mood_text = {'good': '😊 Хорошо/Спокойно', 'tired': '😔 Устал/Пусто', 'pain': '😰 Больно/Страшно'}
    await cb.answer(f"✅ Сохранено: {mood_text.get(m)}")
    await cb.message.edit_text("🧠 <b>Silas — психолог</b>\n\nВыберите действие:", reply_markup=inline.silas_kb())

@router.message(SilasSt.custom)
async def custom_mood(msg: Message, state: FSMContext):
    words = len(msg.text.split())
    if words > 2:
        await msg.answer("❌ Пожалуйста, напиши только 1-2 слова. Попробуй ещё раз.")
        return
    await db.set_mood(msg.from_user.id, 'custom', msg.text)
    await state.clear()
    await msg.answer(f"✅ Состояние сохранено: <b>{msg.text}</b>", reply_markup=inline.silas_kb())

@router.callback_query(F.data == "silas:stats")
async def silas_stats(cb: CallbackQuery):
    s = await db.get_mood_stats(cb.from_user.id)
    total = s['good'] + s['tired'] + s['pain']
    await cb.message.edit_text(
        f"📊 <b>Статистика за месяц</b>\n\n"
        f"😊 Хорошо/Спокойно: {s['good']} раз\n"
        f"😔 Устал/Пусто: {s['tired']} раз\n"
        f"😰 Больно/Страшно: {s['pain']} раз\n\n"
        f"Всего записей: {total}",
        reply_markup=inline.back_kb("silas:diary")
    )

@router.callback_query(F.data == "silas:session")
async def silas_session(cb: CallbackQuery):
    await cb.message.edit_text("⏱ <b>Выберите длительность сеанса:</b>", reply_markup=inline.silas_dur_kb())

@router.callback_query(F.data.startswith("ses:"))
async def start_ses(cb: CallbackQuery, state: FSMContext):
    dur = int(cb.data.split(":")[1])
    sid = await db.start_session(cb.from_user.id, dur)
    await state.set_state(SilasSt.session)
    await state.update_data(bot='silas', sid=sid, dur=dur, start=datetime.now().timestamp())
    await db.clear_msgs(cb.from_user.id, 'silas')
    await db.reset_msg_counter(cb.from_user.id, 'silas')
    await cb.message.edit_text(
        f"🎯 <b>Сеанс начат</b>\n\n"
        f"⏱ Длительность: {dur} мин\n\n"
        f"Расскажи, что тебя беспокоит.\n\n"
        f"/stop — завершить сеанс"
    )

@router.message(SilasSt.session)
async def silas_chat(msg: Message, state: FSMContext):
    if msg.text and msg.text.startswith("/"):
        if msg.text == "/stop":
            d = await state.get_data()
            await db.end_session(d['sid'])
            await state.clear()
            await msg.answer("👋 Сеанс завершён.\n\nСпасибо за доверие. Береги себя.", reply_markup=inline.silas_kb())
        return
    
    u = await db.get_user(msg.from_user.id)
    if not u or u['tokens'] < MIN_TOKENS:
        await msg.answer("❌ Недостаточно токенов.")
        return
    
    d = await state.get_data()
    el = int((datetime.now().timestamp() - d['start']) / 60)
    rem = d['dur'] - el
    
    if rem <= 0:
        await db.end_session(d['sid'])
        await state.clear()
        await msg.answer("⏱ Время сеанса вышло.\n\nСпасибо за работу. До встречи!", reply_markup=inline.silas_kb())
        return
    
    st = await msg.answer("🧠 Silas думает...")
    
    cfg = await db.get_bot_cfg('silas')
    s = await db.get_user_bot(msg.from_user.id, 'silas')
    mood = MOODS.get(s['mood'], s.get('custom_mood') or 'не указано')
    hist = await db.get_msgs(msg.from_user.id, 'silas')
    cnt = await db.inc_msg_counter(msg.from_user.id, 'silas')
    
    sys = SILAS_BASE.format(mood=mood, duration=d['dur'], elapsed=el, remaining=rem)
    if rem <= 5:
        sys += "\n\n⚠️ Осталось мало времени — начинай завершение сеанса."
    if cnt >= 20:
        sys += "\n\n⚡ Пора связать с чем-то из прошлых бесед."
        await db.reset_msg_counter(msg.from_user.id, 'silas')
    
    msgs = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": msg.text}]
    resp, tok = await ask(msgs, cfg['model'])
    
    await db.update_tokens(msg.from_user.id, tok)
    await db.add_msg(msg.from_user.id, 'silas', 'user', msg.text)
    await db.add_msg(msg.from_user.id, 'silas', 'assistant', resp)
    
    try: await st.delete()
    except: pass
    await msg.answer(resp)
    
    if rem <= 5 and rem > 0:
        await msg.answer(f"⏰ Осталось {rem} мин")
