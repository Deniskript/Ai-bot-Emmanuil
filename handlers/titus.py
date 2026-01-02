import re
import json
import base64
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import reply, inline
from utils.ai_client import ask
from utils.titus_memory import analyze_student_response
from utils.voice import download_voice, transcribe_voice
from utils.antiflood import ai_flood
from utils.telegraph import create_telegraph_page, make_preview
from prompts.all_prompts import TITUS_BASE
from config import MIN_TOKENS
from loader import bot


# Хранилище последних сообщений для конспекта/telegraph
last_messages = {}  # {user_id: {"text": str, "course": str, "step": int}}


def build_course_context(course_mem):
    if not course_mem:
        return ""
    parts = []
    problems = course_mem.get('problem_zones', '[]')
    if isinstance(problems, str):
        try:
            problems = json.loads(problems)
        except:
            problems = []
    if problems:
        parts.append("ПРОБЛЕМНЫЕ ТЕМЫ:")
        for p in problems[-5:]:
            step = p.get('step', '?')
            topic = p.get('topic', '?')
            question = p.get('question', '')
            parts.append("  - Шаг %s [%s]: %s" % (step, topic, question))
    topics = course_mem.get('completed_topics', '[]')
    if isinstance(topics, str):
        try:
            topics = json.loads(topics)
        except:
            topics = []
    if topics:
        parts.append("УСВОЕНО: " + ", ".join(topics[-10:]))
    summary = course_mem.get('summary', '')
    if summary:
        parts.append("ПРОГРЕСС: " + summary[:200])
    return "\n".join(parts)


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
        "📓 <b>Обучение — твой личный репетитор</b>\n\n"
        "🎯 Создаёт курсы по любой теме\n"
        "✨ Учит шаг за шагом",
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
    steps_map = {"🚀 10 шагов": 10, "📘 40 шагов": 40, "📖 80 шагов": 80}
    steps = steps_map[msg.text]
    data = await state.get_data()
    cname = data['cname']
    cid = await db.create_course(msg.from_user.id, cname, steps)
    await state.set_state(TitusSt.chat)
    await state.update_data(cid=cid, cname=cname, msg_count=0)
    await db.clear_msgs(msg.from_user.id, 'titus')
    await msg.answer(f"✅ <b>Курс создан!</b>\n\n📓 {cname}\n📊 Шагов: {steps}", reply_markup=reply.study_chat_kb())
    cfg = await db.get_bot_cfg('titus')
    sys = TITUS_BASE + f"\n\nКУРС: {cname}\nШАГ: 1 из {steps}"
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": "Начни шаг 1"}]
    status = await msg.answer("✍️ Готовлю первый шаг...")
    resp, tok = await ask(msgs, cfg['model'])
    await status.delete()
    await db.update_tokens(msg.from_user.id, tok)
    await db.add_msg(msg.from_user.id, 'titus', 'assistant', resp)
    
    # Сохраняем для конспекта
    last_messages[msg.from_user.id] = {"text": resp, "course": cname, "step": 1}
    
    # Определяем нужна ли кнопка Telegraph
    has_tg = len(resp) >= 3000
    
    if has_tg:
        preview = make_preview(resp, 800)
        await msg.answer(
            f"{preview}\n\n<i>⤵️ Читать полностью</i>",
            reply_markup=inline.titus_msg_kb(msg.from_user.id, has_telegraph=True)
        )
    else:
        await msg.answer(resp, reply_markup=inline.titus_msg_kb(msg.from_user.id, has_telegraph=False))


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
    await msg.answer("▶️ <b>Выберите курс:</b>", reply_markup=reply.courses_list_kb(courses))


@router.message(TitusSt.courses_menu, F.text == "🗑 Удалить курс")
async def delete_menu(msg: Message, state: FSMContext):
    data = await state.get_data()
    courses = data.get('courses', [])
    if not courses:
        await msg.answer("📂 Нет курсов")
        return
    await state.set_state(TitusSt.delete_course)
    await state.update_data(del_courses=courses)
    await msg.answer("🗑 <b>Выберите курс для удаления:</b>", reply_markup=reply.courses_list_kb(courses))


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
            await state.set_state(TitusSt.chat)
            await state.update_data(cid=course['id'], cname=course['name'], msg_count=0)
            await db.clear_msgs(msg.from_user.id, 'titus')
            course_mem = await db.get_course_memory(course['id'])
            progress = ""
            if course_mem and course_mem.get('summary'):
                progress = f"\n\n📋 {course_mem['summary'][:150]}"
            await msg.answer(f"📓 <b>{course['name']}</b>\n📊 Шаг {course['current']} из {course['total']}{progress}", reply_markup=reply.study_chat_kb())
            return
    except:
        pass
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
            try:
                await db.delete_course_memory(course['id'])
            except:
                pass
            await msg.answer(f"🗑 Курс «{course['name']}» удалён!")
            await state.set_state(TitusSt.menu)
            await msg.answer("📓 <b>Обучение</b>", reply_markup=reply.study_kb())
            return
    await msg.answer("❌ Выберите курс из списка")


@router.message(TitusSt.menu, F.text == "❓ Помощь")
async def titus_help(msg: Message):
    text = await db.get_text('help_study')
    if not text:
        text = "📓 <b>Обучение — умный репетитор</b>\n\n▸ Создаёт курсы по любой теме\n▸ Проверяет понимание\n▸ Возвращается к сложным темам"
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
    await msg.answer("🗑 История очищена")


@router.message(TitusSt.chat, F.text == "⌛️ Отменить запрос")
async def titus_cancel(msg: Message):
    user_id = msg.from_user.id
    if user_id in active_requests:
        active_requests[user_id] = True
        await msg.answer("❌ Запрос отменён", reply_markup=reply.study_chat_kb())
    else:
        await msg.answer("Нет активного запроса", reply_markup=reply.study_chat_kb())


# === CALLBACK HANDLERS для кнопок ===

@router.callback_query(F.data.startswith("titus:summary:"))
async def titus_make_summary(cb: CallbackQuery):
    """Создание конспекта"""
    user_id = cb.from_user.id
    
    if user_id not in last_messages:
        await cb.answer("❌ Нет текста для конспекта", show_alert=True)
        return
    
    await cb.answer("📝 Создаю конспект...")
    
    data = last_messages[user_id]
    original_text = data['text']
    course_name = data.get('course', 'Курс')
    step = data.get('step', 1)
    
    # Запрос к AI для создания конспекта
    cfg = await db.get_bot_cfg('titus')
    
    summary_prompt = f"""Сделай краткий конспект для записи в тетрадь из этого текста.

ТЕКСТ:
{original_text}

ТРЕБОВАНИЯ К КОНСПЕКТУ:
- Только самое важное и необходимое
- Структурированно, по пунктам
- Определения выделяй
- Формулы/правила отдельно
- Примеры коротко
- Для записи от руки в тетрадь

Конспект:"""

    msgs = [{"role": "user", "content": summary_prompt}]
    
    try:
        resp, tok = await ask(msgs, cfg['model'])
        await db.update_tokens(user_id, tok)
        
        await cb.message.answer(
            f"📝 <b>Конспект | {course_name} | Шаг {step}</b>\n\n{resp}",
            reply_markup=reply.study_chat_kb()
        )
    except Exception as e:
        await cb.message.answer(f"❌ Ошибка: {e}")


@router.callback_query(F.data.startswith("titus:tg:"))
async def titus_telegraph(cb: CallbackQuery):
    """Публикация на Telegraph"""
    user_id = cb.from_user.id
    
    if user_id not in last_messages:
        await cb.answer("❌ Нет текста", show_alert=True)
        return
    
    await cb.answer("📖 Публикую на Telegraph...")
    
    data = last_messages[user_id]
    original_text = data['text']
    course_name = data.get('course', 'Урок')
    step = data.get('step', 1)
    
    title = f"{course_name} — Шаг {step}"
    
    url = await create_telegraph_page(title, original_text)
    
    if url:
        await cb.message.answer(
            f"📖 <b>Полный текст опубликован</b>\n\n{title}",
            reply_markup=inline.titus_telegraph_kb(url)
        )
    else:
        await cb.message.answer("❌ Не удалось опубликовать на Telegraph")


async def process_titus_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    # Проверка антифлуда
    allowed, error_msg = await ai_flood.check(msg.from_user.id)
    if not allowed:
        await msg.answer(error_msg)
        return
    
    u = await db.get_user(msg.from_user.id)
    if not u or u['tokens'] < MIN_TOKENS:
        await msg.answer("❌ Недостаточно токенов!")
        return
    
    data = await state.get_data()
    cid = data.get('cid')
    cname = data.get('cname', 'Курс')
    
    user_id = msg.from_user.id
    active_requests[user_id] = False
    
    status_msg = await msg.answer("✍️ Печатаю...", reply_markup=reply.cancel_kb())
    
    current_step = 1
    total_steps = 10
    resp = None
    
    try:
        if active_requests.get(user_id, False):
            return
            
        cfg = await db.get_bot_cfg('titus')
        hist = await db.get_msgs(msg.from_user.id, 'titus')
        course_info = ""
        
        if cid:
            course = await db.get_course(cid)
            if course:
                current_step = course['current']
                total_steps = course['total']
                course_mem = await db.get_course_memory(cid)
                memory_context = build_course_context(course_mem)
                course_info = f"\n\nКУРС: {course['name']}\nШАГ: {current_step} из {total_steps}\nПРОГРЕСС: {int(current_step/total_steps*100)}%"
                if memory_context:
                    course_info += f"\n\n{memory_context}"
        
        sys = TITUS_BASE + course_info
        msgs_to_send = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": text}]
        
        if active_requests.get(user_id, False):
            return
            
        resp, tok = await ask(msgs_to_send, cfg['model'], image_b64)
        
        if active_requests.get(user_id, False):
            return
            
        await db.update_tokens(msg.from_user.id, tok)
        await db.add_msg(msg.from_user.id, 'titus', 'user', text)
        await db.add_msg(msg.from_user.id, 'titus', 'assistant', resp)
        
        # Сохраняем для конспекта/telegraph
        last_messages[user_id] = {"text": resp, "course": cname, "step": current_step}
        
        if cid and hist:
            last_bot_msg = hist[-1]['content'] if hist and hist[-1]['role'] == 'assistant' else ""
            asyncio.create_task(analyze_student_response(cid, current_step, last_bot_msg, text))
        
        if cid:
            markers = ["переходим к шагу", "идём к шагу", "следующий шаг"]
            if any(m in resp.lower() for m in markers):
                course = await db.get_course(cid)
                if course:
                    new_step = course['current'] + 1
                    if new_step > course['total']:
                        await db.complete_course(cid)
                        await msg.answer("🎉 <b>Курс завершён!</b>\n\nПоздравляю с достижением!")
                    else:
                        await db.update_course_step(cid, new_step)
                        
    finally:
        try:
            await status_msg.delete()
        except:
            pass
        active_requests.pop(user_id, None)
    
    if resp:
        # Определяем нужна ли кнопка Telegraph
        has_tg = len(resp) >= 3000
        step_info = f" • Шаг {current_step}/{total_steps}" if cid else ""
        
        if has_tg:
            preview = make_preview(resp, 800)
            await msg.answer(
                f"{preview}\n\n<i>📓 Обучение{step_info}</i>",
                reply_markup=inline.titus_msg_kb(user_id, has_telegraph=True)
            )
        else:
            await msg.answer(
                f"{resp}\n\n<i>📓 Обучение{step_info}</i>",
                reply_markup=inline.titus_msg_kb(user_id, has_telegraph=False)
            )


@router.message(TitusSt.chat, F.text)
async def titus_text(msg: Message, state: FSMContext):
    await process_titus_message(msg, state, msg.text)


@router.message(TitusSt.chat, F.voice)
async def titus_voice(msg: Message, state: FSMContext):
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
    await process_titus_message(msg, state, text)


@router.message(TitusSt.chat, F.photo)
async def titus_photo(msg: Message, state: FSMContext):
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
    await process_titus_message(msg, state, msg.caption or "Что на изображении?", b64)
