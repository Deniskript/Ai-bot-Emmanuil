"""
Обработчик Titus (Обучение) - 100% автономный модуль
"""
import re
import time
import json
import base64
import asyncio
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from database import redis_db
from keyboards import reply, inline
from utils.openrouter import ask, ask_stream
from utils.tokens import calculate_tokens
from utils.voice import download_voice, transcribe_voice, text_to_speech
from utils.antiflood import ai_flood
from utils.conversations import save_message, clean_response, should_show_preview, get_chat_button, get_titus_keyboard
from loader import bot

# Локальные импорты модуля (всё внутри handlers/titus/)
from . import config as titus_config
from . import texts
from .memory import save_step_progress, build_smart_context
from .prompts import TITUS_BASE, TITUS_VOICE_BASE

router = Router()

# Использование настроек из локального config
MIN_TOKENS = titus_config.MIN_TOKENS
MAX_CACHE_SIZE = titus_config.MAX_CACHE_SIZE
VIDEO_ANALYSIS_MODEL = titus_config.VIDEO_ANALYSIS_MODEL
MAX_TRANSCRIPT_LENGTH = titus_config.MAX_TRANSCRIPT_LENGTH

last_messages = {}
active_requests = {}


def cleanup_cache(cache_dict: dict, max_size: int = MAX_CACHE_SIZE):
    """Очистка кэша при превышении лимита"""
    if len(cache_dict) > max_size:
        keys_to_remove = list(cache_dict.keys())[:len(cache_dict) - max_size + 100]
        for key in keys_to_remove:
            cache_dict.pop(key, None)


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
    video_analysis = State()


active_requests = {}


@router.message(F.text.in_(["📓 Обучение", "📚 Обучение"]))
async def titus_enter(msg: Message, state: FSMContext):
    cfg = await db.get_bot_cfg('titus')
    if not cfg['enabled']:
        await msg.answer(texts.BOT_DISABLED)
        return
    await state.set_state(TitusSt.menu)
    await msg.answer(
        texts.MENU_TEXT,
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
    remaining = await db.get_available_tokens(msg.from_user.id)
    if remaining < MIN_TOKENS:
        await msg.answer("❌ Токены закончились!\n\n💎 Докупите в разделе 💠 Подписка", reply_markup=reply.main_kb(msg.from_user.id))
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
    
    await msg.answer(texts.COURSE_CREATED, reply_markup=reply.study_chat_kb())
    
    # Проверяем настройки голоса для выбора промпта
    titus_settings_pre = redis_db.get_titus_settings(msg.from_user.id) or {}
    voice_enabled_pre = bool(titus_settings_pre.get("voice_enabled", False))
    base_prompt = TITUS_VOICE_BASE if voice_enabled_pre else TITUS_BASE
    
    sys = base_prompt + f"\n\nКУРС: {cname}\nШАГ: 1 из {steps}\n\n⚠️ НЕ представляйся! Сразу начни с 📌 Тема:"
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": "Начни шаг 1"}]
    
    status = await msg.answer("⏳ Обрабатываю...")
    
    # STREAMING для создания курса
    full_response = ""
    sentence_buffer = ""
    displayed_text = ""
    last_update = time.time()
    typing_phase = 0
    stream_msg = None
    
    try:
        async for chunk in ask_stream(msgs, model, max_tokens=4000):
            if not chunk:
                continue
            
            full_response += chunk
            sentence_buffer += chunk
            now = time.time()
            
            if typing_phase == 0 and len(full_response) > 20:
                typing_phase = 1
                try:
                    await status.edit_text("✍️ Печатаю...")
                except:
                    pass
            
            if typing_phase == 1 and len(full_response) > 100:
                typing_phase = 2
                try:
                    await status.delete()
                except:
                    pass
                stream_msg = await msg.answer("_Печатаю..._", parse_mode=None)
            
            if typing_phase == 2 and stream_msg:
                if sentence_buffer.rstrip().endswith(('.', '!', '?', '\n\n')):
                    displayed_text += sentence_buffer
                    sentence_buffer = ""
                    
                    if now - last_update >= 0.5:
                        formatted = clean_response(displayed_text)
                        try:
                            await stream_msg.edit_text(formatted + " ▌")
                            last_update = now
                            await asyncio.sleep(0.3)
                        except:
                            pass
        
        displayed_text += sentence_buffer
        resp = full_response.strip()
        tok = calculate_tokens(msgs, resp)
        
        if stream_msg:
            try:
                await stream_msg.delete()
            except:
                pass
        if status and typing_phase < 2:
            try:
                await status.delete()
            except:
                pass
    except Exception as e:
        print(f"Stream error in create_course: {e}")
        if stream_msg:
            try:
                await stream_msg.delete()
            except:
                pass
        if status:
            try:
                await status.delete()
            except:
                pass
        raise
    
    resp_clean = resp.replace("---NEXT---", "").strip()
    resp_clean = clean_response(resp_clean)
    
    await db.use_tokens_smart(msg.from_user.id, tok, 'titus')
    await db.increment_requests(msg.from_user.id)
    
    # Сохраняем в систему диалогов
    conv_id = await save_message(msg.from_user.id, 'assistant', resp_clean, 'titus')
    
    last_messages[msg.from_user.id] = {"text": resp_clean, "course": cname, "step": 1}
    cleanup_cache(last_messages)  # Предотвращаем утечку памяти
    
    # Проверяем, нужно ли превью
    needs_preview, display_text = should_show_preview(resp_clean, max_length=3000)
    
    # Получаем клавиатуру с Конспектом и Посмотреть весь диалог
    keyboard = get_titus_keyboard(conv_id, len(resp_clean), msg.from_user.id)
    
    # Проверяем настройки голоса
    titus_settings = redis_db.get_titus_settings(msg.from_user.id) or {}
    voice_enabled = bool(titus_settings.get("voice_enabled", False))
    voice_gender = titus_settings.get("voice_gender", "male")
    
    if voice_enabled:
        # === ГОЛОСОВОЙ ОТВЕТ ===
        resp_for_tts = resp_clean
        resp_for_tts = re.sub(r"<[^>]+>", "", resp_for_tts)
        resp_for_tts = resp_for_tts.replace("**", "").replace("*", "")
        resp_for_tts = re.sub(r'[^\w\s,.!?;:—\-()«»"\'\n]+', '', resp_for_tts, flags=re.UNICODE)
        
        voice_tts = "onyx" if voice_gender == "male" else "shimmer"
        audio_path = await text_to_speech(resp_for_tts, voice=voice_tts)
        
        if audio_path:
            from aiogram.types import FSInputFile
            await msg.answer_voice(FSInputFile(audio_path), reply_markup=keyboard)
            try:
                os.remove(audio_path)
            except:
                pass
        else:
            # Fallback на текст
            await msg.answer(
                f"{display_text}\n\n<i>📓 Обучение • Шаг 1/{steps}</i>",
                reply_markup=keyboard
            )
    else:
        # Текстовый ответ
        await msg.answer(
            f"{display_text}\n\n<i>📓 Обучение • Шаг 1/{steps}</i>",
            reply_markup=keyboard
        )


@router.message(TitusSt.menu, F.text == "📂 Ваши курсы")
async def my_courses(msg: Message, state: FSMContext):
    courses = await db.get_courses(msg.from_user.id)
    if not courses:
        await msg.answer(texts.NO_COURSES)
        return
    await state.set_state(TitusSt.courses_menu)
    await state.update_data(courses=[dict(c) for c in courses])
    await msg.answer("📂 <b>Ваши курсы</b>\n\nВыберите действие:", reply_markup=reply.courses_action_kb())


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
    await msg.answer(texts.ERROR_SELECT_COURSE)


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
            await msg.answer(texts.COURSE_DELETED.format(name=course['name']))
            await state.set_state(TitusSt.menu)
            await msg.answer(texts.MENU_TEXT, reply_markup=reply.study_kb(msg.from_user.id))
            return
    await msg.answer(texts.ERROR_SELECT_COURSE)


@router.message(TitusSt.menu, F.text == "📚 Анализ видео")
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
    await msg.answer(texts.MENU_TEXT, reply_markup=reply.study_kb(msg.from_user.id))


@router.message(TitusSt.video_analysis, F.text)
async def video_analysis_process(msg: Message, state: FSMContext):
    from youtube_transcript_api import YouTubeTranscriptApi
    import re as regex
    import time
    
    user_id = msg.from_user.id
    start_time = time.time()
    print(f"[VIDEO] Начало анализа для пользователя {user_id}")
    
    # Проверка токенов
    remaining = await db.get_available_tokens(user_id)
    if remaining < MIN_TOKENS:
        await msg.answer("❌ Токены закончились!\n\n💎 Докупите в разделе 💠 Подписка", reply_markup=reply.main_kb(user_id))
        return
    
    print(f"[VIDEO] Токены проверены: {time.time() - start_time:.2f}с")
    
    # Извлечение video_id из ссылки
    video_id = None
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    
    for pattern in patterns:
        match = regex.search(pattern, msg.text)
        if match:
            video_id = match.group(1)
            break
    
    if not video_id:
        await msg.answer(texts.VIDEO_ANALYSIS_INVALID_LINK, reply_markup=reply.back_kb())
        return
    
    print(f"[VIDEO] Video ID извлечён: {video_id}, время: {time.time() - start_time:.2f}с")
    
    status = await msg.answer(texts.VIDEO_ANALYSIS_EXTRACTING)
    
    try:
        # Получаем субтитры
        print(f"[VIDEO] Начало загрузки субтитров: {time.time() - start_time:.2f}с")
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        print(f"[VIDEO] Субтитры получены: {time.time() - start_time:.2f}с")
        
        # Пытаемся получить русские или английские субтитры
        transcript = None
        try:
            transcript = transcript_list.find_transcript(['ru', 'en'])
            print(f"[VIDEO] Найдены субтитры: {time.time() - start_time:.2f}с")
        except:
            transcript = transcript_list.find_generated_transcript(['ru', 'en'])
            print(f"[VIDEO] Найдены автосубтитры: {time.time() - start_time:.2f}с")
        
        if not transcript:
            print(f"[VIDEO] Субтитры не найдены: {time.time() - start_time:.2f}с")
            await status.edit_text("❌ У этого видео нет субтитров")
            return
        
        # Получаем текст
        print(f"[VIDEO] Начало загрузки текста субтитров: {time.time() - start_time:.2f}с")
        captions = transcript.fetch()
        full_text = " ".join([entry['text'] for entry in captions])
        print(f"[VIDEO] Текст получен ({len(full_text)} символов): {time.time() - start_time:.2f}с")
        
        # Ограничиваем длину (макс 50к символов)
        if len(full_text) > 50000:
            full_text = full_text[:50000] + "..."
        
        await status.edit_text(f"✅ Субтитры получены ({len(full_text)} символов)\n⏳ Анализирую...")
        
        # Анализ через Gemini Flash (дешёвая модель)
        print(f"[VIDEO] Начало AI анализа: {time.time() - start_time:.2f}с")
        analysis_prompt = f"""Проанализируй это видео по субтитрам и составь структурированный конспект:

{full_text}

Требования:
- Главная тема
- Ключевые моменты (по пунктам)
- Важные детали
- Выводы

Формат: структурированно, с эмодзи, понятно."""
        
        resp, tok = await ask([{"role": "user", "content": analysis_prompt}], VIDEO_ANALYSIS_MODEL)
        print(f"[VIDEO] AI анализ завершён: {time.time() - start_time:.2f}с")
        
        await status.delete()
        
        resp_clean = clean_response(resp)
        
        # Списываем токены
        print(f"[VIDEO] Списание токенов: {time.time() - start_time:.2f}с")
        await db.use_tokens_smart(user_id, tok, 'titus')
        await db.increment_requests(user_id)
        
        # Сохраняем в систему диалогов
        print(f"[VIDEO] Сохранение в диалоги: {time.time() - start_time:.2f}с")
        conv_id = await save_message(user_id, 'assistant', resp_clean, 'titus')

        # Сохраняем конспект в PostgreSQL (для WebApp "Мои конспекты")
        try:
            print(f"[VIDEO] Сохранение в PostgreSQL: {time.time() - start_time:.2f}с")
            from database.postgres_db import add_video_note
            url = f"https://www.youtube.com/watch?v={video_id}"
            title = f"YouTube {video_id}"
            await add_video_note(user_id, title=title, url=url, text=resp_clean, source="YouTube")
        except Exception as e:
            print(f"[VIDEO] Ошибка сохранения в PostgreSQL: {e}")
        
        # Сохраняем в last_messages
        last_messages[user_id] = {"text": resp_clean, "course": "Анализ видео", "step": 1}
        cleanup_cache(last_messages)  # Предотвращаем утечку памяти
        
        # Проверяем, нужно ли превью
        needs_preview, display_text = should_show_preview(resp_clean, max_length=3000)
        
        # Получаем клавиатуру с Конспектом и Посмотреть весь диалог
        keyboard = get_titus_keyboard(conv_id, len(resp_clean), user_id)
        
        print(f"[VIDEO] Отправка результата пользователю: {time.time() - start_time:.2f}с")
        await msg.answer(
            f"📚 <b>Анализ видео</b>\n\n{display_text}",
            reply_markup=keyboard
        )
        
        await state.set_state(TitusSt.menu)
        await msg.answer(texts.VIDEO_ANALYSIS_COMPLETED, reply_markup=reply.study_kb(user_id))
        
        print(f"[VIDEO] ✅ ГОТОВО! Общее время: {time.time() - start_time:.2f}с")
        
    except Exception as e:
        error_msg = str(e)
        print(f"[VIDEO] ❌ ОШИБКА на {time.time() - start_time:.2f}с: {error_msg}")
        if "Subtitles are disabled" in error_msg or "transcript" in error_msg.lower():
            await status.edit_text(texts.VIDEO_ANALYSIS_NO_SUBTITLES)
        else:
            await status.edit_text(f"❌ Ошибка: {error_msg[:200]}")


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
        await cb.answer(texts.NO_TEXT_FOR_SUMMARY, show_alert=True)
        return
    
    remaining = await db.get_available_tokens(user_id)
    if remaining < MIN_TOKENS:
        await cb.answer(texts.SUMMARY_NOT_ENOUGH_TOKENS, show_alert=True)
        return
    
    await cb.answer(texts.SUMMARY_CREATING)
    
    model = await db.get_user_model(user_id)
    data = last_messages[user_id]
    
    summary_prompt = f"""Сделай краткий конспект из этого текста:

{data['text']}

Требования: структурированно, по пунктам, только важное."""

    try:
        resp, tok = await ask([{"role": "user", "content": summary_prompt}], model)
        resp = clean_response(resp)
        await db.use_tokens_smart(user_id, tok, 'titus')
        await db.increment_requests(user_id)
        await cb.message.answer(
            f"📝 <b>Конспект | {data.get('course', 'Курс')} | Шаг {data.get('step', 1)}</b>\n\n{resp}",
            reply_markup=reply.study_chat_kb()
        )
    except Exception as e:
        await cb.message.answer(f"❌ Ошибка: {e}", reply_markup=reply.study_chat_kb())


def check_step_transition(resp: str) -> bool:
    return "---NEXT---" in resp


async def process_titus_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    allowed, error_msg = await ai_flood.check(msg.from_user.id)
    if not allowed:
        await msg.answer(error_msg, reply_markup=reply.study_chat_kb())
        return
    
    remaining = await db.get_available_tokens(msg.from_user.id)
    if remaining < MIN_TOKENS:
        await msg.answer("❌ Токены закончились!\n\n💎 Докупите в разделе 💠 Подписка", reply_markup=reply.main_kb(msg.from_user.id))
        return
    
    model = await db.get_user_model(msg.from_user.id)
    titus_settings = redis_db.get_titus_settings(msg.from_user.id) or {}
    voice_enabled = bool(titus_settings.get("voice_enabled", False))
    voice_gender = titus_settings.get("voice_gender", "male")
    
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
        
        # Если включены голосовые ответы — используем voice-ориентированный промпт без HTML/эмодзи
        sys = (TITUS_VOICE_BASE if voice_enabled else TITUS_BASE) + course_info
        msgs_to_send = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": text}]
        
        if request_state['cancelled']:
            return
        
        if image_b64:
            resp, tok = await ask(msgs_to_send, model, image_b64)
        else:
            # УЛУЧШЕННЫЙ STREAMING для Titus
            full_response = ""
            sentence_buffer = ""
            displayed_text = ""
            last_update = time.time()
            typing_phase = 0
            stream_msg = None
            
            async for chunk in ask_stream(msgs_to_send, model, max_tokens=4000):
                if request_state['cancelled']:
                    return
                if not chunk:
                    continue
                
                full_response += chunk
                sentence_buffer += chunk
                now = time.time()
                
                # Фаза 1: показываем "печатаю"
                if typing_phase == 0 and len(full_response) > 20:
                    typing_phase = 1
                    try:
                        await status_msg.edit_text("✍️ Печатаю...")
                    except:
                        pass
                
                # Фаза 2: начинаем показывать текст блоками
                if typing_phase == 1 and len(full_response) > 100:
                    typing_phase = 2
                    try:
                        await status_msg.delete()
                    except:
                        pass
                    stream_msg = await msg.answer("_Печатаю..._", parse_mode=None)
                
                # Обновляем текст блоками
                if typing_phase == 2 and stream_msg:
                    if sentence_buffer.rstrip().endswith(('.', '!', '?', '\n\n')):
                        displayed_text += sentence_buffer
                        sentence_buffer = ""
                        
                        if now - last_update >= 0.5:
                            from utils.errors import check_tokens_and_notify
                            formatted = clean_response(displayed_text)
                            try:
                                await stream_msg.edit_text(formatted + " ▌")
                                last_update = now
                                await asyncio.sleep(0.3)
                            except:
                                pass
            
            displayed_text += sentence_buffer
            resp = full_response.strip()
            tok = calculate_tokens(msgs_to_send, resp)
            
            # Удаляем streaming сообщение
            if stream_msg:
                try:
                    await stream_msg.delete()
                except:
                    pass
            if status_msg and typing_phase < 2:
                try:
                    await status_msg.delete()
                except:
                    pass
        
        if request_state['cancelled']:
            return
        
        should_advance = check_step_transition(resp)
        resp_clean = resp.replace("---NEXT---", "").strip()
        resp_clean = clean_response(resp_clean)
        
        await db.use_tokens_smart(msg.from_user.id, tok, 'titus')
        await db.increment_requests(msg.from_user.id)
        
        # Сохраняем в систему диалогов
        await save_message(msg.from_user.id, 'user', text, 'titus')
        conv_id = await save_message(msg.from_user.id, 'assistant', resp_clean, 'titus')
        
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
                        f"{resp_clean}\n\n{texts.COURSE_COMPLETED}",
                        reply_markup=reply.study_kb(msg.from_user.id)
                    )
                    return
                else:
                    await db.update_course_step(cid, new_step)
                    current_step = new_step
                    await state.update_data(current_step=new_step)
        
        # Очищаем ответ от служебных строк
        resp_clean = clean_response(resp_clean)
        
        # Сохраняем в систему диалогов
        await save_message(user_id, 'user', text, 'titus', model)
        conv_id = await save_message(user_id, 'assistant', resp_clean, 'titus', model)
        
        last_messages[user_id] = {"text": resp_clean, "course": cname, "step": current_step}
        cleanup_cache(last_messages)  # Предотвращаем утечку памяти
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
        
        # Проверяем, нужно ли превью
        needs_preview, display_text = should_show_preview(resp, max_length=3000)
        
        # Получаем клавиатуру с Конспектом и Посмотреть весь диалог
        keyboard = get_titus_keyboard(conv_id, len(resp), user_id)

        if voice_enabled:
            # === ГОЛОСОВОЙ ОТВЕТ ===
            # Под TTS: убираем HTML/эмодзи/служебные маркеры
            resp_clean = resp.replace("---NEXT---", "").strip()
            resp_clean = re.sub(r"<[^>]+>", "", resp_clean)  # теги
            resp_clean = resp_clean.replace("**", "").replace("*", "")
            resp_clean = re.sub(r'[^\w\s,.!?;:—\-()«»"\'\n]+', '', resp_clean, flags=re.UNICODE)

            voice_tts = "onyx" if voice_gender == "male" else "shimmer"
            audio_path = await text_to_speech(resp_clean, voice=voice_tts)

            if audio_path:
                from aiogram.types import FSInputFile
                await msg.answer("💬", reply_markup=reply.study_chat_kb())
                await msg.answer_voice(FSInputFile(audio_path), reply_markup=keyboard)
                try:
                    os.remove(audio_path)
                except:
                    pass
            else:
                # Fallback на текст
                await msg.answer("💬", reply_markup=reply.study_chat_kb())
                await msg.answer(
                    f"{display_text}\n\n<i>📓 Обучение{step_info}</i>",
                    reply_markup=keyboard
                )
        else:
            await msg.answer("💬", reply_markup=reply.study_chat_kb())
            await msg.answer(
                f"{display_text}\n\n<i>📓 Обучение{step_info}</i>",
                reply_markup=keyboard
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
            await status.edit_text(texts.ERROR_NO_RECOGNITION)
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
        await cb.message.answer("❌ Токены закончились!\n\n💎 Докупите в разделе 💠 Подписка", reply_markup=reply.main_kb(msg.from_user.id))
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
    
    # Проверяем настройки голоса для выбора промпта
    titus_settings_pre = redis_db.get_titus_settings(cb.from_user.id) or {}
    voice_enabled_pre = bool(titus_settings_pre.get("voice_enabled", False))
    base_prompt = TITUS_VOICE_BASE if voice_enabled_pre else TITUS_BASE
    
    sys = base_prompt + f"\n\nКУРС: {cname}\nШАГ: {current_step} из {total_steps}\n\n⚠️ Продолжи обучение с шага {current_step}. Сразу начни с 📌 Тема:"
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": f"Продолжи с шага {current_step}"}]
    
    # STREAMING для продолжения
    full_response = ""
    sentence_buffer = ""
    displayed_text = ""
    last_update = time.time()
    typing_phase = 0
    stream_msg = None
    
    try:
        async for chunk in ask_stream(msgs, model, max_tokens=4000):
            if not chunk:
                continue
            
            full_response += chunk
            sentence_buffer += chunk
            now = time.time()
            
            if typing_phase == 0 and len(full_response) > 20:
                typing_phase = 1
                timer_running = False
                timer_task.cancel()
                try:
                    await status.edit_text("✍️ Печатаю...")
                except:
                    pass
            
            if typing_phase == 1 and len(full_response) > 100:
                typing_phase = 2
                try:
                    await status.delete()
                except:
                    pass
                stream_msg = await cb.message.answer("_Печатаю..._", parse_mode=None)
            
            if typing_phase == 2 and stream_msg:
                if sentence_buffer.rstrip().endswith(('.', '!', '?', '\n\n')):
                    displayed_text += sentence_buffer
                    sentence_buffer = ""
                    
                    if now - last_update >= 0.5:
                        formatted = clean_response(displayed_text)
                        try:
                            await stream_msg.edit_text(formatted + " ▌")
                            last_update = now
                            await asyncio.sleep(0.3)
                        except:
                            pass
        
        displayed_text += sentence_buffer
        resp = full_response.strip()
        tok = calculate_tokens(msgs, resp)
        
        if stream_msg:
            try:
                await stream_msg.delete()
            except:
                pass
        if status and typing_phase < 2:
            try:
                await status.delete()
            except:
                pass
    except Exception as e:
        print(f"Stream error in course_continue: {e}")
        timer_running = False
        timer_task.cancel()
        if stream_msg:
            try:
                await stream_msg.delete()
            except:
                pass
        if status:
            try:
                await status.delete()
            except:
                pass
        raise
    
    resp_clean = resp.replace("---NEXT---", "").strip()
    resp_clean = clean_response(resp_clean)
    
    await db.use_tokens_smart(cb.from_user.id, tok, 'titus')
    await db.increment_requests(cb.from_user.id)
    
    # Сохраняем в систему диалогов
    conv_id = await save_message(cb.from_user.id, 'assistant', resp_clean, 'titus')
    
    last_messages[cb.from_user.id] = {"text": resp_clean, "course": cname, "step": current_step}
    cleanup_cache(last_messages)  # Предотвращаем утечку памяти
    
    # Проверяем, нужно ли превью
    needs_preview, display_text = should_show_preview(resp_clean, max_length=3000)
    
    # Получаем клавиатуру с Конспектом и Посмотреть весь диалог
    keyboard = get_titus_keyboard(conv_id, len(resp_clean), cb.from_user.id)
    
    # Проверяем настройки голоса
    titus_settings = redis_db.get_titus_settings(cb.from_user.id) or {}
    voice_enabled = bool(titus_settings.get("voice_enabled", False))
    voice_gender = titus_settings.get("voice_gender", "male")
    
    if voice_enabled:
        # === ГОЛОСОВОЙ ОТВЕТ ===
        resp_for_tts = resp_clean
        resp_for_tts = re.sub(r"<[^>]+>", "", resp_for_tts)
        resp_for_tts = resp_for_tts.replace("**", "").replace("*", "")
        resp_for_tts = re.sub(r'[^\w\s,.!?;:—\-()«»"\'\n]+', '', resp_for_tts, flags=re.UNICODE)
        
        voice_tts = "onyx" if voice_gender == "male" else "shimmer"
        audio_path = await text_to_speech(resp_for_tts, voice=voice_tts)
        
        if audio_path:
            from aiogram.types import FSInputFile
            await cb.message.answer_voice(FSInputFile(audio_path), reply_markup=keyboard)
            try:
                os.remove(audio_path)
            except:
                pass
        else:
            # Fallback на текст
            await cb.message.answer(
                f"{display_text}\n\n<i>📓 Обучение • Шаг {current_step}/{total_steps}</i>",
                reply_markup=keyboard
            )
    else:
        # Текстовый ответ
        await cb.message.answer(
            f"{display_text}\n\n<i>📓 Обучение • Шаг {current_step}/{total_steps}</i>",
            reply_markup=keyboard
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
        await cb.message.answer("❌ Токены закончились!\n\n💎 Докупите в разделе 💠 Подписка", reply_markup=reply.main_kb(msg.from_user.id))
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
    
    # Проверяем настройки голоса для выбора промпта
    titus_settings_pre = redis_db.get_titus_settings(cb.from_user.id) or {}
    voice_enabled_pre = bool(titus_settings_pre.get("voice_enabled", False))
    base_prompt = TITUS_VOICE_BASE if voice_enabled_pre else TITUS_BASE
    
    sys = base_prompt + f"\n\nКУРС: {cname}\nШАГ: {current_step} из {total_steps}\n\n⚠️ Повтори и закрепи сложные темы: {topics_text}"
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": f"Разбери подробно темы, которые были сложными: {topics_text}"}]
    
    # STREAMING для повторения
    full_response = ""
    sentence_buffer = ""
    displayed_text = ""
    last_update = time.time()
    typing_phase = 0
    stream_msg = None
    
    try:
        async for chunk in ask_stream(msgs, model, max_tokens=4000):
            if not chunk:
                continue
            
            full_response += chunk
            sentence_buffer += chunk
            now = time.time()
            
            if typing_phase == 0 and len(full_response) > 20:
                typing_phase = 1
                timer_running = False
                timer_task.cancel()
                try:
                    await status.edit_text("✍️ Печатаю...")
                except:
                    pass
            
            if typing_phase == 1 and len(full_response) > 100:
                typing_phase = 2
                try:
                    await status.delete()
                except:
                    pass
                stream_msg = await cb.message.answer("_Печатаю..._", parse_mode=None)
            
            if typing_phase == 2 and stream_msg:
                if sentence_buffer.rstrip().endswith(('.', '!', '?', '\n\n')):
                    displayed_text += sentence_buffer
                    sentence_buffer = ""
                    
                    if now - last_update >= 0.5:
                        formatted = clean_response(displayed_text)
                        try:
                            await stream_msg.edit_text(formatted + " ▌")
                            last_update = now
                            await asyncio.sleep(0.3)
                        except:
                            pass
        
        displayed_text += sentence_buffer
        resp = full_response.strip()
        tok = calculate_tokens(msgs, resp)
        
        if stream_msg:
            try:
                await stream_msg.delete()
            except:
                pass
        if status and typing_phase < 2:
            try:
                await status.delete()
            except:
                pass
        
        resp_clean = clean_response(resp)
        
        await db.use_tokens_smart(cb.from_user.id, tok, 'titus')
        await db.increment_requests(cb.from_user.id)
        
        # Сохраняем в систему диалогов
        conv_id = await save_message(cb.from_user.id, 'assistant', resp_clean, 'titus')
        
        last_messages[cb.from_user.id] = {"text": resp_clean, "course": cname, "step": current_step}
        cleanup_cache(last_messages)  # Предотвращаем утечку памяти
        
        # Проверяем, нужно ли превью
        needs_preview, display_text = should_show_preview(resp_clean, max_length=3000)
        
        # Получаем клавиатуру с Конспектом и Посмотреть весь диалог
        keyboard = get_titus_keyboard(conv_id, len(resp_clean), cb.from_user.id)
        
        # Проверяем настройки голоса
        titus_settings = redis_db.get_titus_settings(cb.from_user.id) or {}
        voice_enabled = bool(titus_settings.get("voice_enabled", False))
        voice_gender = titus_settings.get("voice_gender", "male")
        
        if voice_enabled:
            # === ГОЛОСОВОЙ ОТВЕТ ===
            resp_for_tts = resp_clean
            resp_for_tts = re.sub(r"<[^>]+>", "", resp_for_tts)
            resp_for_tts = resp_for_tts.replace("**", "").replace("*", "")
            resp_for_tts = re.sub(r'[^\w\s,.!?;:—\-()«»"\'\n]+', '', resp_for_tts, flags=re.UNICODE)
            
            voice_tts = "onyx" if voice_gender == "male" else "shimmer"
            audio_path = await text_to_speech(resp_for_tts, voice=voice_tts)
            
            if audio_path:
                from aiogram.types import FSInputFile
                await cb.message.answer_voice(FSInputFile(audio_path), reply_markup=keyboard)
                try:
                    os.remove(audio_path)
                except:
                    pass
            else:
                # Fallback на текст
                await cb.message.answer(
                    f"{display_text}\n\n<i>📓 Обучение • Повторение сложных тем</i>",
                    reply_markup=keyboard
                )
        else:
            # Текстовый ответ
            await cb.message.answer(
                f"{display_text}\n\n<i>📓 Обучение • Повторение сложных тем</i>",
                reply_markup=keyboard
            )
    except Exception as e:
        timer_running = False
        timer_task.cancel()
        try:
            await status.delete()
        except:
            pass
        await cb.message.answer(f"❌ Ошибка: {str(e)[:200]}", reply_markup=reply.study_chat_kb())
