from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import inline
from utils.ai_client import ask
from prompts.all_prompts import TITUS_BASE
from config import MIN_TOKENS

router = Router()

class TitusSt(StatesGroup):
    name = State()
    learn = State()

@router.callback_query(F.data == "bot:titus")
async def titus_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    cfg = await db.get_bot_cfg('titus')
    if not cfg['enabled']:
        await cb.answer("🔴 Titus временно недоступен", show_alert=True)
        return
    await cb.message.edit_text("📚 <b>Titus — учитель</b>\n\nВыберите действие:", reply_markup=inline.titus_kb())

@router.callback_query(F.data == "titus:new")
async def titus_new(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(
        "📝 <b>Новый курс</b>\n\n"
        "Напиши название темы, которую хочешь изучить.\n\n"
        "Например:\n"
        "• Python для начинающих\n"
        "• Основы маркетинга\n"
        "• История искусства"
    )
    await state.set_state(TitusSt.name)

@router.message(TitusSt.name)
async def course_name(msg: Message, state: FSMContext):
    await state.update_data(cname=msg.text)
    await msg.answer(
        f"📚 Курс: <b>{msg.text}</b>\n\n"
        f"Выбери глубину изучения:",
        reply_markup=inline.titus_steps_kb()
    )

@router.callback_query(F.data.startswith("steps:"))
async def create_course(cb: CallbackQuery, state: FSMContext):
    steps = int(cb.data.split(":")[1])
    d = await state.get_data()
    cid = await db.create_course(cb.from_user.id, d['cname'], steps)
    await state.set_state(TitusSt.learn)
    await state.update_data(bot='titus', cid=cid)
    await db.clear_msgs(cb.from_user.id, 'titus')
    await db.reset_msg_counter(cb.from_user.id, 'titus')
    
    depth = {10: "🚀 Обзорный", 40: "📘 Стандартный", 80: "📖 Углублённый"}
    await cb.message.edit_text(
        f"✅ <b>Курс создан!</b>\n\n"
        f"📚 {d['cname']}\n"
        f"📊 Шагов: {steps} ({depth.get(steps, '')})\n\n"
        f"/stop — приостановить обучение"
    )
    
    u = await db.get_user(cb.from_user.id)
    cfg = await db.get_bot_cfg('titus')
    sys = TITUS_BASE.format(course=d['cname'], step=1, total=steps)
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": "Начни шаг 1"}]
    resp, tok = await ask(msgs, cfg['model'])
    await db.update_tokens(cb.from_user.id, tok)
    await db.add_msg(cb.from_user.id, 'titus', 'assistant', resp)
    await cb.message.answer(resp)

@router.callback_query(F.data == "titus:list")
async def my_courses(cb: CallbackQuery, state: FSMContext):
    cs = await db.get_courses(cb.from_user.id)
    if not cs:
        await cb.answer("📂 У вас пока нет курсов", show_alert=True)
        return
    
    t = "📂 <b>Ваши курсы:</b>\n\n"
    for c in cs[:10]:
        if c['done']:
            t += f"📘 {c['name']} ✅\n   └ Завершён\n\n"
        else:
            pct = int(c['current'] / c['total'] * 100)
            t += f"📘 {c['name']}\n   ├ Прогресс: {c['current']}/{c['total']} ({pct}%)\n\n"
    
    t += "Для продолжения нажмите «Новый курс» и введите то же название."
    await cb.message.edit_text(t, reply_markup=inline.back_kb("bot:titus"))

@router.message(TitusSt.learn)
async def titus_chat(msg: Message, state: FSMContext):
    if msg.text and msg.text.startswith("/"):
        if msg.text == "/stop":
            await state.clear()
            await msg.answer("👋 Обучение приостановлено.\n\nКурс сохранён — можешь продолжить позже.", reply_markup=inline.titus_kb())
        return
    
    u = await db.get_user(msg.from_user.id)
    if not u or u['tokens'] < MIN_TOKENS:
        await msg.answer("❌ Недостаточно токенов.")
        return
    
    d = await state.get_data()
    c = await db.get_course(d['cid'])
    if not c: return
    
    st = await msg.answer("📚 Titus проверяет...")
    
    cfg = await db.get_bot_cfg('titus')
    hist = await db.get_msgs(msg.from_user.id, 'titus')
    cnt = await db.inc_msg_counter(msg.from_user.id, 'titus')
    
    sys = TITUS_BASE.format(course=c['name'], step=c['current'], total=c['total'])
    if cnt >= 20:
        sys += "\n\n⚡ Похвали за прогресс!"
        await db.reset_msg_counter(msg.from_user.id, 'titus')
    
    msgs = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": msg.text}]
    resp, tok = await ask(msgs, cfg['model'])
    
    await db.update_tokens(msg.from_user.id, tok)
    await db.add_msg(msg.from_user.id, 'titus', 'user', msg.text)
    await db.add_msg(msg.from_user.id, 'titus', 'assistant', resp)
    
    if "следующий шаг" in resp.lower() or f"шаг {c['current']+1}" in resp.lower() or "правильно" in resp.lower():
        await db.update_step(d['cid'], c['current'] + 1)
    
    try: await st.delete()
    except: pass
    await msg.answer(resp)
