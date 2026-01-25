"""
Luca (Soul AI) - 100% автономный модуль
Оптимизирован для 1000+ одновременных пользователей
Использует централизованное ядро core/
"""
import asyncio
import base64
import logging
import os
import re

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from core import api_queue, rate_limiter
from core.cache import LRUCache
from core.config import MSG_RATE_LIMITED
from database import postgres_db as db, redis_db
from handlers.ai_buttons import (
    CANCEL_REQUEST_BTN,
    cancel_user_request,
    clear_cancel,
    get_waiting_kb,
    is_cancelled,
)
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
from utils.markdown import md_to_html
from utils.memory import update_memory
from utils.openrouter import ask
from utils.stars import calculate_stars
from utils.status_manager import show_status
from utils.streaming import stream_response
from utils.telegraph import create_telegraph_page
from utils.voice import download_voice, text_to_speech, transcribe_voice

# Локальные импорты модуля (всё внутри handlers/luca/)
from . import config as luca_config
from . import keyboards as kb
from . import texts
from .memory import (
    CHAR_NAMES,
    CHARS,
    build_memory_context,
    get_user_memory,
)
from .prompts import LUCA_VOICE_RULES, LUCA_VOICE_STYLE_MIND, LUCA_VOICE_STYLE_SOUL

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
# КОНФИГУРАЦИЯ ИЗ ЛОКАЛЬНОГО CONFIG
# ═══════════════════════════════════════

MIN_STARS = luca_config.MIN_STARS
VOICE_MAP = luca_config.VOICE_MAP


# ═══════════════════════════════════════
# СОСТОЯНИЯ FSM
# ═══════════════════════════════════════

class LukaSt(StatesGroup):
    menu = State()
    chat = State()
    char = State()
    voice_choose = State()
    voice_chat = State()


# ═══════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════

def get_user_settings(user_id: int) -> dict:
    """Получить настройки пользователя из Redis"""
    return redis_db.get_luca_settings(user_id)


async def safe_background_task(coro, task_name: str = "background") -> None:
    """Безопасный запуск фоновой задачи с логированием ошибок"""
    try:
        await coro
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"[{task_name}] Error: {e}")


def create_safe_task(coro, task_name: str = "background"):
    """Создать фоновую задачу с отслеживанием ошибок"""
    return asyncio.create_task(safe_background_task(coro, task_name))


# ═══════════════════════════════════════
# МЕНЮ
# ═══════════════════════════════════════

@router.message(F.text == "✨ Soul Чат")
async def luka_enter(msg: Message, state: FSMContext) -> None:
    cfg = await db.get_bot_cfg('luca')
    if not cfg['enabled']:
        await msg.answer(texts.BOT_DISABLED)
        return
    await state.set_state(LukaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_key = s.get('character', 'soul')
    char_name = CHAR_NAMES.get(char_key, '🕊 Душа')
    
    # Отправляем баннер с проверкой существования
    banner_path = "assets/banner_dialog.png"
    if os.path.exists(banner_path):
        try:
            banner = FSInputFile(banner_path)
            await msg.answer_photo(
                photo=banner,
                reply_markup=kb.dialog_kb(msg.from_user.id)
            )
        except Exception as e:
            logger.warning(f"Failed to send banner: {e}")
            await msg.answer(
                texts.MENU_TEXT.format(char_name=char_name),
                reply_markup=kb.dialog_kb(msg.from_user.id)
            )
    else:
        await msg.answer(
            texts.MENU_TEXT.format(char_name=char_name),
            reply_markup=kb.dialog_kb(msg.from_user.id)
        )


@router.message(LukaSt.menu, F.text == "💬 Начать")
async def luka_start_chat(msg: Message, state: FSMContext) -> None:
    await db.clear_msgs(msg.from_user.id, 'luca')
    await db.reset_msg_counter(msg.from_user.id, 'luca')
    await state.set_state(LukaSt.chat)
    await msg.answer(
        texts.CHAT_STARTED,
        reply_markup=kb.dialog_chat_kb()
    )


@router.message(LukaSt.menu, F.text == "🔄 Режим")
async def luka_char_menu(msg: Message, state: FSMContext) -> None:
    await state.set_state(LukaSt.char)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_key = s.get('character', 'soul')
    char_name = CHAR_NAMES.get(char_key, '🕊 Душа')
    await msg.answer(
        texts.CHAR_SELECT.format(char_name=char_name),
        reply_markup=kb.dialog_char_kb()
    )


@router.message(LukaSt.menu, F.text == "🧹 Очистить")
async def luka_clear(msg: Message) -> None:
    await db.clear_msgs(msg.from_user.id, 'luca')
    await msg.answer(texts.HISTORY_CLEARED)


@router.message(LukaSt.menu, F.text == "◀️ Назад")
async def luka_back(msg: Message, state: FSMContext) -> None:
    await state.clear()
    await msg.answer("🫧 Выберите бота:", reply_markup=global_reply.bots_menu_kb())


# ═══════════════════════════════════════
# ХАРАКТЕР
# ═══════════════════════════════════════

@router.message(LukaSt.char, F.text == "🕊 Душа")
async def char_soul(msg: Message, state: FSMContext) -> None:
    await db.set_char(msg.from_user.id, 'soul')
    await state.set_state(LukaSt.menu)
    await msg.answer(
        texts.SOUL_SET,
        reply_markup=kb.dialog_kb(msg.from_user.id)
    )


@router.message(LukaSt.char, F.text == "💡 Разум")
async def char_mind(msg: Message, state: FSMContext) -> None:
    await db.set_char(msg.from_user.id, 'mind')
    await state.set_state(LukaSt.menu)
    await msg.answer(
        texts.MIND_SET,
        reply_markup=kb.dialog_kb(msg.from_user.id)
    )


@router.message(LukaSt.char, F.text == "🎤 Голос")
async def char_voice(msg: Message, state: FSMContext) -> None:
    """Вход в голосовой режим"""
    voice_gender = await db.get_voice_gender(msg.from_user.id, 'luca')
    
    if voice_gender:
        await state.set_state(LukaSt.voice_chat)
        gender_name = "👨 Мужской" if voice_gender == "male" else "👩 Женский"
        await msg.answer(
            texts.VOICE_ACTIVATED.format(gender_name=gender_name),
            reply_markup=kb.voice_chat_kb()
        )
    else:
        await state.set_state(LukaSt.voice_choose)
        await msg.answer(
            texts.VOICE_CHOOSE,
            reply_markup=kb.voice_gender_kb()
        )


@router.message(LukaSt.char, F.text == "◀️ Назад к Диалогу")
async def char_back(msg: Message, state: FSMContext) -> None:
    await state.set_state(LukaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_key = s.get('character', 'soul')
    char_name = CHAR_NAMES.get(char_key, '🕊 Душа')
    await msg.answer(
        f"🫧 <b>Soul AI</b>\n\n🪞 Режим: {char_name}",
        reply_markup=kb.dialog_kb(msg.from_user.id)
    )


# ═══════════════════════════════════════
# ГОЛОСОВОЙ РЕЖИМ
# ═══════════════════════════════════════

@router.callback_query(F.data.startswith("voice:gender:"))
async def voice_gender_selected(cb: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора голоса"""
    gender = cb.data.split(":")[2]
    
    await db.set_voice_gender(cb.from_user.id, gender, 'luca')
    await state.set_state(LukaSt.voice_chat)
    
    gender_name = "👨 Мужской" if gender == "male" else "👩 Женский"
    await cb.message.edit_text(
        f"✅ <b>Голос выбран: {gender_name}</b>\n\n"
        f"🎤 Голосовой режим активирован!\n\n"
        f"💬 Отправь голосовое сообщение или напиши текст — я отвечу голосом!"
    )
    
    await cb.message.answer(
        texts.VOICE_READY,
        reply_markup=kb.voice_chat_kb()
    )


@router.message(LukaSt.voice_chat, F.text == "🛑 Завершить")
async def voice_stop(msg: Message, state: FSMContext) -> None:
    """Выход из голосового режима"""
    await state.set_state(LukaSt.char)
    await msg.answer(
        texts.VOICE_ENDED,
        reply_markup=kb.dialog_char_kb()
    )


@router.message(LukaSt.voice_chat, F.text == "🔄 Сменить голос")
async def voice_change_gender(msg: Message, state: FSMContext) -> None:
    """Смена голоса"""
    await state.set_state(LukaSt.voice_choose)
    current_gender = await db.get_voice_gender(msg.from_user.id, 'luca')
    current_name = "👨 Мужской" if current_gender == "male" else "👩 Женский"
    
    await msg.answer(
        texts.VOICE_CHANGE.format(current_name=current_name),
        reply_markup=kb.voice_gender_kb()
    )


@router.message(LukaSt.voice_chat, F.text == CANCEL_REQUEST_BTN)
async def voice_cancel(msg: Message, state: FSMContext) -> None:
    """Отмена запроса в голосовом режиме"""
    user_id = msg.from_user.id
    cancel_user_request(user_id)
    
    request_state = await active_requests.get(user_id)
    if request_state and isinstance(request_state, dict):
        request_state['cancelled'] = True
        if request_state.get('status'):
            try:
                await request_state['status'].stop()
            except Exception as e:
                logger.debug(f"Failed to stop status: {e}")
    
    try:
        await msg.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    
    await state.set_state(LukaSt.char)
    await msg.answer("❌ Запрос отменён", reply_markup=kb.dialog_char_kb())


# ═══════════════════════════════════════
# ЧАТ
# ═══════════════════════════════════════

@router.message(LukaSt.chat, F.text == "🛑 Завершить")
async def luka_stop(msg: Message, state: FSMContext) -> None:
    await state.set_state(LukaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_key = s.get('character', 'soul')
    char_name = CHAR_NAMES.get(char_key, '🕊 Душа')
    await msg.answer(
        texts.CHAT_ENDED.format(char_name=char_name),
        reply_markup=kb.dialog_kb(msg.from_user.id)
    )


@router.message(LukaSt.chat, F.text == CANCEL_REQUEST_BTN)
async def luka_cancel(msg: Message, state: FSMContext) -> None:
    """Отмена запроса в текстовом чате"""
    user_id = msg.from_user.id
    cancel_user_request(user_id)
    
    request_state = await active_requests.get(user_id)
    if request_state and isinstance(request_state, dict):
        request_state['cancelled'] = True
        if request_state.get('kb_msg'):
            try:
                await request_state['kb_msg'].delete()
            except (TelegramBadRequest, TelegramForbiddenError):
                pass
        if request_state.get('status'):
            try:
                await request_state['status'].stop()
            except Exception as e:
                logger.debug(f"Failed to stop status: {e}")
    
    try:
        await msg.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    
    await state.set_state(LukaSt.menu)
    await msg.answer("❌ Запрос отменён", reply_markup=kb.dialog_kb(user_id))


@router.callback_query(F.data == "luca:tg")
async def luka_telegraph(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    
    data = await last_messages.get(user_id)
    if not data:
        await cb.answer(texts.NO_TEXT_FOR_TELEGRAPH, show_alert=True)
        return
    
    await cb.answer(texts.PUBLISHING_TELEGRAPH)
    
    text = data['text']
    char = data.get('char', 'Soul AI')
    
    url = await create_telegraph_page(f"🫧 Soul AI — {char}", text)
    
    if url:
        from keyboards.inline import titus_telegraph_kb
        await cb.message.answer(
            texts.TELEGRAPH_PUBLISHED,
            reply_markup=titus_telegraph_kb(url)
        )
    else:
        await cb.message.answer(texts.TELEGRAPH_FAILED)


# ═══════════════════════════════════════
# ОБРАБОТКА СООБЩЕНИЙ
# ═══════════════════════════════════════

async def process_luka_message(msg: Message, state: FSMContext, text: str, image_b64: str = None) -> None:
    user_id = msg.from_user.id
    sent_msg = None
    
    # Удаляем предыдущий смайлик клавиатуры (если был)
    data = await state.get_data()
    prev_kb_msg_id = data.get('kb_msg_id')
    if prev_kb_msg_id:
        try:
            await bot.delete_message(msg.chat.id, prev_kb_msg_id)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
        await state.update_data(kb_msg_id=None)
    
    # Rate limiting через core.rate_limiter
    allowed, wait_time = await rate_limiter.check(user_id)
    if not allowed:
        await msg.answer(MSG_RATE_LIMITED.format(seconds=wait_time))
        return
    
    # Антифлуд
    allowed, error_msg = await ai_flood.check(user_id)
    if not allowed:
        await msg.answer(error_msg)
        return
    
    # Проверка звёзд с красивым сообщением
    if not await ensure_balance(msg, required=MIN_STARS):
        return
    
    # Сбрасываем флаг отмены
    clear_cancel(user_id)
    
    # Показываем клавиатуру ожидания
    waiting_msg = await msg.answer("⏳", reply_markup=get_waiting_kb())
    
    # Модель
    model = await db.get_user_model(user_id)
    
    # Статус запроса
    request_state = {'cancelled': False, 'loading_msg': waiting_msg, 'status': None}
    await active_requests.set(user_id, request_state)
    
    # Получаем настройки пользователя из Redis
    user_settings = get_user_settings(user_id)
    char_key = user_settings['character']
    char_prompt = CHARS.get(char_key, CHARS['soul'])
    char_name = CHAR_NAMES.get(char_key, '🕊 Душа')
    
    # Параллельное получение памяти, истории и счётчика
    mem, hist, cnt = await asyncio.gather(
        get_user_memory(user_id),
        db.get_msgs(user_id, 'luca', 20),
        db.inc_msg_counter(user_id, 'luca')
    )
    memory_context = build_memory_context(mem)
    
    # Системный промпт
    system_prompt = f"""{char_prompt}

{memory_context}

ВАЖНО: НЕ начинай ответ с приветствия если пользователь не здоровается первым. Отвечай по существу."""

    # Если включены голосовые ответы в текстовом чате
    if user_settings.get('voice_enabled'):
        voice_style = LUCA_VOICE_STYLE_SOUL if char_key == 'soul' else LUCA_VOICE_STYLE_MIND
        system_prompt += f"\n\n{LUCA_VOICE_RULES}\n\n{voice_style}"

    if cnt >= 20:
        system_prompt += "\n\n⚡ Упомяни что-то из памяти о пользователе!"
        await db.reset_msg_counter(user_id, 'luca')
    
    # Формируем сообщения для API
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(hist)
    messages.append({"role": "user", "content": text})
    
    try:
        # Вызов API через core.api_queue
        if image_b64:
            # Удаляем смайлик ожидания ДО запроса
            if waiting_msg:
                try:
                    await waiting_msg.delete()
                except (TelegramBadRequest, TelegramForbiddenError):
                    pass
            
            status = await show_status(bot, msg.chat.id, "photo")
            request_state['status'] = status
            try:
                result = await api_queue.execute(ask, messages, model, image_b64)
                if result is None:
                    await msg.answer("⚠️ Запрос занял слишком много времени. Попробуй ещё раз.")
                    await active_requests.delete(user_id)
                    return
                resp, stars_used = result
            except Exception as e:
                await msg.answer(f"❌ Ошибка: {e}")
                await active_requests.delete(user_id)
                return
            finally:
                if status:
                    await status.stop()
        else:
            # Удаляем смайлик ожидания ДО стриминга
            if waiting_msg:
                try:
                    await waiting_msg.delete()
                except (TelegramBadRequest, TelegramForbiddenError):
                    pass
            
            try:
                result = await api_queue.execute(
                    stream_response,
                    bot=bot,
                    message=msg,
                    messages=messages,
                    model=model,
                    status_type="text"
                )
                if result is None:
                    await msg.answer("⚠️ Запрос занял слишком много времени. Попробуй ещё раз.")
                    await active_requests.delete(user_id)
                    return
                resp, sent_msg = result
                stars_used = calculate_stars(messages, resp)
            except Exception as e:
                logger.error(f"Stream error: {e}")
                await active_requests.delete(user_id)
                return
        
        await active_requests.delete(user_id)
        
        # Проверяем отмену запроса
        if is_cancelled(user_id):
            clear_cancel(user_id)
            return
        
        if not resp:
            await msg.answer(texts.ERROR_EMPTY_RESPONSE, reply_markup=kb.dialog_kb(user_id))
            return
        
        # Очищаем ответ от служебных строк
        resp = clean_response(resp)
        
        # Списываем звёзды с отслеживанием по боту
        await db.use_stars_smart(user_id, stars_used, 'luca')
        await db.increment_requests(user_id)
        
        # Сохраняем в историю
        await db.add_msg(user_id, 'luca', 'user', text)
        await db.add_msg(user_id, 'luca', 'assistant', resp)
        
        # Сохраняем в систему диалогов
        await save_message(user_id, 'user', text, 'luca', model)
        conv_id = await save_message(user_id, 'assistant', resp, 'luca', model)
        
        # Обновляем память в фоне
        create_safe_task(update_memory(user_id, 'luca', text, resp), f"update_memory:{user_id}")
        
        # Сохраняем для Telegraph
        await last_messages.set(user_id, {"text": resp, "char": char_name})
        
        resp_html = md_to_html(resp)
        
        # Проверяем, нужно ли превью
        needs_preview, display_text = should_show_preview(resp_html, max_length=3000)
        
        if needs_preview:
            display_text = md_to_html(display_text)
        
        # Получаем кнопку для просмотра диалога
        keyboard = get_chat_button(conv_id, len(resp_html))

        if user_settings['voice_enabled']:
            # === ГОЛОСОВОЙ ОТВЕТ ===
            if sent_msg:
                try:
                    await sent_msg.delete()
                except Exception:
                    pass
            
            voice_tts = VOICE_MAP.get(user_settings['voice_gender'], "onyx")
            
            # Очищаем текст от markdown для TTS
            resp_clean = resp.replace("**", "").replace("*", "").replace("#", "")
            resp_clean = re.sub(r'[^\w\s,.!?;:—\-()«»"\'\n]+', '', resp_clean, flags=re.UNICODE)
            
            try:
                audio_path = await text_to_speech(resp_clean, voice=voice_tts)
                
                if audio_path:
                    voice_file = FSInputFile(audio_path)
                    await msg.answer_voice(voice_file, reply_markup=keyboard)
                    
                    try:
                        os.remove(audio_path)
                    except OSError:
                        pass
                else:
                    footer = texts.RESPONSE_FOOTER.format(char_name=char_name)
                    await msg.answer(f"{display_text}{footer}", reply_markup=keyboard)
                    
            except Exception as e:
                logger.error(f"TTS error in text chat: {e}")
                footer = texts.RESPONSE_FOOTER.format(char_name=char_name)
                await msg.answer(f"{display_text}{footer}", reply_markup=keyboard)
            
            # Восстанавливаем reply-клавиатуру (невидимое сообщение)
            kb_msg = await msg.answer("ㅤ", reply_markup=kb.dialog_chat_kb())
            await state.update_data(kb_msg_id=kb_msg.message_id)
        else:
            # === ТЕКСТОВЫЙ ОТВЕТ ===
            footer = texts.RESPONSE_FOOTER.format(char_name=char_name)
            final_text = f"{display_text}{footer}"
            
            if sent_msg:
                try:
                    await sent_msg.edit_text(final_text, reply_markup=keyboard, parse_mode="HTML")
                except Exception:
                    await msg.answer(final_text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await msg.answer(final_text, reply_markup=keyboard, parse_mode="HTML")
            
            # Восстанавливаем reply-клавиатуру (невидимое сообщение)
            kb_msg = await msg.answer("ㅤ", reply_markup=kb.dialog_chat_kb())
            await state.update_data(kb_msg_id=kb_msg.message_id)
            
    except Exception as e:
        logger.exception(f"[Luca] Error in process_luka_message: {e}")
        await active_requests.delete(user_id)


@router.message(LukaSt.chat, F.text)
async def luka_chat_text(msg: Message, state: FSMContext) -> None:
    if msg.text in ["🛑 Завершить", "⏹ Стоп", CANCEL_REQUEST_BTN]:
        return
    await process_luka_message(msg, state, msg.text)


@router.message(LukaSt.chat, F.voice)
async def luka_chat_voice(msg: Message, state: FSMContext) -> None:
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
    await process_luka_message(msg, state, text)


@router.message(LukaSt.chat, F.photo)
async def luka_chat_photo(msg: Message, state: FSMContext) -> None:
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
    await process_luka_message(msg, state, msg.caption or "Что на изображении?", b64)


# ═══════════════════════════════════════
# ГОЛОСОВОЙ ЧАТ - ОБРАБОТКА СООБЩЕНИЙ
# ═══════════════════════════════════════

async def process_voice_message(msg: Message, state: FSMContext, text: str) -> None:
    """
    Обработка сообщения в голосовом режиме
    """
    user_id = msg.from_user.id
    
    # Удаляем предыдущий смайлик клавиатуры (если был)
    data = await state.get_data()
    prev_kb_msg_id = data.get('kb_msg_id')
    if prev_kb_msg_id:
        try:
            await bot.delete_message(msg.chat.id, prev_kb_msg_id)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
        await state.update_data(kb_msg_id=None)
    
    # Rate limiting через core.rate_limiter
    allowed, wait_time = await rate_limiter.check(user_id)
    if not allowed:
        await msg.answer(MSG_RATE_LIMITED.format(seconds=wait_time))
        return
    
    # Антифлуд
    allowed, error_msg = await ai_flood.check(user_id)
    if not allowed:
        await msg.answer(error_msg)
        return
    
    # Проверка звёзд
    if not await ensure_balance(msg, required=MIN_STARS):
        return
    
    # Статус запроса с кнопкой отмены
    request_state = {'cancelled': False, 'status': None}
    await active_requests.set(user_id, request_state)
    
    status = await show_status(bot, msg.chat.id, "voice")
    request_state['status'] = status
    
    try:
        # Получаем настройки пользователя из Redis
        user_settings = get_user_settings(user_id)
        voice_gender = user_settings['voice_gender']
        char_key = user_settings['character']
        
        # Параллельное получение модели, памяти и истории
        model, mem, hist = await asyncio.gather(
            db.get_user_model(user_id),
            get_user_memory(user_id),
            db.get_msgs(user_id, 'luca', 20)
        )
        memory_context = build_memory_context(mem)
        char_prompt = CHARS.get(char_key, CHARS['soul'])
        voice_style = LUCA_VOICE_STYLE_SOUL if char_key == 'soul' else LUCA_VOICE_STYLE_MIND
        
        # Системный промпт с эмоциональностью
        system_prompt = f"""{char_prompt}

{memory_context}

ВАЖНО: НЕ начинай ответ с приветствия если пользователь не здоровается. Отвечай по существу.
{LUCA_VOICE_RULES}
{voice_style}"""
        
        # Формируем сообщения для API
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(hist)
        messages.append({"role": "user", "content": text})
        
        # Проверка на отмену
        if request_state['cancelled']:
            await active_requests.delete(user_id)
            return
        
        # Запрос к AI через core.api_queue
        result = await api_queue.execute(ask, messages, model)
        if result is None:
            await msg.answer("⚠️ Запрос занял слишком много времени. Попробуй ещё раз.")
            await active_requests.delete(user_id)
            return
        resp, stars_used = result
        
        # Проверка на отмену
        if request_state['cancelled']:
            await active_requests.delete(user_id)
            return
        
        if not resp:
            await msg.answer(texts.ERROR_NO_AI_RESPONSE)
            await active_requests.delete(user_id)
            return
        
        # Очищаем ответ от эмодзи и markdown
        resp_clean = resp.replace("**", "").replace("*", "")
        resp_clean = re.sub(r'[^\w\s,.!?;:—\-()«»"\']+', '', resp_clean, flags=re.UNICODE)
        
        # Списываем звёзды
        await db.use_stars_smart(user_id, stars_used, 'luca')
        await db.increment_requests(user_id)
        
        # Сохраняем в историю
        await db.add_msg(user_id, 'luca', 'user', text)
        await db.add_msg(user_id, 'luca', 'assistant', resp_clean)
        
        # Обновляем память в фоне
        create_safe_task(update_memory(user_id, 'luca', text, resp_clean), f"update_memory:{user_id}")
        
        # Проверка на отмену
        if request_state['cancelled']:
            await active_requests.delete(user_id)
            return
        
        # Преобразуем в речь
        voice_tts = VOICE_MAP.get(voice_gender, "onyx")
        audio_path = await text_to_speech(resp_clean, voice=voice_tts)
        
        if not audio_path:
            await msg.answer(texts.ERROR_TTS_FAILED)
            await msg.answer(f"📝 {resp_clean[:500]}")
            await active_requests.delete(user_id)
            return
        
        # Проверка на отмену перед отправкой
        if request_state['cancelled']:
            try:
                os.remove(audio_path)
            except OSError:
                pass
            await active_requests.delete(user_id)
            return
        
        # Отправляем голосовое сообщение
        voice_file = FSInputFile(audio_path)
        await msg.answer_voice(voice_file)
        
        # Удаляем временный файл
        try:
            os.remove(audio_path)
        except OSError:
            pass
        
        # Восстанавливаем reply-клавиатуру (невидимое сообщение)
        kb_msg = await msg.answer("ㅤ", reply_markup=kb.voice_chat_kb())
        await state.update_data(kb_msg_id=kb_msg.message_id)
        
        await active_requests.delete(user_id)
            
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await msg.answer(f"❌ Ошибка: {str(e)[:100]}")
        await active_requests.delete(user_id)
    finally:
        if status:
            await status.stop()


@router.message(LukaSt.voice_chat, F.voice)
async def voice_chat_voice(msg: Message, state: FSMContext) -> None:
    """Обработка голосового сообщения от пользователя"""
    if msg.text in ["🛑 Завершить", "🔄 Сменить голос", CANCEL_REQUEST_BTN]:
        return
    
    status = await show_status(bot, msg.chat.id, "voice")
    
    try:
        file_path = await download_voice(bot, msg.voice.file_id)
        if not file_path:
            await msg.answer(texts.ERROR_VOICE_DOWNLOAD)
            return
        
        text = await transcribe_voice(file_path)
        if not text:
            await msg.answer(texts.ERROR_VOICE_RECOGNITION)
            return
        
        await msg.answer(texts.RECOGNIZED_TEXT.format(text=text))
        await process_voice_message(msg, state, text)
        
    except Exception as e:
        logger.error(f"Voice recognition error: {e}")
        await msg.answer(f"❌ Ошибка: {str(e)[:100]}")
    finally:
        if status:
            await status.stop()


@router.message(LukaSt.voice_chat, F.text)
async def voice_chat_text(msg: Message, state: FSMContext) -> None:
    """Обработка текстового сообщения (бот отвечает голосом)"""
    if msg.text in ["🛑 Завершить", "🔄 Сменить голос", CANCEL_REQUEST_BTN]:
        return
    
    await process_voice_message(msg, state, msg.text)
