"""
Обработчик Silas (Психолог) - 100% автономный модуль
"""
from aiogram import Router, F
import re
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.postgres_db import set_silas_settings, get_silas_settings
from database import db, redis_db
from keyboards import reply as global_reply  # для bots_menu_kb()
from utils.openrouter import ask
from utils.tokens import calculate_tokens
from utils.memory import update_memory
from utils.voice import download_voice, transcribe_voice, text_to_speech
from aiogram.types import FSInputFile
import os
from utils.antiflood import ai_flood
from utils.telegraph import create_telegraph_page, make_preview
from utils.conversations import save_message, clean_response, should_show_preview, get_chat_button
from utils.status_manager import show_status
from utils.streaming import stream_response
from config import MIN_TOKENS
from loader import bot
from datetime import datetime
import asyncio
import base64

from . import keyboards as kb
from . import texts
from .prompts import SILAS_SYSTEM, SILAS_VOICE_RULES, MOODS
from .memory import build_memory_context

router = Router()

def md_to_html(text):
    """Конвертирует **bold** в <b>bold</b>"""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

class SilasSt(StatesGroup):
    menu = State()
    mood = State()
    custom = State()
    duration = State()
    session = State()

active_requests = {}
last_messages = {}

# Максимальное количество записей в кэше (для предотвращения утечек памяти)
MAX_CACHE_SIZE = 1000

def cleanup_cache(cache_dict: dict, max_size: int = MAX_CACHE_SIZE):
    """Очистка кэша при превышении лимита"""
    if len(cache_dict) > max_size:
        keys_to_remove = list(cache_dict.keys())[:len(cache_dict) - max_size + 100]
        for key in keys_to_remove:
            cache_dict.pop(key, None)

# ========== МЕНЮ ==========

async def _start_session_with_settings(msg: Message, state: FSMContext, duration: int, mood: str = '', voice_enabled: bool = False):
    """Вспомогательная функция для запуска сессии с заданными настройками"""
    try:
        print(f"🔵 [Silas] _start_session_with_settings: duration={duration}, mood={mood}, voice={voice_enabled}")
        
        # Нормализуем настроение: 'hard' из Web App → 'pain' в БД
        if mood == 'hard':
            mood = 'pain'
        
        # Сохраняем настроение в БД если указано
        if mood:
            await db.set_mood(msg.from_user.id, mood)
        
        # Сохраняем настройки в PostgreSQL для постоянного хранения
        await set_silas_settings(
            uid=msg.from_user.id,
            duration=duration,
            voice_enabled=voice_enabled
        )
        print(f"🔵 [Silas] Настройки сохранены в PostgreSQL")
        
        sid = await db.start_session(msg.from_user.id, duration)
        print(f"🔵 [Silas] Сессия создана: session_id={sid}")
        
        await state.set_state(SilasSt.session)
        await state.update_data(bot='silas', sid=sid, dur=duration, start=datetime.now().timestamp())
        print(f"🔵 [Silas] Состояние установлено: SilasSt.session")
        
        await db.clear_msgs(msg.from_user.id, 'silas')
        await db.reset_msg_counter(msg.from_user.id, 'silas')
        print(f"🔵 [Silas] История очищена, счётчик сброшен")
        
        await msg.answer(
            texts.START_SESSION.format(duration=duration),
            reply_markup=kb.psycho_chat_kb()
        )
        print(f"✅ [Silas] Сеанс успешно запущен для user_id={msg.from_user.id} с настройками из Web App")
    except Exception as e:
        print(f"❌ [Silas] ОШИБКА в _start_session_with_settings: {e}")
        import traceback
        traceback.print_exc()
        raise

@router.message(F.text.in_(["🛋️ Психолог"]))
async def silas_enter(msg: Message, state: FSMContext):
    cfg = await db.get_bot_cfg('silas')
    if not cfg['enabled']:
        await msg.answer(texts.BOT_DISABLED)
        return
    await state.set_state(SilasSt.menu)
    # Отправляем баннер вместо текста
    banner = FSInputFile("assets/banner_silas.png")
    await msg.answer_photo(
        photo=banner,
        reply_markup=kb.psycho_kb(msg.from_user.id)
    )

@router.message(SilasSt.menu, F.text == "🛋️ Начать сессию")
async def silas_start_session(msg: Message, state: FSMContext):
    try:
        print(f"🔵 [Silas] silas_start_session вызван: user_id={msg.from_user.id}")
        
        user_id = msg.from_user.id
        
        # Проверяем настройки из Web App
        cached_settings = redis_db.get_silas_settings_cache(user_id)
        
        if cached_settings and cached_settings.get('duration'):
            # Настройки есть — запускаем сессию сразу БЕЗ клавиатуры
            duration = cached_settings['duration']
            mood = cached_settings.get('mood', '')
            # Нормализация: 'hard' из Web App → 'pain' в БД
            if mood == 'hard':
                mood = 'pain'
            voice_enabled = cached_settings.get('voice_enabled', False)
            
            print(f"🔵 [Silas] Найдены настройки из Web App: duration={duration}, mood={mood}, voice={voice_enabled}")
            
            # Запустить сессию напрямую БЕЗ показа клавиатуры
            await _start_session_with_settings(msg, state, duration, mood, voice_enabled)
            return
        
        # Только если настроек НЕТ — показываем клавиатуру выбора
        print(f"🔵 [Silas] Настройки не найдены, показываем меню выбора")
        await state.set_state(SilasSt.duration)
        await msg.answer("Выбери длительность:", reply_markup=kb.psycho_dur_kb())
        print(f"✅ [Silas] Меню выбора длительности отправлено")
    except Exception as e:
        print(f"❌ [Silas] ОШИБКА в silas_start_session: {e}")
        import traceback
        traceback.print_exc()
        raise

# Обработчик "📔 Настроение" удалён - теперь используется Web App "🧘 Подготовка"

@router.message(SilasSt.menu, F.text == "📖 Как это работает")
async def silas_help(msg: Message):
    text = await db.get_text('help_psycho')
    if not text:
        text = "🛋️ <b>Психолог</b> — AI-помощник для поддержки и самопознания"
    await msg.answer(text)

@router.message(SilasSt.menu, F.text == "◀️ Назад")
async def silas_back(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("✨ Выберите помощника:", reply_markup=global_reply.bots_menu_kb())

@router.message(SilasSt.duration, F.text.in_({"15 минут", "30 минут", "60 минут"}))
async def silas_set_duration(msg: Message, state: FSMContext):
    try:
        print(f"🔵 [Silas] silas_set_duration вызван: user_id={msg.from_user.id}, text='{msg.text}'")
        dur_map = {"15 минут": 15, "30 минут": 30, "60 минут": 60}
        dur = dur_map.get(msg.text, 30)
        print(f"🔵 [Silas] Длительность: {dur} мин")
        
        sid = await db.start_session(msg.from_user.id, dur)
        print(f"🔵 [Silas] Сессия создана: session_id={sid}")
        
        await state.set_state(SilasSt.session)
        await state.update_data(bot='silas', sid=sid, dur=dur, start=datetime.now().timestamp())
        print(f"🔵 [Silas] Состояние установлено: SilasSt.session")
        
        await db.clear_msgs(msg.from_user.id, 'silas')
        await db.reset_msg_counter(msg.from_user.id, 'silas')
        print(f"🔵 [Silas] История очищена, счётчик сброшен")
        
        await msg.answer(
            texts.START_SESSION.format(duration=dur),
            reply_markup=kb.psycho_chat_kb()
        )
        print(f"✅ [Silas] Сеанс успешно запущен для user_id={msg.from_user.id}")
    except Exception as e:
        print(f"❌ [Silas] ОШИБКА в silas_set_duration: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка при запуске сеанса: {str(e)[:200]}")
        raise

@router.message(SilasSt.duration, F.text == "◀️ Назад к Психологу")
async def dur_back(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.menu)
    await msg.answer(texts.MENU_TEXT, reply_markup=kb.psycho_kb(msg.from_user.id))

@router.message(SilasSt.mood, F.text == "Хорошо")
async def mood_good(msg: Message, state: FSMContext):
    await db.set_mood(msg.from_user.id, 'good')
    await state.set_state(SilasSt.menu)
    await msg.answer(texts.MOOD_SAVED.format(mood="😊 Хорошо"), reply_markup=kb.psycho_kb(msg.from_user.id))

@router.message(SilasSt.mood, F.text == "Устал")
async def mood_tired(msg: Message, state: FSMContext):
    await db.set_mood(msg.from_user.id, 'tired')
    await state.set_state(SilasSt.menu)
    await msg.answer(texts.MOOD_SAVED.format(mood="😔 Устал"), reply_markup=kb.psycho_kb(msg.from_user.id))

@router.message(SilasSt.mood, F.text == "Тяжело")
async def mood_pain(msg: Message, state: FSMContext):
    await db.set_mood(msg.from_user.id, 'pain')
    await state.set_state(SilasSt.menu)
    await msg.answer(texts.MOOD_SAVED.format(mood="😰 Тяжело"), reply_markup=kb.psycho_kb(msg.from_user.id))

@router.message(SilasSt.mood, F.text == "✏️ Ваше настроение")
async def mood_custom(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.custom)
    await msg.answer(texts.CUSTOM_MOOD_INPUT)

@router.message(SilasSt.mood, F.text == "Статистика")
async def mood_stats(msg: Message):
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
async def mood_back(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.menu)
    await msg.answer(texts.MENU_TEXT, reply_markup=kb.psycho_kb(msg.from_user.id))

@router.message(SilasSt.custom)
async def custom_mood_input(msg: Message, state: FSMContext):
    words = len(msg.text.split())
    if words > 2:
        await msg.answer(texts.CUSTOM_MOOD_ERROR)
        return
    await db.set_mood(msg.from_user.id, 'custom', msg.text)
    await state.set_state(SilasSt.menu)
    await msg.answer(texts.MOOD_SAVED.format(mood=f"<b>{msg.text}</b>"), reply_markup=kb.psycho_kb(msg.from_user.id))

@router.message(SilasSt.session, F.text == "🛑 Завершить")
async def silas_stop(msg: Message, state: FSMContext):
    d = await state.get_data()
    await db.end_session(d.get('sid'))
    await state.set_state(SilasSt.menu)
    await msg.answer(
        texts.STOP_SESSION,
        reply_markup=kb.psycho_kb(msg.from_user.id)
    )

@router.message(SilasSt.session, F.text == "🗑 Очистить")
async def silas_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'silas')
    await msg.answer(texts.HISTORY_CLEARED)

@router.message(SilasSt.session, F.text == "⌛️ Отменить запрос")
async def silas_cancel(msg: Message):
    user_id = msg.from_user.id
    if user_id in active_requests and isinstance(active_requests[user_id], dict):
        active_requests[user_id]['cancelled'] = True
        # Удаляем сообщения
        try:
            if active_requests[user_id].get('kb_msg'):
                await active_requests[user_id]['kb_msg'].delete()
        except:
            pass
        try:
            if active_requests[user_id].get('status'):
                await active_requests[user_id]['status'].stop()
        except:
            pass
        # Удаляем сообщение пользователя
        try:
            await msg.delete()
        except:
            pass
        await msg.answer(texts.REQUEST_CANCELLED, reply_markup=kb.psycho_chat_kb())
    else:
        await msg.answer(texts.NO_ACTIVE_REQUEST, reply_markup=kb.psycho_chat_kb())

@router.callback_query(F.data == "silas:tg")
async def silas_telegraph(cb: CallbackQuery):
    user_id = cb.from_user.id
    if user_id not in last_messages:
        await cb.answer(texts.NO_TEXT_FOR_TELEGRAPH, show_alert=True)
        return
    await cb.answer(texts.TELEGRAPH_PUBLISHING)
    data = last_messages[user_id]
    text = data['text']
    url = await create_telegraph_page("🛋️ Психолог — Сеанс", text)
    if url:
        await cb.message.answer(
            texts.TELEGRAPH_PUBLISHED,
            reply_markup=kb.silas_msg_kb(has_telegraph=True)
        )
    else:
        await cb.message.answer(texts.TELEGRAPH_FAILED)

async def process_silas_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    allowed, error_msg = await ai_flood.check(msg.from_user.id)
    if not allowed:
        await msg.answer(error_msg)
        return
    
    remaining = await db.get_available_tokens(msg.from_user.id)
    if remaining < MIN_TOKENS:
        await msg.answer(texts.NO_TOKENS, reply_markup=global_reply.main_kb(msg.from_user.id))
        return
    
    model = await db.get_user_model(msg.from_user.id)
    
    d = await state.get_data()
    el = int((datetime.now().timestamp() - d['start']) / 60)
    rem = d['dur'] - el
    
    if rem <= 0:
        await db.end_session(d['sid'])
        await state.set_state(SilasSt.menu)
        await msg.answer(
            texts.SESSION_ENDED,
            reply_markup=kb.psycho_kb(msg.from_user.id)
        )
        return
    
    user_id = msg.from_user.id
    request_state = {'cancelled': False, 'kb_msg': None, 'status': None}
    active_requests[user_id] = request_state
    
    status_type = "photo" if image_b64 else "text"
    status = await show_status(bot, msg.chat.id, status_type)
    request_state['status'] = status
    
    resp = None
    
    try:
        if request_state['cancelled']:
            return
        
        s = await db.get_user_bot(msg.from_user.id, 'silas')
        
        # Получаем настроение из кэша Redis (приоритет) или из БД
        cached_settings = redis_db.get_silas_settings_cache(msg.from_user.id)
        voice_enabled = cached_settings.get('voice_enabled', False) if cached_settings else False
        if cached_settings and cached_settings.get('mood'):
            mood = cached_settings.get('mood')
            # Нормализация: 'hard' → 'pain'
            if mood == 'hard':
                mood = 'pain'
        else:
            # Получаем из БД
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
        
        mem = await db.get_memory(msg.from_user.id, 'silas')
        hist = await db.get_msgs(msg.from_user.id, 'silas')
        cnt = await db.inc_msg_counter(msg.from_user.id, 'silas')
        sys = SILAS_SYSTEM.format(mood=mood_text, duration=d['dur'], elapsed=el, remaining=rem, msg_count=cnt)
        sys += build_memory_context(mem)
        if voice_enabled:
            sys += "\n\n" + SILAS_VOICE_RULES
        
        if rem <= 5:
            sys += "\n\nОсталось мало времени — начинайте завершение."
        if cnt >= 20:
            sys += "\n\nСвяжите с предыдущими беседами."
            await db.reset_msg_counter(msg.from_user.id, 'silas')
        
        msgs = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": text}]
        
        if request_state['cancelled']:
            return
        
        if image_b64:
            resp, tok = await ask(msgs, model, image_b64)
            sent_msg = None
        else:
            resp, sent_msg = await stream_response(
                bot=bot,
                message=msg,
                messages=msgs,
                model=model,
                status_type="text"
            )
            tok = calculate_tokens(msgs, resp)
        
        if request_state['cancelled']:
            return
        
        # Очищаем ответ от служебных строк
        resp = clean_response(resp)
        
        await db.use_tokens_smart(msg.from_user.id, tok, 'silas')
        await db.increment_requests(msg.from_user.id)
        
        await db.add_msg(msg.from_user.id, 'silas', 'user', text)
        await db.add_msg(msg.from_user.id, 'silas', 'assistant', resp)
        
        # Сохраняем в систему диалогов
        model = await db.get_user_model(msg.from_user.id)
        await save_message(msg.from_user.id, 'user', text, 'silas', model)
        conv_id = await save_message(msg.from_user.id, 'assistant', resp, 'silas', model)
        
        # Обновляем память каждые 15 сообщений (экономия токенов)
        if cnt % 15 == 0 or cnt == 1:
            asyncio.create_task(update_memory(msg.from_user.id, 'silas', text, resp))
        
        last_messages[user_id] = {"text": resp}
        cleanup_cache(last_messages)  # Предотвращаем утечку памяти
        
    finally:
        if status:
            await status.stop()
        active_requests.pop(user_id, None)
    
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
            # Удаляем текстовое сообщение от стриминга
            if sent_msg:
                try:
                    await sent_msg.delete()
                except Exception:
                    pass
            
            # Используем мужской голос по умолчанию (как у Луки)
            voice_tts = "onyx"  # Мужской голос OpenAI TTS
            
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
                    except:
                        pass
                else:
                    # Fallback на текст если TTS не сработал
                    await msg.answer(f"{display_text}{footer}", reply_markup=keyboard)
                    
            except Exception as e:
                print(f"TTS error in Silas: {e}")
                # Fallback на текст
                await msg.answer(f"{display_text}{footer}", reply_markup=keyboard)
        else:
            # === ТЕКСТОВЫЙ ОТВЕТ ===
            # Редактируем существующее сообщение вместо отправки нового
            final_text = f"{display_text}{footer}"
            
            if sent_msg:
                try:
                    await sent_msg.edit_text(final_text, reply_markup=keyboard, parse_mode="HTML")
                except Exception:
                    # Если не удалось отредактировать - отправляем новое
                    await msg.answer(final_text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await msg.answer(final_text, reply_markup=keyboard, parse_mode="HTML")

@router.message(SilasSt.session, F.text)
async def silas_text(msg: Message, state: FSMContext):
    await process_silas_message(msg, state, msg.text)

@router.message(SilasSt.session, F.voice)
async def silas_voice(msg: Message, state: FSMContext):
    status = await show_status(bot, msg.chat.id, "voice")
    try:
        fp = await download_voice(bot, msg.voice.file_id)
        text = await transcribe_voice(fp)
        if not text:
            await msg.answer(texts.ERROR_NO_RECOGNITION)
            return
    except Exception as e:
        await msg.answer(f"❌ {e}")
        return
    finally:
        if status:
            await status.stop()
    await process_silas_message(msg, state, text)

@router.message(SilasSt.session, F.photo)
async def silas_photo(msg: Message, state: FSMContext):
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
    await process_silas_message(msg, state, msg.caption or "Опишите что вы видите", b64)
