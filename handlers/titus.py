from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import inline
from utils.ai_client import ask
from utils.voice import download_voice, transcribe_voice
from prompts.all_prompts import TITUS_BASE
from config import MIN_TOKENS
from loader import bot
import asyncio
import base64


router = Router()

MAX_COURSES = 4  # Лимит курсов


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
    
    courses = await db.get_courses(cb.from_user.id)
    active = len([c for c in courses if not c['done']])
    
    await cb.message.edit_text(
        f"📚 <b>Titus — учитель</b>\n\n"
        f"Модель: {cfg['model']}\n"
        f"Активных курсов: {active}/{MAX_COURSES}\n\n"
        f"Выберите действие:",
        reply_markup=inline.titus_kb()
    )


@router.callback_query(F.data == "titus:new")
async def titus_new(cb: CallbackQuery, state: FSMContext):
    # Проверяем лимит курсов
    courses = await db.get_courses(cb.from_user.id)
    active = [c for c in courses if not c['done']]
    
    if len(active) >= MAX_COURSES:
        await cb.answer(
            f"❌ Лимит {MAX_COURSES} курса! Завершите один из текущих.",
            show_alert=True
        )
        return
    
    await cb.message.edit_text(
        "📝 <b>Новый курс</b>\n\n"
        "Напиши название темы, которую хочешь изучить.\n\n"
        "Например:\n"
        "• Python для начинающих\n"
        "• Основы маркетинга\n"
        "• История искусства",
        reply_markup=inline.back_kb("bot:titus")
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
    
    if 'cname' not in d:
        await cb.answer("❌ Сначала введите название курса", show_alert=True)
        return
    
    status = await cb.message.edit_text("🔎 Создаю курс... 0 сек")
    start_time = asyncio.get_event_loop().time()
    
    cid = await db.create_course(cb.from_user.id, d['cname'], steps)
    await state.set_state(TitusSt.learn)
    await state.update_data(bot='titus', cid=cid)
    await db.clear_msgs(cb.from_user.id, 'titus')
    await db.reset_msg_counter(cb.from_user.id, 'titus')
    
    depth = {10: "🚀 Обзорный", 40: "📘 Стандартный", 80: "📖 Углублённый"}
    
    u = await db.get_user(cb.from_user.id)
    cfg = await db.get_bot_cfg('titus')
    sys = TITUS_BASE.format(course=d['cname'], step=1, total=steps)
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": "Начни шаг 1"}]
    
    resp, tok = await ask(msgs, cfg['model'])
    await db.update_tokens(cb.from_user.id, tok)
    await db.add_msg(cb.from_user.id, 'titus', 'assistant', resp)
    
    elapsed = int(asyncio.get_event_loop().time() - start_time)
    
    try:
        await status.delete()
    except:
        pass
    
    await cb.message.answer(
        f"✅ <b>Курс создан!</b>\n\n"
        f"📚 {d['cname']}\n"
        f"📊 Шагов: {steps} ({depth.get(steps, '')})\n\n"
        f"/stop — приостановить обучение"
    )
    await cb.message.answer(f"{resp}\n\n<i>📚 Titus | ⏱ {elapsed} сек</i>")


@router.callback_query(F.data == "titus:list")
async def my_courses(cb: CallbackQuery, state: FSMContext):
    cs = await db.get_courses(cb.from_user.id)
    if not cs:
        await cb.answer("📂 У вас пока нет курсов", show_alert=True)
        return
    
    # Создаем кнопки для каждого курса
    buttons = []
    for c in cs[:10]:
        if c['done']:
            status = "✅"
        else:
            pct = int(c['current'] / c['total'] * 100)
            status = f"{pct}%"
        
        buttons.append([InlineKeyboardButton(
            text=f"{status} {c['name'][:30]}",
            callback_data=f"course:{c['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="bot:titus")])
    
    await cb.message.edit_text(
        f"📂 <b>Ваши курсы ({len(cs)}):</b>\n\n"
        f"Нажмите для продолжения:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("course:"))
async def continue_course(cb: CallbackQuery, state: FSMContext):
    cid = int(cb.data.split(":")[1])
    c = await db.get_course(cid)
    
    if not c:
        await cb.answer("❌ Курс не найден", show_alert=True)
        return
    
    if c['done']:
        await cb.answer("✅ Этот курс уже завершён!", show_alert=True)
        return
    
    await state.set_state(TitusSt.learn)
    await state.update_data(bot='titus', cid=cid)
    
    pct = int(c['current'] / c['total'] * 100)
    await cb.message.edit_text(
        f"📚 <b>Продолжаем: {c['name']}</b>\n\n"
        f"📊 Прогресс: {c['current']}/{c['total']} ({pct}%)\n\n"
        f"Напиши 'продолжить' или задай вопрос по теме.\n\n"
        f"/stop — приостановить"
    )


async def process_titus_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    """Обработка сообщения Titus"""
    u = await db.get_user(msg.from_user.id)
    if not u or u['tokens'] < MIN_TOKENS:
        await msg.answer("❌ Недостаточно токенов.")
        return
    
    d = await state.get_data()
    c = await db.get_course(d['cid'])
    if not c:
        return
    
    start_time = asyncio.get_event_loop().time()
    status_msg = await msg.answer("🔎 Обрабатываю... 0 сек")
    
    async def update_status():
        while True:
            await asyncio.sleep(1)
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            try:
                await status_msg.edit_text(f"📚 Titus проверяет... {elapsed} сек")
            except:
                break
    
    status_task = asyncio.create_task(update_status())
    
    try:
        cfg = await db.get_bot_cfg('titus')
        hist = await db.get_msgs(msg.from_user.id, 'titus')
        cnt = await db.inc_msg_counter(msg.from_user.id, 'titus')
        
        sys = TITUS_BASE.format(course=c['name'], step=c['current'], total=c['total'])
        if cnt >= 20:
            sys += "\n\n⚡ Похвали за прогресс!"
            await db.reset_msg_counter(msg.from_user.id, 'titus')
        
        msgs = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": text}]
        resp, tok = await ask(msgs, cfg['model'], image_b64)
        
        await db.update_tokens(msg.from_user.id, tok)
        await db.add_msg(msg.from_user.id, 'titus', 'user', text)
        await db.add_msg(msg.from_user.id, 'titus', 'assistant', resp)
        
        # Проверяем переход на следующий шаг
        next_step_triggers = ["следующий шаг", f"шаг {c['current']+1}", "правильно", "верно", "молодец", "отлично"]
        if any(t in resp.lower() for t in next_step_triggers):
            new_step = c['current'] + 1
            if new_step > c['total']:
                await db.finish_course(d['cid'])
                await state.clear()
                await msg.answer(
                    f"🎉 <b>Поздравляю!</b>\n\n"
                    f"Курс «{c['name']}» завершён!\n\n"
                    f"Ты прошёл все {c['total']} шагов!",
                    reply_markup=inline.titus_kb()
                )
                return
            else:
                await db.update_step(d['cid'], new_step)
        
    finally:
        status_task.cancel()
        try:
            await status_msg.delete()
        except:
            pass
    
    elapsed = int(asyncio.get_event_loop().time() - start_time)
    pct = int(c['current'] / c['total'] * 100)
    await msg.answer(f"{resp}\n\n<i>📚 Titus | ⏱ {elapsed} сек</i>")


@router.message(TitusSt.learn, F.text)
async def titus_chat_text(msg: Message, state: FSMContext):
    if msg.text.startswith("/"):
        if msg.text == "/stop":
            await state.clear()
            await msg.answer(
                "👋 Обучение приостановлено.\n\n"
                "Курс сохранён — можешь продолжить позже из 📂 Мои курсы.",
                reply_markup=inline.titus_kb()
            )
        return
    
    await process_titus_message(msg, state, msg.text)


@router.message(TitusSt.learn, F.voice)
async def titus_chat_voice(msg: Message, state: FSMContext):
    status = await msg.answer("🎤 Распознаю голос...")
    
    try:
        file_path = await download_voice(bot, msg.voice.file_id)
        if not file_path:
            await status.edit_text("❌ Не удалось скачать голосовое")
            return
        
        text = await transcribe_voice(file_path)
        if not text:
            await status.edit_text("❌ Не удалось распознать речь")
            return
        
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ Ошибка: {e}")
        return
    
    await process_titus_message(msg, state, text)


@router.message(TitusSt.learn, F.photo)
async def titus_chat_photo(msg: Message, state: FSMContext):
    status = await msg.answer("📷 Анализирую фото...")
    
    try:
        photo = msg.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_data = await bot.download_file(file.file_path)
        image_b64 = base64.b64encode(file_data.read()).decode()
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ Ошибка: {e}")
        return
    
    text = msg.caption or "Объясни что на этом изображении и как это связано с темой курса."
    await process_titus_message(msg, state, text, image_b64)
