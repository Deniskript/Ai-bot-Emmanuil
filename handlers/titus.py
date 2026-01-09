import re
import time
import json
import base64
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import reply, inline
from utils.openrouter import ask, ask_stream
from utils.tokens import calculate_tokens
from utils.titus_memory import save_step_progress, build_smart_context
from utils.voice import download_voice, transcribe_voice
from utils.antiflood import ai_flood
from utils.telegraph import create_telegraph_page, make_preview, clean_html_for_telegram
from prompts.titus_prompt import TITUS_BASE
from config import MIN_TOKENS
from loader import bot


last_messages = {}


def build_course_context(course_mem, current_step=1, student_name=None):
    return build_smart_context(course_mem, current_step, student_name)


router = Router()


class TitusSt(StatesGroup):
    menu = State()
    chat = State()
    new_course = State()
    select_steps = State()
    courses_menu = State()
    continue_course = State()
    delete_course = State()


active_requests = {}


@router.message(F.text == "📓 Обучение")
async def titus_enter(msg: Message, state: FSMContext):
    cfg = await db.get_bot_cfg('titus')
    if not cfg['enabled']:
        await msg.answer("🔴 Обучение временно недоступно")
        return
    await state.set_state(TitusSt.menu)
    await msg.answer(
        "📓 <b>Обучение будущего</b>\n\n"
        "✨ Объясняет как лучший профессор\n"
        "🧠 Помнит твои сложности\n"
        "🔄 Адаптируется под тебя\n"
        "✅ Проверяет понимание\n\n"
        "📖 Перед началом загляни в раздел «Помощь»",
        reply_markup=reply.study_kb()
    )


@router.message(TitusSt.menu, F.text == "📝 Новый курс")
async def titus_new_course(msg: Message, state: FSMContext):
    courses = await db.get_courses(msg.from_user.id)
    active = [c for c in courses if not c['done']]
    if len(active) >= 5:
        await msg.answer("❌ Максимум 5 курсов!\n\nУдалите старый в «📂 Ваши курсы»")
        return
    await state.set_state(TitusSt.new_course)
    await msg.answer("📝 <b>Напиши тему курса:</b>\n\n<i>Например: Python для начинающих</i>", reply_markup=reply.back_kb())


@router.message(TitusSt.new_course, F.text == "◀️ Назад")
async def new_course_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.menu)
    await msg.answer("📓 <b>Обучение</b>\n\n✨ Выбери действие:", reply_markup=reply.study_kb())


@router.message(TitusSt.new_course, F.text)
async def titus_course_name(msg: Message, state: FSMContext):
    await state.update_data(cname=msg.text)
    await state.set_state(TitusSt.select_steps)
    await msg.answer(f"📓 <b>{msg.text}</b>\n\n🎯 Выбери глубину изучения:", reply_markup=reply.study_steps_kb())


@router.message(TitusSt.select_steps, F.text == "◀️ Назад")
async def steps_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.new_course)
    await msg.answer("📝 <b>Напиши тему курса:</b>", reply_markup=reply.back_kb())


@router.message(TitusSt.select_steps, F.text.in_({"🚀 10 шагов", "📘 40 шагов", "📖 80 шагов"}))
async def create_course(msg: Message, state: FSMContext):
    remaining = await db.get_available_tokens(msg.from_user.id)
    if remaining < MIN_TOKENS:
        await msg.answer("❌ Токены закончились!\n\n💎 Докупите в разделе 💠 Подписка", reply_markup=reply.main_kb())
        return
    
    model = await db.get_user_model(msg.from_user.id)
    
    steps_map = {"🚀 10 шагов": 10, "📘 40 шагов": 40, "📖 80 шагов": 80}
    steps = steps_map[msg.text]
    data = await state.get_data()
    cname = data['cname']
    cid = await db.create_course(msg.from_user.id, cname, steps)
    await state.set_state(TitusSt.chat)
    await state.update_data(cid=cid, cname=cname, current_step=1, total_steps=steps)
    await db.clear_msgs(msg.from_user.id, 'titus')
    
    await msg.answer(f"✅ Курс создан!", reply_markup=reply.study_chat_kb())
    
    sys = TITUS_BASE + f"\n\nКУРС: {cname}\nШАГ: 1 из {steps}\n\n⚠️ НЕ представляйся! Сразу начни с 📌 Тема:"
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": "Начни шаг 1"}]
    
    status = await msg.answer("⏳ Обрабатываю. Пожалуйста подождите...")
    timer_running = True
    
    async def update_timer():
        sec = 0
        while timer_running:
            await asyncio.sleep(1)
            if not timer_running:
                break
            sec += 1
            try:
                await status.edit_text(f"✍️ Печатаю... ({sec} сек)")
            except:
                pass
    
    timer_task = asyncio.create_task(update_timer())
    resp, tok = await ask(msgs, model)
    timer_running = False
    timer_task.cancel()
    await status.delete()
    
    resp_clean = resp.replace("---NEXT---", "").strip()
    resp_clean = clean_html_for_telegram(resp_clean)
    
    await db.use_tokens_smart(msg.from_user.id, tok)
    await db.increment_requests(msg.from_user.id)
    await db.add_msg(msg.from_user.id, 'titus', 'assistant', resp_clean)
    
    last_messages[msg.from_user.id] = {"text": resp_clean, "course": cname, "step": 1}
    
    if len(resp_clean) >= 3000:
        preview = make_preview(resp_clean, 800)
        text_to_send = f"{preview}\n\n<i>📖 Полный текст — нажмите Telegraph</i>"
    else:
        text_to_send = resp_clean
    
    await msg.answer(
        f"{text_to_send}\n\n<i>📓 Обучение • Шаг 1/{steps}</i>",
        reply_markup=inline.titus_msg_kb(msg.from_user.id, has_telegraph=True)
    )


@router.message(TitusSt.menu, F.text == "📂 Ваши курсы")
async def my_courses(msg: Message, state: FSMContext):
    courses = await db.get_courses(msg.from_user.id)
    if not courses:
        await msg.answer("📂 Курсов пока нет\n\nСоздайте первый в «📝 Новый курс»")
        return
    await state.set_state(TitusSt.courses_menu)
    await state.update_data(courses=[dict(c) for c in courses])
    await msg.answer("📂 <b>Ваши курсы</b>\n\nВыберите действие:", reply_markup=reply.courses_action_kb())


@router.message(TitusSt.courses_menu, F.text == "◀️ Назад")
async def courses_menu_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.menu)
    await msg.answer("📓 <b>Обучение</b>", reply_markup=reply.study_kb())


@router.message(TitusSt.courses_menu, F.text == "▶️ Продолжить курс")
async def continue_menu(msg: Message, state: FSMContext):
    data = await state.get_data()
    courses = [c for c in data.get('courses', []) if not c['done']]
    if not courses:
        await msg.answer("📂 Нет активных курсов")
        return
    await state.set_state(TitusSt.continue_course)
    await state.update_data(active_courses=courses)
    await msg.answer("▶️ <b>Выберите курс:</b>", reply_markup=reply.courses_list_kb(courses, show_progress=True))


@router.message(TitusSt.courses_menu, F.text == "🗑 Удалить курс")
async def delete_menu(msg: Message, state: FSMContext):
    data = await state.get_data()
    courses = data.get('courses', [])
    if not courses:
        await msg.answer("📂 Нет курсов")
        return
    await state.set_state(TitusSt.delete_course)
    await state.update_data(del_courses=courses)
    await msg.answer("🗑 <b>Выберите курс для удаления:</b>", reply_markup=reply.courses_list_kb(courses, show_progress=True))


@router.message(TitusSt.continue_course, F.text == "◀️ Назад")
async def continue_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.courses_menu)
    await msg.answer("📂 <b>Ваши курсы</b>", reply_markup=reply.courses_action_kb())


@router.message(TitusSt.continue_course, F.text)
async def continue_select(msg: Message, state: FSMContext):
    data = await state.get_data()
    courses = data.get('active_courses', [])
    try:
        num = int(msg.text.split(".")[0]) - 1
        if 0 <= num < len(courses):
            course = courses[num]
            cid = course['id']
            current_step = course['current']
            total_steps = course['total']
            cname = course['name']
            
            await state.set_state(TitusSt.chat)
            await state.update_data(cid=cid, cname=cname, current_step=current_step, total_steps=total_steps)
            await db.clear_msgs(msg.from_user.id, 'titus')
            
            user = await db.get_user(msg.from_user.id)
            name = user.get('first_name', 'друг') if user else 'друг'
            
            course_mem = await db.get_course_memory(cid)
            difficult_topics = []
            if course_mem and course_mem.get('weak_topics'):
                weak = course_mem['weak_topics']
                if isinstance(weak, str):
                    try:
                        weak = json.loads(weak)
                    except:
                        weak = []
                difficult_topics = weak[:3] if isinstance(weak, list) else []
            
            greeting = f"👋 С возвращением, {name}!\n\n"
            greeting += f"📓 <b>{cname}</b>\n"
            
            if difficult_topics:
                greeting += "\n⚠️ <b>В прошлый раз были сложности с:</b>\n"
                for topic in difficult_topics:
                    if isinstance(topic, dict):
                        greeting += f"• {topic.get('topic', topic)}\n"
                    else:
                        greeting += f"• {topic}\n"
            
            greeting += f"\n📍 Текущий прогресс: шаг {current_step} из {total_steps}"
            
            await msg.answer(greeting, reply_markup=reply.study_chat_kb())
            await msg.answer(
                "Что выберешь?",
                reply_markup=inline.course_continue_kb(cid, current_step, bool(difficult_topics))
            )
            return
    except Exception as e:
        print(f"Error in continue_select: {e}")
    await msg.answer("❌ Выберите курс из списка")


@router.message(TitusSt.delete_course, F.text == "◀️ Назад")
async def delete_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.courses_menu)
    await msg.answer("📂 <b>Ваши курсы</b>", reply_markup=reply.courses_action_kb())


@router.message(TitusSt.delete_course, F.text)
async def delete_select(msg: Message, state: FSMContext):
    data = await state.get_data()
    courses = data.get('del_courses', [])
    match = re.match(r'^(\d+)', msg.text.strip())
    if match:
        num = int(match.group(1)) - 1
        if 0 <= num < len(courses):
            course = courses[num]
            await db.delete_course(course['id'])
            await msg.answer(f"🗑 Курс «{course['name']}» удалён!")
            await state.set_state(TitusSt.menu)
            await msg.answer("📓 <b>Обучение</b>", reply_markup=reply.study_kb())
            return
    await msg.answer("❌ Выберите курс из списка")


@router.message(TitusSt.menu, F.text == "🔍 Помощь")
async def titus_help(msg: Message):
    text = await db.get_text('help_study')
    if not text:
        text = "📓 <b>Обучение — умный репетитор</b>\n\n▸ Создаёт курсы по любой теме\n▸ Проверяет понимание"
    await msg.answer(text)


@router.message(TitusSt.menu, F.text == "◀️ Назад")
async def titus_back(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("✨ Выберите помощника:", reply_markup=reply.bots_menu_kb())


@router.message(TitusSt.chat, F.text == "🛑 Завершить")
async def titus_stop(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.menu)
    await msg.answer("👋 <b>Курс сохранён!</b>\n\nПродолжить можно в «📂 Ваши курсы»", reply_markup=reply.study_kb())


@router.message(TitusSt.chat, F.text == "🗑 Очистить")
async def titus_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'titus')
    await msg.answer("🗑 История очищена", reply_markup=reply.study_chat_kb())


@router.message(TitusSt.chat, F.text == "⌛️ Отменить запрос")
async def titus_cancel(msg: Message):
    user_id = msg.from_user.id
    if user_id in active_requests and isinstance(active_requests[user_id], dict):
        active_requests[user_id]['cancelled'] = True
        try:
            if active_requests[user_id].get('kb_msg'):
                await active_requests[user_id]['kb_msg'].delete()
        except:
            pass
        try:
            if active_requests[user_id].get('status_msg'):
                await active_requests[user_id]['status_msg'].delete()
        except:
            pass
        try:
            await msg.delete()
        except:
            pass
        await msg.answer("❌ Запрос отменён", reply_markup=reply.study_chat_kb())
    else:
        await msg.answer("Нет активного запроса", reply_markup=reply.study_chat_kb())


@router.callback_query(F.data.startswith("titus:summary:"))
async def titus_make_summary(cb: CallbackQuery):
    user_id = cb.from_user.id
    if user_id not in last_messages:
        await cb.answer("❌ Нет текста для конспекта", show_alert=True)
        return
    
    remaining = await db.get_available_tokens(user_id)
    if remaining < MIN_TOKENS:
        await cb.answer("❌ Недостаточно токенов!", show_alert=True)
        return
    
    await cb.answer("📝 Создаю конспект...")
    
    model = await db.get_user_model(user_id)
    data = last_messages[user_id]
    
    summary_prompt = f"""Сделай краткий конспект из этого текста:

{data['text']}

Требования: структурированно, по пунктам, только важное."""

    try:
        resp, tok = await ask([{"role": "user", "content": summary_prompt}], model)
        resp = clean_html_for_telegram(resp)
        await db.use_tokens_smart(user_id, tok)
        await db.increment_requests(user_id)
        await cb.message.answer(
            f"📝 <b>Конспект | {data.get('course', 'Курс')} | Шаг {data.get('step', 1)}</b>\n\n{resp}",
            reply_markup=reply.study_chat_kb()
        )
    except Exception as e:
        await cb.message.answer(f"❌ Ошибка: {e}", reply_markup=reply.study_chat_kb())


@router.callback_query(F.data.startswith("titus:tg:"))
async def titus_telegraph(cb: CallbackQuery):
    user_id = cb.from_user.id
    if user_id not in last_messages:
        await cb.answer("❌ Нет текста", show_alert=True)
        return
    
    await cb.answer("📖 Публикую на Telegraph...")
    data = last_messages[user_id]
    title = f"{data.get('course', 'Урок')} — Шаг {data.get('step', 1)}"
    url = await create_telegraph_page(title, data['text'])
    
    if url:
        await cb.message.answer(
            f"📖 <b>Полный текст опубликован</b>\n\n{title}",
            reply_markup=inline.titus_telegraph_kb(url)
        )
    else:
        await cb.message.answer("❌ Не удалось опубликовать на Telegraph", reply_markup=reply.study_chat_kb())


def check_step_transition(resp: str) -> bool:
    return "---NEXT---" in resp


async def process_titus_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    allowed, error_msg = await ai_flood.check(msg.from_user.id)
    if not allowed:
        await msg.answer(error_msg, reply_markup=reply.study_chat_kb())
        return
    
    remaining = await db.get_available_tokens(msg.from_user.id)
    if remaining < MIN_TOKENS:
        await msg.answer("❌ Токены закончились!\n\n💎 Докупите в разделе 💠 Подписка", reply_markup=reply.main_kb())
        return
    
    model = await db.get_user_model(msg.from_user.id)
    
    data = await state.get_data()
    cid = data.get('cid')
    cname = data.get('cname', 'Курс')
    user_id = msg.from_user.id
    request_state = {'cancelled': False, 'kb_msg': None, 'status_msg': None}
    active_requests[user_id] = request_state
    
    status_msg = await msg.answer("⏳ Обрабатываю. Пожалуйста подождите...")
    request_state['status_msg'] = status_msg
    
    current_step = data.get('current_step', 1)
    total_steps = data.get('total_steps', 10)
    resp = None
    tok = 0
    timer_running = True
    
    async def update_timer():
        sec = 0
        while timer_running:
            await asyncio.sleep(1)
            if not timer_running or request_state['cancelled']:
                break
            sec += 1
            try:
                await status_msg.edit_text(f"✍️ Печатаю... ({sec})")
            except:
                pass
    
    timer_task = asyncio.create_task(update_timer())
    
    try:
        if request_state['cancelled']:
            return
            
        hist = await db.get_msgs(msg.from_user.id, 'titus')
        course_info = ""
        
        if cid:
            course = await db.get_course(cid)
            if course:
                current_step = course['current']
                total_steps = course['total']
                await state.update_data(current_step=current_step, total_steps=total_steps)
                
                user = await db.get_user(msg.from_user.id)
                student_name = user.get('first_name') if user else None
                
                course_mem = await db.get_course_memory(cid)
                memory_context = build_course_context(course_mem, current_step, student_name)
                course_info = f"\n\nКУРС: {course['name']}\nШАГ: {current_step} из {total_steps}\nПРОГРЕСС: {int(current_step/total_steps*100)}%"
                if memory_context:
                    course_info += f"\n\n{memory_context}"
        
        sys = TITUS_BASE + course_info
        msgs_to_send = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": text}]
        
        if request_state['cancelled']:
            return
        
        if image_b64:
            resp, tok = await ask(msgs_to_send, model, image_b64)
        else:
            # Стриминг для текста
            full_response = ""
            last_update = time.time()
            typing_seconds = 0
            
            async for chunk in ask_stream(msgs_to_send, model):
                if request_state['cancelled']:
                    return
                if chunk:
                    full_response += chunk
                
                now = time.time()
                if now - last_update >= 1.0:
                    typing_seconds += 1
                    if typing_seconds <= 3:
                        try:
                            await status_msg.edit_text(f"✍️ Печатаю... ({typing_seconds})")
                        except:
                            pass
                    elif len(full_response) > 50:
                        display = full_response[:4000] + " ▌" if len(full_response) > 4000 else full_response + " ▌"
                        try:
                            await status_msg.edit_text(display)
                        except:
                            pass
                    last_update = now
            
            resp = full_response.strip()
            tok = calculate_tokens(msgs_to_send, resp)
        
        if request_state['cancelled']:
            return
        
        should_advance = check_step_transition(resp)
        resp_clean = resp.replace("---NEXT---", "").strip()
        resp_clean = clean_html_for_telegram(resp_clean)
        
        await db.use_tokens_smart(msg.from_user.id, tok)
        await db.increment_requests(msg.from_user.id)
        await db.add_msg(msg.from_user.id, 'titus', 'user', text)
        await db.add_msg(msg.from_user.id, 'titus', 'assistant', resp_clean)
        
        if cid and should_advance:
            course = await db.get_course(cid)
            if course:
                last_bot_msg = hist[-1]['content'] if hist and hist[-1]['role'] == 'assistant' else ""
                asyncio.create_task(save_step_progress(cid, current_step, last_bot_msg, text))
                
                new_step = course['current'] + 1
                if new_step > course['total']:
                    await db.complete_course(cid)
                    await state.set_state(TitusSt.menu)
                    timer_running = False
                    timer_task.cancel()
                    try:
                        await status_msg.delete()
                    except:
                        pass
                    await msg.answer(
                        f"{resp_clean}\n\n🎉 <b>Курс завершён!</b>\n\nПоздравляю с достижением!",
                        reply_markup=reply.study_kb()
                    )
                    return
                else:
                    await db.update_course_step(cid, new_step)
                    current_step = new_step
                    await state.update_data(current_step=new_step)
        
        last_messages[user_id] = {"text": resp_clean, "course": cname, "step": current_step}
        resp = resp_clean
                        
    finally:
        timer_running = False
        timer_task.cancel()
        try:
            await status_msg.delete()
        except:
            pass
        active_requests.pop(user_id, None)
    
    if resp:
        step_info = f" • Шаг {current_step}/{total_steps}" if cid else ""
        
        if len(resp) >= 3000:
            preview = make_preview(resp, 800)
            text_to_send = f"{preview}\n\n<i>📖 Полный текст — нажмите Telegraph</i>"
        else:
            text_to_send = resp
        
        await msg.answer("💬", reply_markup=reply.study_chat_kb())
        await msg.answer(
            f"{text_to_send}\n\n<i>📓 Обучение{step_info}</i>",
            reply_markup=inline.titus_msg_kb(user_id, has_telegraph=True)
        )


@router.message(TitusSt.chat, F.text)
async def titus_text(msg: Message, state: FSMContext):
    await process_titus_message(msg, state, msg.text)


@router.message(TitusSt.chat, F.voice)
async def titus_voice(msg: Message, state: FSMContext):
    status = await msg.answer("🎧 Слушаю...")
    timer_running = True
    
    async def update_timer():
        sec = 0
        while timer_running:
            await asyncio.sleep(1)
            if not timer_running:
                break
            sec += 1
            try:
                await status.edit_text(f"🎧 Слушаю... ({sec} сек)")
            except:
                pass
    
    timer_task = asyncio.create_task(update_timer())
    try:
        fp = await download_voice(bot, msg.voice.file_id)
        text = await transcribe_voice(fp)
        timer_running = False
        timer_task.cancel()
        if not text:
            await status.edit_text("❌ Не распознано")
            return
        await status.delete()
    except Exception as e:
        timer_running = False
        timer_task.cancel()
        await status.edit_text(f"❌ {e}")
        return
    await process_titus_message(msg, state, text)


@router.message(TitusSt.chat, F.photo)
async def titus_photo(msg: Message, state: FSMContext):
    status = await msg.answer("🔎 Смотрю фото...")
    timer_running = True
    
    async def update_timer():
        sec = 0
        while timer_running:
            await asyncio.sleep(1)
            if not timer_running:
                break
            sec += 1
            try:
                await status.edit_text(f"🔎 Смотрю фото... ({sec} сек)")
            except:
                pass
    
    timer_task = asyncio.create_task(update_timer())
    try:
        photo = msg.photo[-1]
        file = await bot.get_file(photo.file_id)
        data = await bot.download_file(file.file_path)
        b64 = base64.b64encode(data.read()).decode()
        timer_running = False
        timer_task.cancel()
        await status.delete()
    except Exception as e:
        timer_running = False
        timer_task.cancel()
        await status.edit_text(f"❌ {e}")
        return
    await process_titus_message(msg, state, msg.caption or "Что на изображении?", b64)


@router.callback_query(F.data.startswith("course:continue:"))
async def course_continue_step(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    cid = int(parts[2])
    current_step = int(parts[3])
    
    await cb.answer()
    
    data = await state.get_data()
    cname = data.get('cname', 'Курс')
    total_steps = data.get('total_steps', 10)
    
    remaining = await db.get_available_tokens(cb.from_user.id)
    if remaining < MIN_TOKENS:
        await cb.message.answer("❌ Токены закончились!\n\n💎 Докупите в разделе 💠 Подписка", reply_markup=reply.main_kb())
        return
    
    model = await db.get_user_model(cb.from_user.id)
    
    status = await cb.message.answer("⏳ Обрабатываю. Пожалуйста подождите...")
    timer_running = True
    
    async def update_timer():
        sec = 0
        while timer_running:
            await asyncio.sleep(1)
            if not timer_running:
                break
            sec += 1
            try:
                await status.edit_text(f"✍️ Печатаю... ({sec} сек)")
            except:
                pass
    
    timer_task = asyncio.create_task(update_timer())
    
    sys = TITUS_BASE + f"\n\nКУРС: {cname}\nШАГ: {current_step} из {total_steps}\n\n⚠️ Продолжи обучение с шага {current_step}. Сразу начни с 📌 Тема:"
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": f"Продолжи с шага {current_step}"}]
    
    resp, tok = await ask(msgs, model)
    timer_running = False
    timer_task.cancel()
    await status.delete()
    
    resp_clean = resp.replace("---NEXT---", "").strip()
    resp_clean = clean_html_for_telegram(resp_clean)
    
    await db.use_tokens_smart(cb.from_user.id, tok)
    await db.increment_requests(cb.from_user.id)
    await db.add_msg(cb.from_user.id, 'titus', 'assistant', resp_clean)
    
    last_messages[cb.from_user.id] = {"text": resp_clean, "course": cname, "step": current_step}
    
    if len(resp_clean) >= 3000:
        preview = make_preview(resp_clean, 800)
        text_to_send = f"{preview}\n\n<i>📖 Полный текст — нажмите Telegraph</i>"
    else:
        text_to_send = resp_clean
    
    await cb.message.answer(
        f"{text_to_send}\n\n<i>📓 Обучение • Шаг {current_step}/{total_steps}</i>",
        reply_markup=inline.titus_msg_kb(cb.from_user.id, has_telegraph=True)
    )


@router.callback_query(F.data.startswith("course:repeat:"))
async def course_repeat_weak(cb: CallbackQuery, state: FSMContext):
    cid = int(cb.data.split(":")[2])
    
    await cb.answer()
    
    data = await state.get_data()
    cname = data.get('cname', 'Курс')
    current_step = data.get('current_step', 1)
    total_steps = data.get('total_steps', 10)
    
    remaining = await db.get_available_tokens(cb.from_user.id)
    if remaining < MIN_TOKENS:
        await cb.message.answer("❌ Токены закончились!\n\n💎 Докупите в разделе 💠 Подписка", reply_markup=reply.main_kb())
        return
    
    model = await db.get_user_model(cb.from_user.id)
    
    course_mem = await db.get_course_memory(cid)
    weak_topics = []
    if course_mem and course_mem.get('weak_topics'):
        weak = course_mem['weak_topics']
        if isinstance(weak, str):
            try:
                weak = json.loads(weak)
            except:
                weak = []
        weak_topics = weak[:3] if isinstance(weak, list) else []
    
    topics_text = ", ".join([t.get('topic', str(t)) if isinstance(t, dict) else str(t) for t in weak_topics])
    
    status = await cb.message.answer("⏳ Обрабатываю. Пожалуйста подождите...")
    timer_running = True
    
    async def update_timer():
        sec = 0
        while timer_running:
            await asyncio.sleep(1)
            if not timer_running:
                break
            sec += 1
            try:
                await status.edit_text(f"✍️ Печатаю... ({sec} сек)")
            except:
                pass
    
    timer_task = asyncio.create_task(update_timer())
    
