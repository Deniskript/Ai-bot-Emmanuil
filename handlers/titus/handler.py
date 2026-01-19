"""
Обработчик Titus (Обучение) - оптимизирован для 1000+ пользователей
Использует централизованное ядро core/
"""
import asyncio
import base64
import json
import logging
import re

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, 
    KeyboardButton, WebAppInfo, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Core — централизованное ядро
from core import rate_limiter, cleanup_manager
from core.cache import LRUCache
from core.config import MSG_RATE_LIMITED

# Database
from database import postgres_db as db

# Utils
from keyboards import reply, inline
from utils.openrouter import ask
from utils.stars import calculate_stars
from utils.conversations import save_message, clean_response, should_show_preview, get_titus_keyboard
from utils.streaming import stream_response
from utils.status_manager import show_status
from utils.markdown import md_to_html
from utils.balance_guard import ensure_balance
from loader import bot

# Локальные импорты модуля
from . import config as titus_config
from . import texts
from .memory import save_step_progress, build_smart_context
from .prompts import TITUS_BASE, TITUS_CLARIFY

# Logging
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════
# ИНИЦИАЛИЗАЦИЯ
# ═══════════════════════════════════════

router = Router()  # ТОЛЬКО ОДИН РАЗ!

# Константы из локального config
MIN_STARS = titus_config.MIN_STARS
VIDEO_ANALYSIS_MODEL = titus_config.VIDEO_ANALYSIS_MODEL
MAX_TRANSCRIPT_LENGTH = titus_config.MAX_TRANSCRIPT_LENGTH

# Кэши с автоочисткой через core (вместо утекающих dict)
last_messages_cache = LRUCache(max_size=500, default_ttl=3600)
active_requests_cache = LRUCache(max_size=200, default_ttl=300)

# Регистрация очистки в core
cleanup_manager.register(last_messages_cache.cleanup)
cleanup_manager.register(active_requests_cache.cleanup)


# ═══════════════════════════════════════
# СОСТОЯНИЯ FSM
# ═══════════════════════════════════════

class TitusSt(StatesGroup):
    menu = State()
    chat = State()
    new_course = State()
    select_steps = State()
    courses_menu = State()
    continue_course = State()
    delete_course = State()
    video_analysis = State()


# ═══════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════

def is_clarification_question(text: str) -> bool:
    """Определяет, является ли сообщение уточняющим вопросом по теме"""
    text_lower = text.lower().strip()
    
    clarify_markers = [
        "не понял", "не понимаю", "непонятно",
        "объясни", "поясни", "расскажи подробнее",
        "почему", "зачем", "как это", "что значит",
        "можешь объяснить", "ещё раз", "еще раз",
        "а если", "а как", "а что",
        "не ясно", "неясно", "уточни",
        "в смысле", "то есть", "имеется в виду"
    ]
    
    for marker in clarify_markers:
        if marker in text_lower:
            return True
    
    if "?" in text and len(text) < 100:
        return True
    
    return False


async def batch_db_operations(user_id: int, stars_used: int, bot_name: str = 'titus'):
    """Батчинг операций с БД"""
    await asyncio.gather(
        db.use_stars_smart(user_id, stars_used, bot_name),
        db.increment_requests(user_id),
        return_exceptions=True
    )


# ═══════════════════════════════════════
# ОБРАБОТЧИКИ МЕНЮ
# ═══════════════════════════════════════

@router.message(F.text.in_(["📓 Обучение", "📚 Обучение"]))
async def titus_enter(msg: Message, state: FSMContext):
    cfg = await db.get_bot_cfg('titus')
    if not cfg['enabled']:
        await msg.answer(texts.BOT_DISABLED)
        return
    await state.set_state(TitusSt.menu)
    
    banner = FSInputFile("assets/banner_titus.png")
    await msg.answer_photo(
        photo=banner,
        reply_markup=reply.study_kb(msg.from_user.id)
    )


@router.message(TitusSt.menu, F.text == "📝 Новый курс")
async def titus_new_course(msg: Message, state: FSMContext):
    courses = await db.get_courses(msg.from_user.id)
    active = [c for c in courses if not c['done']]
    if len(active) >= titus_config.MAX_ACTIVE_COURSES:
        await msg.answer(texts.MAX_COURSES_REACHED, reply_markup=reply.back_kb())
        return
    await state.set_state(TitusSt.new_course)
    await msg.answer(texts.NEW_COURSE_PROMPT, reply_markup=reply.back_kb())


@router.message(TitusSt.new_course, F.text == "◀️ Назад")
async def new_course_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.menu)
    await msg.answer(texts.MENU_TEXT, reply_markup=reply.study_kb(msg.from_user.id))


@router.message(TitusSt.new_course, F.text)
async def titus_course_name(msg: Message, state: FSMContext):
    await state.update_data(cname=msg.text)
    await state.set_state(TitusSt.select_steps)
    await msg.answer(f"📓 <b>{msg.text}</b>\n\n{texts.SELECT_STEPS_PROMPT}", reply_markup=reply.study_steps_kb())


@router.message(TitusSt.select_steps, F.text == "◀️ Назад")
async def steps_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.new_course)
    await msg.answer(texts.COURSE_NAME_PROMPT, reply_markup=reply.back_kb())


@router.message(TitusSt.select_steps, F.text.in_({"🚀 10 шагов", "📘 40 шагов", "📖 80 шагов"}))
async def create_course(msg: Message, state: FSMContext):
    if not await ensure_balance(msg, required=MIN_STARS):
        return
    
    user_id = msg.from_user.id
    model = await db.get_user_model(user_id)
    
    steps_map = {"🚀 10 шагов": 10, "📘 40 шагов": 40, "📖 80 шагов": 80}
    steps = steps_map[msg.text]
    data = await state.get_data()
    cname = data['cname']
    cid = await db.create_course(user_id, cname, steps)
    await state.set_state(TitusSt.chat)
    await state.update_data(cid=cid, cname=cname, current_step=1, total_steps=steps)
    await db.clear_msgs(user_id, 'titus')
    
    await msg.answer(
        f"✅ <b>Курс «{cname}» создан!</b>\n\n"
        f"📚 Количество шагов: {steps}\n"
        f"📍 Начинаем <b>Шаг 1</b>...",
        reply_markup=reply.study_chat_kb()
    )
    
    base_prompt = TITUS_BASE
    sys = base_prompt + f"\n\nКУРС: {cname}\nШАГ: 1 из {steps}\n\n⚠️ НЕ представляйся! Сразу начни с 📌 Тема:"
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": "Начни шаг 1"}]
    
    try:
        resp, sent_msg = await stream_response(
            bot=bot,
            message=msg,
            messages=msgs,
            model=model,
            status_type="text"
        )
        stars_used = calculate_stars(msgs, resp)
    except Exception as e:
        logger.error(f"Stream error in create_course: {e}")
        raise
    
    resp_clean = resp.replace("---NEXT---", "").strip()
    resp_clean = clean_response(resp_clean)
    
    # Батчинг операций БД
    await batch_db_operations(user_id, stars_used, 'titus')
    
    conv_id = await save_message(user_id, 'assistant', resp_clean, 'titus')
    
    # Сохраняем в кэш (с автоочисткой)
    last_messages_cache.set(user_id, {"text": resp_clean, "course": cname, "step": 1})
    
    keyboard = get_titus_keyboard(conv_id, len(resp_clean), user_id)
    
    final_text = f"<i>📓 Обучение • Шаг 1/{steps}</i>"
    
    if sent_msg:
        try:
            await sent_msg.edit_reply_markup(reply_markup=keyboard)
        except Exception:
            await msg.answer(final_text, reply_markup=keyboard)
    else:
        await msg.answer(final_text, reply_markup=keyboard)


@router.message(TitusSt.menu, F.text == "📁 Ваши курсы")
async def my_courses(msg: Message, state: FSMContext):
    courses = await db.get_courses(msg.from_user.id)
    if not courses:
        await msg.answer(texts.NO_COURSES)
        return
    await state.set_state(TitusSt.courses_menu)
    await state.update_data(courses=[dict(c) for c in courses])
    await msg.answer("📁 <b>Ваши курсы</b>\n\nВыберите действие:", reply_markup=reply.courses_action_kb())


@router.message(TitusSt.courses_menu, F.text == "◀️ Назад")
async def courses_menu_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.menu)
    await msg.answer(texts.MENU_TEXT, reply_markup=reply.study_kb(msg.from_user.id))


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
    await msg.answer("📁 <b>Ваши курсы</b>", reply_markup=reply.courses_action_kb())


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
            
            # Батчинг запросов к БД
            user, course_mem = await asyncio.gather(
                db.get_user(msg.from_user.id),
                db.get_course_memory(cid),
                return_exceptions=True
            )
            
            if isinstance(user, Exception):
                user = None
            if isinstance(course_mem, Exception):
                course_mem = None
            
            name = user.get('first_name', 'друг') if user else 'друг'
            
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
        logger.error(f"Error in continue_select: {e}")
    await msg.answer(texts.ERROR_SELECT_COURSE)


@router.message(TitusSt.delete_course, F.text == "◀️ Назад")
async def delete_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.courses_menu)
    await msg.answer("📁 <b>Ваши курсы</b>", reply_markup=reply.courses_action_kb())


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
            await msg.answer(texts.COURSE_DELETED.format(name=course['name']))
            await state.set_state(TitusSt.menu)
            await msg.answer(texts.MENU_TEXT, reply_markup=reply.study_kb(msg.from_user.id))
            return
    await msg.answer(texts.ERROR_SELECT_COURSE)


# ═══════════════════════════════════════
# АНАЛИЗ ВИДЕО (с asyncio.to_thread для YouTube API)
# ═══════════════════════════════════════

@router.message(TitusSt.menu, F.text.in_(["📚 Анализ видео", "📹 Анализ видео"]))
async def video_analysis_start(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.video_analysis)
    await msg.answer(
        texts.VIDEO_ANALYSIS_START,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📂 Мои конспекты", web_app=WebAppInfo(url=f"https://soul-bot.ru/creativity/video-notes?user_id={msg.from_user.id}"))],
                [KeyboardButton(text="◀️ Назад")],
            ],
            resize_keyboard=True
        )
    )


@router.message(TitusSt.video_analysis, F.text == "◀️ Назад")
async def video_analysis_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.menu)
    from keyboards.reply import socials_menu_kb
    await msg.answer("📲 Соцсети", reply_markup=socials_menu_kb(msg.from_user.id))


@router.message(TitusSt.video_analysis, F.text)
async def video_analysis_process(msg: Message, state: FSMContext):
    from youtube_transcript_api import YouTubeTranscriptApi
    
    user_id = msg.from_user.id
    logger.info(f"Video analysis started for user {user_id}")
    
    if not await ensure_balance(msg, required=MIN_STARS):
        return
    
    # Извлечение video_id
    video_id = None
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, msg.text)
        if match:
            video_id = match.group(1)
            break
    
    if not video_id:
        await msg.answer(texts.VIDEO_ANALYSIS_INVALID_LINK, reply_markup=reply.back_kb())
        return
    
    logger.debug(f"Video ID extracted: {video_id}")
    
    status = await show_status(bot, msg.chat.id, "text")
    
    try:
        # ✅ Асинхронный вызов YouTube API (не блокирует event loop!)
        transcript_list = await asyncio.to_thread(
            YouTubeTranscriptApi.list_transcripts, 
            video_id
        )
        
        transcript = None
        try:
            transcript = await asyncio.to_thread(
                transcript_list.find_transcript, 
                ['ru', 'en']
            )
        except:
            transcript = await asyncio.to_thread(
                transcript_list.find_generated_transcript, 
                ['ru', 'en']
            )
        
        if not transcript:
            await msg.answer("❌ У этого видео нет субтитров")
            return
        
        captions = await asyncio.to_thread(transcript.fetch)
        full_text = " ".join([entry['text'] for entry in captions])
        logger.debug(f"Transcript fetched: {len(full_text)} chars")
        
        if len(full_text) > MAX_TRANSCRIPT_LENGTH:
            full_text = full_text[:MAX_TRANSCRIPT_LENGTH] + "..."
        
        analysis_prompt = f"""Проанализируй это видео по субтитрам и составь структурированный конспект:

{full_text}

Требования:
- Главная тема
- Ключевые моменты (по пунктам)
- Важные детали
- Выводы

Формат: структурированно, с эмодзи, понятно."""
        
        resp, stars_used = await ask([{"role": "user", "content": analysis_prompt}], VIDEO_ANALYSIS_MODEL)
        
        if status:
            await status.stop()
        
        resp_clean = clean_response(resp)
        
        # Батчинг операций БД
        await batch_db_operations(user_id, stars_used, 'titus')
        
        conv_id = await save_message(user_id, 'assistant', resp_clean, 'titus')

        # Сохраняем конспект в PostgreSQL
        try:
            from database.postgres_db import add_video_note
            url = f"https://www.youtube.com/watch?v={video_id}"
            title = f"YouTube {video_id}"
            await add_video_note(user_id, title=title, url=url, text=resp_clean, source="YouTube")
        except Exception as e:
            logger.error(f"Error saving video note: {e}")
        
        # Сохраняем в кэш
        last_messages_cache.set(user_id, {"text": resp_clean, "course": "Анализ видео", "step": 1})
        
        needs_preview, display_text = should_show_preview(resp_clean, max_length=3000)
        keyboard = get_titus_keyboard(conv_id, len(resp_clean), user_id)
        
        await msg.answer(
            f"📹 <b>Анализ видео</b>\n\n{display_text}",
            reply_markup=keyboard
        )
        
        await state.set_state(TitusSt.menu)
        from keyboards.reply import socials_menu_kb
        await msg.answer(texts.VIDEO_ANALYSIS_COMPLETED, reply_markup=socials_menu_kb(user_id))
        
        logger.info(f"Video analysis completed for user {user_id}")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Video analysis error: {error_msg}")
        if "Subtitles are disabled" in error_msg or "transcript" in error_msg.lower():
            await msg.answer(texts.VIDEO_ANALYSIS_NO_SUBTITLES)
        else:
            await msg.answer(f"❌ Ошибка: {error_msg[:200]}")
    finally:
        if status:
            await status.stop()


# ═══════════════════════════════════════
# МЕНЮ И УПРАВЛЕНИЕ ЧАТОМ
# ═══════════════════════════════════════

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
    await msg.answer(texts.COURSE_SAVED, reply_markup=reply.study_kb(msg.from_user.id))


@router.message(TitusSt.chat, F.text == "🗑 Очистить")
async def titus_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'titus')
    await msg.answer(texts.HISTORY_CLEARED, reply_markup=reply.study_chat_kb())


@router.message(TitusSt.chat, F.text == "⌛️ Отменить запрос")
async def titus_cancel(msg: Message):
    user_id = msg.from_user.id
    request_data = active_requests_cache.get(user_id)
    
    if request_data and isinstance(request_data, dict):
        request_data['cancelled'] = True
        try:
            if request_data.get('kb_msg'):
                await request_data['kb_msg'].delete()
        except:
            pass
        try:
            if request_data.get('status'):
                await request_data['status'].stop()
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
    cached = last_messages_cache.get(user_id)
    
    if not cached:
        await cb.answer(texts.NO_TEXT_FOR_SUMMARY, show_alert=True)
        return
    
    if not await ensure_balance(cb, required=MIN_STARS):
        return
    
    await cb.answer(texts.SUMMARY_CREATING)
    
    model = await db.get_user_model(user_id)
    
    summary_prompt = f"""Сделай краткий конспект из этого текста:

{cached['text']}

Требования: структурированно, по пунктам, только важное."""

    try:
        resp, stars_used = await ask([{"role": "user", "content": summary_prompt}], model)
        resp = clean_response(resp)
        await batch_db_operations(user_id, stars_used, 'titus')
        await cb.message.answer(
            f"📝 <b>Конспект | {cached.get('course', 'Курс')} | Шаг {cached.get('step', 1)}</b>\n\n{resp}",
            reply_markup=reply.study_chat_kb()
        )
    except Exception as e:
        await cb.message.answer(f"❌ Ошибка: {e}", reply_markup=reply.study_chat_kb())


# ═══════════════════════════════════════
# ОСНОВНАЯ ОБРАБОТКА СООБЩЕНИЙ
# ═══════════════════════════════════════

async def process_titus_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    user_id = msg.from_user.id
    
    # Rate limiting через core
    allowed, wait_time = await rate_limiter.check(user_id)
    if not allowed:
        await msg.answer(MSG_RATE_LIMITED.format(seconds=wait_time), reply_markup=reply.study_chat_kb())
        return
    
    if not await ensure_balance(msg, required=MIN_STARS):
        return
    
    model = await db.get_user_model(user_id)
    
    data = await state.get_data()
    cid = data.get('cid')
    cname = data.get('cname', 'Курс')
    request_state = {'cancelled': False, 'kb_msg': None, 'status': None}
    active_requests_cache.set(user_id, request_state)
    
    current_step = data.get('current_step', 1)
    total_steps = data.get('total_steps', 10)
    resp = None
    stars_used = 0
    conv_id = None
    
    try:
        if request_state['cancelled']:
            return
        
        # Батчинг запросов к БД
        if cid:
            course, hist, course_mem, user = await asyncio.gather(
                db.get_course(cid),
                db.get_msgs(user_id, 'titus'),
                db.get_course_memory(cid),
                db.get_user(user_id),
                return_exceptions=True
            )
            
            # Обработка ошибок
            if isinstance(course, Exception):
                course = None
            if isinstance(hist, Exception):
                hist = []
            if isinstance(course_mem, Exception):
                course_mem = None
            if isinstance(user, Exception):
                user = None
        else:
            hist = await db.get_msgs(user_id, 'titus')
            course = None
            course_mem = None
            user = None
        
        course_info = ""
        
        if course:
            current_step = course['current']
            total_steps = course['total']
            await state.update_data(current_step=current_step, total_steps=total_steps)
            
            student_name = user.get('first_name') if user else None
            memory_context = build_smart_context(course_mem, current_step, student_name)
            logger.debug(f"Memory context for course {cid}: {len(memory_context)} chars")
            
            course_info = f"\n\nКУРС: {course['name']}\nШАГ: {current_step} из {total_steps}\nПРОГРЕСС: {int(current_step/total_steps*100)}%"
            if memory_context:
                course_info += f"\n\n{memory_context}"
        
        # Определяем тип промпта
        base_prompt = TITUS_CLARIFY if is_clarification_question(text) else TITUS_BASE
        
        sys = base_prompt + course_info
        msgs_to_send = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": text}]
        
        if request_state['cancelled']:
            return
        
        if image_b64:
            resp, stars_used = await ask(msgs_to_send, model, image_b64)
            sent_msg = None
        else:
            resp, sent_msg = await stream_response(
                bot=bot,
                message=msg,
                messages=msgs_to_send,
                model=model,
                status_type="text"
            )
            stars_used = calculate_stars(msgs_to_send, resp)
        
        if request_state['cancelled']:
            return
        
        # Определяем переход на следующий шаг
        user_lower = text.lower().strip()
        
        question_markers = [
            '?', 'не понял', 'непонял', 'не понимаю', 'объясни', 'поясни', 'почему', 'зачем',
            'как это', 'что значит', 'что такое', 'можешь объяснить', 'расскажи подробнее',
            'затрудняюсь', 'сложно', 'не знаю', 'трудно'
        ]
        
        skip_markers = [
            'понял', 'ясно', 'дальше', 'давай', 'следующий', 'продолжай', 'го', 'далее',
            'окей', 'ок', 'хорошо', 'ладно', 'да', 'угу', 'ага'
        ]
        
        is_question = any(q in user_lower for q in question_markers)
        is_skip = any(s in user_lower for s in skip_markers) and not is_question
        is_answer = len(text) > 15 and not is_question and not is_skip
        should_advance = (is_skip or is_answer) and cid is not None
        
        resp_clean = resp.replace("---NEXT---", "").strip()
        resp_clean = clean_response(resp_clean)
        
        # Батчинг операций БД
        await batch_db_operations(user_id, stars_used, 'titus')
        
        # Сохраняем сообщения
        await save_message(user_id, 'user', text, 'titus')
        conv_id = await save_message(user_id, 'assistant', resp_clean, 'titus')
        
        # Логика перехода на следующий шаг
        if cid and should_advance and course:
            last_bot_msg = hist[-1]['content'] if hist and hist[-1]['role'] == 'assistant' else ""
            asyncio.create_task(save_step_progress(cid, current_step, last_bot_msg, text))
            
            new_step = course['current'] + 1
            if new_step > course['total']:
                await db.complete_course(cid)
                await state.set_state(TitusSt.menu)
                await msg.answer(
                    f"{resp_clean}\n\n{texts.COURSE_COMPLETED}",
                    reply_markup=reply.study_kb(user_id)
                )
                return
            else:
                await db.update_course_step(cid, new_step)
                current_step = new_step
                await state.update_data(current_step=new_step)
        
        # Сохраняем в кэш
        last_messages_cache.set(user_id, {"text": resp_clean, "course": cname, "step": current_step})
        resp = resp_clean
                        
    finally:
        active_requests_cache.delete(user_id)
    
    if resp:
        step_info = f" • Шаг {current_step}/{total_steps}" if cid else ""
        needs_preview, display_text = should_show_preview(resp, max_length=3000)
        keyboard = get_titus_keyboard(conv_id, len(resp), user_id)

        temp_msg = None
        try:
            temp_msg = await msg.answer("💬", reply_markup=reply.study_chat_kb())
        except Exception:
            pass

        try:
            final_text = f"{display_text}\n\n<i>📓 Обучение{step_info}</i>"
            
            if sent_msg:
                try:
                    await sent_msg.edit_text(final_text, reply_markup=keyboard, parse_mode="HTML")
                except Exception:
                    await msg.answer(final_text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await msg.answer(final_text, reply_markup=keyboard, parse_mode="HTML")
        finally:
            if temp_msg:
                try:
                    await temp_msg.delete()
                except Exception:
                    pass


@router.message(TitusSt.chat, F.text)
async def titus_text(msg: Message, state: FSMContext):
    await process_titus_message(msg, state, msg.text)


@router.message(TitusSt.chat, F.photo)
async def titus_photo(msg: Message, state: FSMContext):
    status = await show_status(bot, msg.chat.id, "photo")
    try:
        photo = msg.photo[-1]
        file = await bot.get_file(photo.file_id)
        data = await bot.download_file(file.file_path)
        b64 = base64.b64encode(data.read()).decode()
    except Exception as e:
        await msg.answer(f"❌ {e}")
        return
    finally:
        if status:
            await status.stop()
    await process_titus_message(msg, state, msg.caption or "Что на изображении?", b64)


# ═══════════════════════════════════════
# CALLBACK HANDLERS
# ═══════════════════════════════════════

@router.callback_query(F.data.startswith("course:continue:"))
async def course_continue_step(cb: CallbackQuery, state: FSMContext):
    logger.debug(f"course_continue_step called, data={cb.data}")
    parts = cb.data.split(":")
    cid = int(parts[2])
    current_step = int(parts[3])
    user_id = cb.from_user.id
    
    await cb.answer()
    temp_msg = None
    try:
        temp_msg = await cb.message.answer("💬", reply_markup=reply.study_chat_kb())
    except Exception:
        pass
    
    data = await state.get_data()
    cname = data.get('cname', 'Курс')
    total_steps = data.get('total_steps', 10)
    
    if not await ensure_balance(cb, required=MIN_STARS):
        return
    
    model = await db.get_user_model(user_id)
    
    base_prompt = TITUS_BASE
    sys = base_prompt + f"\n\nКУРС: {cname}\nШАГ: {current_step} из {total_steps}\n\n⚠️ Продолжи обучение с шага {current_step}. Сразу начни с 📌 Тема:"
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": f"Продолжи с шага {current_step}"}]
    
    try:
        resp, sent_msg = await stream_response(
            bot=bot,
            message=cb.message,
            messages=msgs,
            model=model,
            status_type="text"
        )
        stars_used = calculate_stars(msgs, resp)
    except Exception as e:
        logger.error(f"Stream error in course_continue: {e}")
        raise
    finally:
        if temp_msg:
            try:
                await temp_msg.delete()
            except Exception:
                pass

    resp_clean = resp.replace("---NEXT---", "").strip()
    resp_clean = clean_response(resp_clean)
    footer = f"\n\n<i>📓 Обучение • Шаг {current_step}/{total_steps}</i>"
    resp_with_footer = f"{resp_clean}{footer}"

    await batch_db_operations(user_id, stars_used, 'titus')
    conv_id = await save_message(user_id, 'assistant', resp_clean, 'titus')
    
    last_messages_cache.set(user_id, {"text": resp_clean, "course": cname, "step": current_step})
    keyboard = get_titus_keyboard(conv_id, len(resp_clean), user_id)

    if sent_msg:
        try:
            await sent_msg.edit_text(resp_with_footer, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            await cb.message.answer(resp_with_footer, parse_mode="HTML", reply_markup=keyboard)
    else:
        await cb.message.answer(resp_with_footer, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("course:repeat:"))
async def course_repeat_weak(cb: CallbackQuery, state: FSMContext):
    cid = int(cb.data.split(":")[2])
    user_id = cb.from_user.id
    
    await cb.answer()
    temp_msg = None
    try:
        temp_msg = await cb.message.answer("💬", reply_markup=reply.study_chat_kb())
    except Exception:
        pass
    
    data = await state.get_data()
    cname = data.get('cname', 'Курс')
    current_step = data.get('current_step', 1)
    total_steps = data.get('total_steps', 10)
    
    if not await ensure_balance(cb, required=MIN_STARS):
        return
    
    model = await db.get_user_model(user_id)
    
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
    
    base_prompt = TITUS_CLARIFY
    course_context = f"Курс: {cname}\nШаг: {current_step} из {total_steps}"
    
    sys = f"{base_prompt}\n\n📚 Контекст курса:\n{course_context}\n\n⚠️ Повтори и закрепи сложные темы: {topics_text}"
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": f"Разбери подробно темы, которые были сложными: {topics_text}"}]
    
    try:
        resp, sent_msg = await stream_response(
            bot=bot,
            message=cb.message,
            messages=msgs,
            model=model,
            status_type="text"
        )
        stars_used = calculate_stars(msgs, resp)
        
        resp_clean = clean_response(resp)
        
        await batch_db_operations(user_id, stars_used, 'titus')
        conv_id = await save_message(user_id, 'assistant', resp_clean, 'titus')
        
        last_messages_cache.set(user_id, {"text": resp_clean, "course": cname, "step": current_step})
        keyboard = get_titus_keyboard(conv_id, len(resp_clean), user_id)
        
        if sent_msg:
            try:
                await sent_msg.edit_reply_markup(reply_markup=keyboard)
            except Exception:
                await cb.message.answer(
                    f"<i>📓 Обучение • Повторение сложных тем</i>",
                    reply_markup=keyboard
                )
        else:
            await cb.message.answer(
                f"<i>📓 Обучение • Повторение сложных тем</i>",
                reply_markup=keyboard
            )
    except Exception as e:
        await cb.message.answer(f"❌ Ошибка: {str(e)[:200]}", reply_markup=reply.study_chat_kb())
    finally:
        if temp_msg:
            try:
                await temp_msg.delete()
            except Exception:
                pass
