"""
Обработчик Silas (Психолог) - 100% автономный модуль
Оптимизирован для 1000+ одновременных пользователей
Использует централизованное ядро core/
"""
import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from config import MIN_STARS
from core import api_queue, rate_limiter
from core.cache import LRUCache
from core.config import MSG_RATE_LIMITED
from database import postgres_db as db, redis_db
from database.postgres_db import get_silas_settings, set_silas_settings
from keyboards import reply as global_reply
from loader import bot
from utils.antiflood import ai_flood
from utils.balance_guard import ensure_balance
from utils.conversations import (
    clean_response,
    get_chat_button,
    save_message,
    should_show_preview,
)
from utils.memory import update_memory
from utils.openrouter import ask
from utils.stars import calculate_stars
from utils.status_manager import show_status
from utils.streaming import stream_response
from utils.telegraph import create_telegraph_page
from utils.voice import download_voice, text_to_speech, transcribe_voice

from . import keyboards as kb
from . import texts
from .memory import build_memory_context
from .prompts import SILAS_SYSTEM, SILAS_VOICE_RULES

# Настройка логгера
logger = logging.getLogger(__name__)

router = Router()


# ═══════════════════════════════════════
# ЛОКАЛЬНЫЕ КЭШИ (используют core.LRUCache)
# ═══════════════════════════════════════

# Кэш активных запросов
active_requests: LRUCache = LRUCache(max_size=500, default_ttl=300)

# Кэш последних сообщений для Telegraph
last_messages: LRUCache = LRUCache(max_size=1000, default_ttl=3600)


# ═══════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════

def md_to_html(text: str) -> str:
    """Конвертирует **bold** в <b>bold</b>"""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


async def safe_background_task(coro, task_name: str = "background") -> None:
    """Безопасный запуск фоновой задачи"""
    try:
        await coro
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"[{task_name}] Error: {e}")


# ═══════════════════════════════════════
# СОСТОЯНИЯ FSM
# ═══════════════════════════════════════

class SilasSt(StatesGroup):
    menu = State()
    mood = State()
    custom = State()
    duration = State()
    session = State()


# ═══════════════════════════════════════
# ОСНОВНЫЕ ОБРАБОТЧИКИ
# ═══════════════════════════════════════

async def _start_session_with_settings(
    msg: Message, 
    state: FSMContext, 
    duration: int, 
    mood: str = '', 
    voice_enabled: bool = False
) -> None:
    """Вспомогательная функция для запуска сессии с заданными настройками"""
    user_id = msg.from_user.id
    
    try:
        logger.info(f"[Silas] Starting session: user={user_id}, duration={duration}, mood={mood}, voice={voice_enabled}")
        
        # Нормализуем настроение: 'hard' из Web App → 'pain' в БД
        if mood == 'hard':
            mood = 'pain'
        
        # Сохраняем настроение в БД если указано
        if mood:
            await db.set_mood(user_id, mood)
        
        # Сохраняем настройки в PostgreSQL
        await set_silas_settings(
            uid=user_id,
            duration=duration,
            voice_enabled=voice_enabled
        )
        
        sid = await db.start_session(user_id, duration)
        logger.info(f"[Silas] Session created: session_id={sid}")
        
        await state.set_state(SilasSt.session)
        await state.update_data(bot='silas', sid=sid, dur=duration, start=datetime.now().timestamp())
        
        await db.clear_msgs(user_id, 'silas')
        await db.reset_msg_counter(user_id, 'silas')
        
        await msg.answer(
            texts.START_SESSION.format(duration=duration),
            reply_markup=kb.psycho_chat_kb()
        )
        logger.info(f"[Silas] Session started successfully: user={user_id}")
        
    except Exception as e:
        logger.exception(f"[Silas] Error in _start_session_with_settings: {e}")
        raise


@router.message(F.text.in_(["🛋️ Психолог"]))
async def silas_enter(msg: Message, state: FSMContext) -> None:
    cfg = await db.get_bot_cfg('silas')
    if not cfg['enabled']:
        await msg.answer(texts.BOT_DISABLED)
        return
    await state.set_state(SilasSt.menu)
    banner = FSInputFile("assets/banner_silas.png")
    await msg.answer_photo(
        photo=banner,
        reply_markup=kb.psycho_kb(msg.from_user.id)
    )


@router.message(SilasSt.menu, F.text == "🛋️ Начать сессию")
async def silas_start_session(msg: Message, state: FSMContext) -> None:
    user_id = msg.from_user.id
    
    try:
        logger.debug(f"[Silas] silas_start_session: user_id={user_id}")
        
        # Проверяем настройки из Web App
        cached_settings = redis_db.get_silas_settings_cache(user_id)
        
        if cached_settings and cached_settings.get('duration'):
            duration = cached_settings['duration']
            mood = cached_settings.get('mood', '')
            if mood == 'hard':
                mood = 'pain'
            voice_enabled = cached_settings.get('voice_enabled', False)
            
            logger.debug(f"[Silas] Using cached settings: duration={duration}, mood={mood}, voice={voice_enabled}")
            await _start_session_with_settings(msg, state, duration, mood, voice_enabled)
            return
        
        # Только если настроек НЕТ — показываем клавиатуру выбора
        logger.debug(f"[Silas] No cached settings, showing duration menu")
        await state.set_state(SilasSt.duration)
        await msg.answer("Выбери длительность:", reply_markup=kb.psycho_dur_kb())
        
    except Exception as e:
        logger.exception(f"[Silas] Error in silas_start_session: {e}")
        raise


@router.message(SilasSt.menu, F.text == "📖 Как это работает?")
async def silas_help(msg: Message) -> None:
    text = await db.get_text('help_psycho')
    if not text:
        text = "🛋️ <b>Психолог</b> — AI-помощник для поддержки и самопознания"
    await msg.answer(text)


@router.message(SilasSt.menu, F.text == "◀️ Назад")
async def silas_back(msg: Message, state: FSMContext) -> None:
    await state.clear()
    await msg.answer("✨ Выберите помощника:", reply_markup=global_reply.bots_menu_kb())


@router.message(SilasSt.duration, F.text.in_({"15 минут", "30 минут", "60 минут"}))
async def silas_set_duration(msg: Message, state: FSMContext) -> None:
    user_id = msg.from_user.id
    
    try:
        logger.debug(f"[Silas] silas_set_duration: user_id={user_id}, text='{msg.text}'")
        dur_map = {"15 минут": 15, "30 минут": 30, "60 минут": 60}
        dur = dur_map.get(msg.text, 30)
        
        sid = await db.start_session(user_id, dur)
        logger.debug(f"[Silas] Session created: session_id={sid}")
        
        await state.set_state(SilasSt.session)
        await state.update_data(bot='silas', sid=sid, dur=dur, start=datetime.now().timestamp())
        
        await db.clear_msgs(user_id, 'silas')
        await db.reset_msg_counter(user_id, 'silas')
        
        await msg.answer(
            texts.START_SESSION.format(duration=dur),
            reply_markup=kb.psycho_chat_kb()
        )
        logger.info(f"[Silas] Session started: user={user_id}")
        
    except Exception as e:
        logger.exception(f"[Silas] Error in silas_set_duration: {e}")
        await msg.answer(f"❌ Ошибка при запуске сеанса: {str(e)[:200]}")
        raise


@router.message(SilasSt.duration, F.text == "◀️ Назад к Психологу")
async def dur_back(msg: Message, state: FSMContext) -> None:
    await state.set_state(SilasSt.menu)
    await msg.answer(texts.MENU_TEXT, reply_markup=kb.psycho_kb(msg.from_user.id))


# ═══════════════════════════════════════
# ОБРАБОТЧИКИ НАСТРОЕНИЯ
# ═══════════════════════════════════════

@router.message(SilasSt.mood, F.text == "Хорошо")
async def mood_good(msg: Message, state: FSMContext) -> None:
    await db.set_mood(msg.from_user.id, 'good')
    await state.set_state(SilasSt.menu)
    await msg.answer(texts.MOOD_SAVED.format(mood="😊 Хорошо"), reply_markup=kb.psycho_kb(msg.from_user.id))


@router.message(SilasSt.mood, F.text == "Устал")
async def mood_tired(msg: Message, state: FSMContext) -> None:
    await db.set_mood(msg.from_user.id, 'tired')
    await state.set_state(SilasSt.menu)
    await msg.answer(texts.MOOD_SAVED.format(mood="😔 Устал"), reply_markup=kb.psycho_kb(msg.from_user.id))


@router.message(SilasSt.mood, F.text == "Тяжело")
async def mood_pain(msg: Message, state: FSMContext) -> None:
    await db.set_mood(msg.from_user.id, 'pain')
    await state.set_state(SilasSt.menu)
    await msg.answer(texts.MOOD_SAVED.format(mood="😰 Тяжело"), reply_markup=kb.psycho_kb(msg.from_user.id))


@router.message(SilasSt.mood, F.text == "✏️ Ваше настроение")
async def mood_custom(msg: Message, state: FSMContext) -> None:
    await state.set_state(SilasSt.custom)
    await msg.answer(texts.CUSTOM_MOOD_INPUT)


@router.message(SilasSt.mood, F.text == "Статистика")
async def mood_stats(msg: Message) -> None:
    s = await db.get_mood_stats(msg.from_user.id)
    total = s['good'] + s['tired'] + s['pain']
    await msg.answer(
        texts.MOOD_STATS.format(
            good=s['good'],
            tired=s['tired'],
            pain=s['pain'],
            total=total
        )
    )


@router.message(SilasSt.mood, F.text == "◀️ Назад к Психологу")
async def mood_back(msg: Message, state: FSMContext) -> None:
    await state.set_state(SilasSt.menu)
    await msg.answer(texts.MENU_TEXT, reply_markup=kb.psycho_kb(msg.from_user.id))


@router.message(SilasSt.custom)
async def custom_mood_input(msg: Message, state: FSMContext) -> None:
    words = len(msg.text.split())
    if words > 2:
        await msg.answer(texts.CUSTOM_MOOD_ERROR)
        return
    await db.set_mood(msg.from_user.id, 'custom', msg.text)
    await state.set_state(SilasSt.menu)
    await msg.answer(texts.MOOD_SAVED.format(mood=f"<b>{msg.text}</b>"), reply_markup=kb.psycho_kb(msg.from_user.id))


# ═══════════════════════════════════════
# ОБРАБОТЧИКИ СЕССИИ
# ═══════════════════════════════════════

@router.message(SilasSt.session, F.text == "🛑 Завершить")
async def silas_stop(msg: Message, state: FSMContext) -> None:
    d = await state.get_data()
    await db.end_session(d.get('sid'))
    await state.set_state(SilasSt.menu)
    await msg.answer(
        texts.STOP_SESSION,
        reply_markup=kb.psycho_kb(msg.from_user.id)
    )


@router.message(SilasSt.session, F.text == "🗑 Очистить")
async def silas_clear(msg: Message) -> None:
    await db.clear_msgs(msg.from_user.id, 'silas')
    await msg.answer(texts.HISTORY_CLEARED)


@router.message(SilasSt.session, F.text == "⌛️ Отменить запрос")
async def silas_cancel(msg: Message) -> None:
    user_id = msg.from_user.id
    request_state = await active_requests.get(user_id)
    
    if request_state and isinstance(request_state, dict):
        request_state['cancelled'] = True
        
        # Удаляем сообщения
        if request_state.get('kb_msg'):
            try:
                await request_state['kb_msg'].delete()
            except Exception as e:
                logger.debug(f"Failed to delete kb_msg: {e}")
        
        if request_state.get('status'):
            try:
                await request_state['status'].stop()
            except Exception as e:
                logger.debug(f"Failed to stop status: {e}")
        
        # Удаляем сообщение пользователя
        try:
            await msg.delete()
        except Exception as e:
            logger.debug(f"Failed to delete user msg: {e}")
        
        await msg.answer(texts.REQUEST_CANCELLED, reply_markup=kb.psycho_chat_kb())
    else:
        await msg.answer(texts.NO_ACTIVE_REQUEST, reply_markup=kb.psycho_chat_kb())


@router.callback_query(F.data == "silas:tg")
async def silas_telegraph(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    data = await last_messages.get(user_id)
    
    if not data:
        await cb.answer(texts.NO_TEXT_FOR_TELEGRAPH, show_alert=True)
        return
    
    await cb.answer(texts.TELEGRAPH_PUBLISHING)
    text = data['text']
    url = await create_telegraph_page("🛋️ Психолог — Сеанс", text)
    
    if url:
        await cb.message.answer(
            texts.TELEGRAPH_PUBLISHED,
            reply_markup=kb.silas_msg_kb(has_telegraph=True)
        )
    else:
        await cb.message.answer(texts.TELEGRAPH_FAILED)


# ═══════════════════════════════════════
# ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ
# ═══════════════════════════════════════

async def process_silas_message(
    msg: Message, 
    state: FSMContext, 
    text: str, 
    image_b64: Optional[str] = None
) -> None:
    """Основной обработчик сообщений с оптимизацией для нагрузки"""
    user_id = msg.from_user.id
    
    # Rate limiting через core.rate_limiter
    allowed, wait_time = await rate_limiter.check(user_id)
    if not allowed:
        await msg.answer(MSG_RATE_LIMITED.format(seconds=wait_time))
        return
    
    # Antiflood проверка
    allowed, error_msg = await ai_flood.check(user_id)
    if not allowed:
        await msg.answer(error_msg)
        return
    
    # Проверка баланса
    if not await ensure_balance(msg, required=MIN_STARS):
        return
    
    model = await db.get_user_model(user_id)
    
    d = await state.get_data()
    el = int((datetime.now().timestamp() - d['start']) / 60)
    rem = d['dur'] - el
    
    if rem <= 0:
        await db.end_session(d['sid'])
        await state.set_state(SilasSt.menu)
        await msg.answer(
            texts.SESSION_ENDED,
            reply_markup=kb.psycho_kb(user_id)
        )
        return
    
    request_state = {'cancelled': False, 'kb_msg': None, 'status': None}
    await active_requests.set(user_id, request_state)
    
    status = None
    resp = None
    
    try:
        if request_state['cancelled']:
            return
        
        s = await db.get_user_bot(user_id, 'silas')
        
        # Получаем настроение из кэша Redis (приоритет) или из БД
        cached_settings = redis_db.get_silas_settings_cache(user_id)
        voice_enabled = cached_settings.get('voice_enabled', False) if cached_settings else False
        
        if cached_settings and cached_settings.get('mood'):
            mood = cached_settings.get('mood')
            if mood == 'hard':
                mood = 'pain'
        else:
            mood = s.get('mood') or s.get('custom_mood') or 'не указано'
        
        # Преобразуем mood для промпта
        mood_descriptions = {
            'good': 'хорошее — клиент в ресурсе',
            'tired': 'усталость — нужен бережный подход',
            'hard': 'тяжело — приоритет на поддержку',
            'pain': 'тяжело — приоритет на поддержку',
            '': 'не указано'
        }
        mood_text = mood_descriptions.get(mood, 'не указано')
        
        mem = await db.get_memory(user_id, 'silas')
        hist = await db.get_msgs(user_id, 'silas')
        cnt = await db.inc_msg_counter(user_id, 'silas')
        
        sys = SILAS_SYSTEM.format(mood=mood_text, duration=d['dur'], elapsed=el, remaining=rem, msg_count=cnt)
        sys += build_memory_context(mem)
        
        if voice_enabled:
            sys += "\n\n" + SILAS_VOICE_RULES
        
        if rem <= 5:
            sys += "\n\nОсталось мало времени — начинайте завершение."
        if cnt >= 20:
            sys += "\n\nСвяжите с предыдущими беседами."
            await db.reset_msg_counter(user_id, 'silas')
        
        msgs = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": text}]
        
        if request_state['cancelled']:
            return
        
        # Вызов API через core.api_queue
        if image_b64:
            status = await show_status(bot, msg.chat.id, "photo")
            request_state['status'] = status
            result = await api_queue.execute(ask, msgs, model, image_b64)
            if result is None:
                await msg.answer("⚠️ Запрос занял слишком много времени. Попробуй ещё раз.")
                return
            resp, stars_used = result
            sent_msg = None
        else:
            result = await api_queue.execute(
                stream_response,
                bot=bot,
                message=msg,
                messages=msgs,
                model=model,
                status_type="text"
            )
            if result is None:
                await msg.answer("⚠️ Запрос занял слишком много времени. Попробуй ещё раз.")
                return
            resp, sent_msg = result
            stars_used = calculate_stars(msgs, resp)
        
        if request_state['cancelled']:
            return
        
        # Очищаем ответ от служебных строк
        resp = clean_response(resp)
        
        await db.use_stars_smart(user_id, stars_used, 'silas')
        await db.increment_requests(user_id)
        
        await db.add_msg(user_id, 'silas', 'user', text)
        await db.add_msg(user_id, 'silas', 'assistant', resp)
        
        # Сохраняем в систему диалогов
        model = await db.get_user_model(user_id)
        await save_message(user_id, 'user', text, 'silas', model)
        conv_id = await save_message(user_id, 'assistant', resp, 'silas', model)
        
        # Обновляем память каждые 15 сообщений (экономия звёзд)
        if cnt % 15 == 0 or cnt == 1:
            asyncio.create_task(safe_background_task(
                update_memory(user_id, 'silas', text, resp),
                "memory_update"
            ))
        
        await last_messages.set(user_id, {"text": resp})
        
    except Exception as e:
        logger.exception(f"[Silas] Error in process_silas_message: {e}")
        raise
    finally:
        if status:
            await status.stop()
        await active_requests.delete(user_id)
    
    if resp:
        resp_html = md_to_html(resp)
        footer = texts.RESPONSE_FOOTER
        
        # Проверяем, нужно ли превью
        needs_preview, display_text = should_show_preview(resp_html, max_length=3000)
        
        if needs_preview:
            display_text = md_to_html(display_text)
        
        # Получаем кнопку для просмотра диалога
        keyboard = get_chat_button(conv_id, len(resp_html))
        
        if voice_enabled:
            # === ГОЛОСОВОЙ ОТВЕТ ===
            if sent_msg:
                try:
                    await sent_msg.delete()
                except Exception as e:
                    logger.debug(f"Failed to delete sent_msg: {e}")
            
            voice_tts = "onyx"
            
            # Очищаем текст от markdown для TTS
            resp_clean = resp.replace("**", "").replace("*", "").replace("#", "")
            resp_clean = re.sub(r'[^\w\s,.!?;:—\-()«»"\'\n]+', '', resp_clean, flags=re.UNICODE)
            
            try:
                audio_path = await text_to_speech(resp_clean, voice=voice_tts)
                
                if audio_path:
                    voice_file = FSInputFile(audio_path)
                    await msg.answer_voice(voice_file, reply_markup=keyboard)
                    
                    # Удаляем временный файл
                    try:
                        os.remove(audio_path)
                    except Exception as e:
                        logger.debug(f"Failed to remove temp audio: {e}")
                else:
                    await msg.answer(f"{display_text}{footer}", reply_markup=keyboard)
                    
            except Exception as e:
                logger.error(f"TTS error in Silas: {e}")
                await msg.answer(f"{display_text}{footer}", reply_markup=keyboard)
        else:
            # === ТЕКСТОВЫЙ ОТВЕТ ===
            final_text = f"{display_text}{footer}"
            
            if sent_msg:
                try:
                    await sent_msg.edit_text(final_text, reply_markup=keyboard, parse_mode="HTML")
                except Exception as e:
                    logger.debug(f"Failed to edit sent_msg: {e}")
                    await msg.answer(final_text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await msg.answer(final_text, reply_markup=keyboard, parse_mode="HTML")


@router.message(SilasSt.session, F.text)
async def silas_text(msg: Message, state: FSMContext) -> None:
    await process_silas_message(msg, state, msg.text)


@router.message(SilasSt.session, F.voice)
async def silas_voice(msg: Message, state: FSMContext) -> None:
    status = await show_status(bot, msg.chat.id, "voice")
    try:
        fp = await download_voice(bot, msg.voice.file_id)
        text = await transcribe_voice(fp)
        if not text:
            await msg.answer(texts.ERROR_NO_RECOGNITION)
            return
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await msg.answer(f"❌ {e}")
        return
    finally:
        if status:
            await status.stop()
    await process_silas_message(msg, state, text)


@router.message(SilasSt.session, F.photo)
async def silas_photo(msg: Message, state: FSMContext) -> None:
    import base64
    
    status = await show_status(bot, msg.chat.id, "photo")
    try:
        photo = msg.photo[-1]
        file = await bot.get_file(photo.file_id)
        data = await bot.download_file(file.file_path)
        b64 = base64.b64encode(data.read()).decode()
    except Exception as e:
        logger.error(f"Photo processing error: {e}")
        await msg.answer(f"❌ {e}")
        return
    finally:
        if status:
            await status.stop()
    await process_silas_message(msg, state, msg.caption or "Опишите что вы видите", b64)
