"""
-+ Luca (Soul AI) - 100% автономный модуль
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from database import postgres_db as db
from database import redis_db
from keyboards import reply as global_reply  # для bots_menu_kb()
from utils.openrouter import ask
from utils.stars import calculate_stars
from utils.memory import update_memory
from utils.voice import download_voice, transcribe_voice, text_to_speech
from utils.antiflood import ai_flood
from utils.telegraph import create_telegraph_page
from utils.conversations import save_message, clean_response, should_show_preview, get_chat_button
from utils.status_manager import show_status
from utils.streaming import stream_response
from utils.balance_guard import ensure_balance
from utils.markdown import md_to_html
from loader import bot
import asyncio
import base64
import re
import os
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)

# Локальные импорты модуля (всё внутри handlers/luca/)
from . import config as luca_config
from . import texts
from . import keyboards as kb
from .memory import (
    get_user_memory,
    build_memory_context,
    build_prompt_with_memory,
    CHARS,
    CHAR_NAMES
)
from .prompts import LUCA_VOICE_RULES, LUCA_VOICE_STYLE_SOUL, LUCA_VOICE_STYLE_MIND
from handlers.ai_buttons import CANCEL_REQUEST_BTN, get_waiting_kb, is_cancelled, clear_cancel, cancel_user_request

router = Router()


# ========== СОСТОЯНИЯ ==========

class LukaSt(StatesGroup):
    menu = State()
    chat = State()
    char = State()
    voice_choose = State()  # Выбор голоса
    voice_chat = State()    # Голосовой чат


# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========

active_requests: OrderedDict = OrderedDict()
last_messages: OrderedDict = OrderedDict()

# Использование настроек из локального config
MIN_STARS = luca_config.MIN_STARS
MAX_CACHE_SIZE = luca_config.MAX_CACHE_SIZE
VOICE_MAP = luca_config.VOICE_MAP


# ========== УТИЛИТЫ ==========

def get_user_settings(user_id: int) -> dict:
    """Получить настройки пользователя из Redis"""
    return redis_db.get_luca_settings(user_id)


def cleanup_cache(cache_dict: OrderedDict, max_size: int = MAX_CACHE_SIZE):
    """Очистка кэша с удалением самых старых записей (FIFO)"""
    while len(cache_dict) > max_size:
        cache_dict.popitem(last=False)  # Удаляем самый старый элемент


async def _safe_background_task(coro, task_name: str = "background"):
    """Безопасный запуск фоновой задачи с логированием ошибок"""
    try:
        await coro
    except Exception as e:
        logger.error(f"Background task '{task_name}' failed: {e}", exc_info=True)


def create_safe_task(coro, task_name: str = "background"):
    """Создать фоновую задачу с отслеживанием ошибок"""
    return asyncio.create_task(_safe_background_task(coro, task_name))


# ========== МЕНЮ ==========

@router.message(F.text == "✨ Soul Чат")
async def luka_enter(msg: Message, state: FSMContext):
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
async def luka_start_chat(msg: Message, state: FSMContext):
    await db.clear_msgs(msg.from_user.id, 'luca')
    await db.reset_msg_counter(msg.from_user.id, 'luca')
    await state.set_state(LukaSt.chat)
    await msg.answer(
        texts.CHAT_STARTED,
        reply_markup=kb.dialog_chat_kb()
    )


@router.message(LukaSt.menu, F.text == "🔄 Режим")
async def luka_char_menu(msg: Message, state: FSMContext):
    await state.set_state(LukaSt.char)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_key = s.get('character', 'soul')
    char_name = CHAR_NAMES.get(char_key, '🕊 Душа')
    await msg.answer(
        texts.CHAR_SELECT.format(char_name=char_name),
        reply_markup=kb.dialog_char_kb()
    )


@router.message(LukaSt.menu, F.text == "🧹 Очистить")
async def luka_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'luca')
    await msg.answer(texts.HISTORY_CLEARED)


@router.message(LukaSt.menu, F.text == "◀️ Назад")
async def luka_back(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("🫧 Выберите бота:", reply_markup=global_reply.bots_menu_kb())


# ========== ХАРАКТЕР ==========

@router.message(LukaSt.char, F.text == "🕊 Душа")
async def char_soul(msg: Message, state: FSMContext):
    await db.set_char(msg.from_user.id, 'soul')
    await state.set_state(LukaSt.menu)
    await msg.answer(
        texts.SOUL_SET,
        reply_markup=kb.dialog_kb(msg.from_user.id)
    )


@router.message(LukaSt.char, F.text == "💡 Разум")
async def char_mind(msg: Message, state: FSMContext):
    await db.set_char(msg.from_user.id, 'mind')
    await state.set_state(LukaSt.menu)
    await msg.answer(
        texts.MIND_SET,
        reply_markup=kb.dialog_kb(msg.from_user.id)
    )


@router.message(LukaSt.char, F.text == "🎤 Голос")
async def char_voice(msg: Message, state: FSMContext):
    """Вход в голосовой режим"""
    # Проверяем есть ли уже сохранённый голос
    voice_gender = await db.get_voice_gender(msg.from_user.id, 'luca')
    
    if voice_gender:
        # Голос уже выбран, сразу в чат
        await state.set_state(LukaSt.voice_chat)
        gender_name = "👨 Мужской" if voice_gender == "male" else "👩 Женский"
        await msg.answer(
            texts.VOICE_ACTIVATED.format(gender_name=gender_name),
            reply_markup=kb.voice_chat_kb()
        )
    else:
        # Первый вход - выбор голоса
        await state.set_state(LukaSt.voice_choose)
        await msg.answer(
            texts.VOICE_CHOOSE,
            reply_markup=kb.voice_gender_kb()
        )


@router.message(LukaSt.char, F.text == "◀️ Назад к Диалогу")
async def char_back(msg: Message, state: FSMContext):
    await state.set_state(LukaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_key = s.get('character', 'soul')
    char_name = CHAR_NAMES.get(char_key, '🕊 Душа')
    await msg.answer(
        f"🫧 <b>Soul AI</b>\n\n🪞 Режим: {char_name}",
        reply_markup=kb.dialog_kb(msg.from_user.id)
    )


# ========== ГОЛОСОВОЙ РЕЖИМ ==========

@router.callback_query(F.data.startswith("voice:gender:"))
async def voice_gender_selected(cb: CallbackQuery, state: FSMContext):
    """Обработка выбора голоса"""
    gender = cb.data.split(":")[2]  # male или female
    
    # Сохраняем выбор в БД
    await db.set_voice_gender(cb.from_user.id, gender, 'luca')
    
    # Переходим в режим чата
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
async def voice_stop(msg: Message, state: FSMContext):
    """Выход из голосового режима"""
    await state.set_state(LukaSt.char)
    await msg.answer(
        texts.VOICE_ENDED,
        reply_markup=kb.dialog_char_kb()
    )


@router.message(LukaSt.voice_chat, F.text == "🔄 Сменить голос")
async def voice_change_gender(msg: Message, state: FSMContext):
    """Смена голоса"""
    await state.set_state(LukaSt.voice_choose)
    current_gender = await db.get_voice_gender(msg.from_user.id, 'luca')
    current_name = "👨 Мужской" if current_gender == "male" else "👩 Женский"
    
    await msg.answer(
        texts.VOICE_CHANGE.format(current_name=current_name),
        reply_markup=kb.voice_gender_kb()
    )


@router.message(LukaSt.voice_chat, F.text == CANCEL_REQUEST_BTN)
async def voice_cancel(msg: Message, state: FSMContext):
    """Отмена запроса в голосовом режиме"""
    user_id = msg.from_user.id
    cancel_user_request(user_id)
    
    if user_id in active_requests:
        active_requests[user_id]['cancelled'] = True
        try:
            if active_requests[user_id].get('status'):
                await active_requests[user_id]['status'].stop()
        except Exception as e:
            logger.debug(f"Failed to stop status: {e}")
    
    try:
        await msg.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    
    await state.set_state(LukaSt.char)
    await msg.answer("❌ Запрос отменён", reply_markup=kb.dialog_char_kb())


# ========== ЧАТ ==========

@router.message(LukaSt.chat, F.text == "🛑 Завершить")
async def luka_stop(msg: Message, state: FSMContext):
    await state.set_state(LukaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_key = s.get('character', 'soul')
    char_name = CHAR_NAMES.get(char_key, '🕊 Душа')
    await msg.answer(
        texts.CHAT_ENDED.format(char_name=char_name),
        reply_markup=kb.dialog_kb(msg.from_user.id)
    )


@router.message(LukaSt.chat, F.text == CANCEL_REQUEST_BTN)
async def luka_cancel(msg: Message, state: FSMContext):
    """Отмена запроса в текстовом чате"""
    user_id = msg.from_user.id
    cancel_user_request(user_id)
    
    if user_id in active_requests:
        active_requests[user_id]['cancelled'] = True
        try:
            if active_requests[user_id].get('kb_msg'):
                await active_requests[user_id]['kb_msg'].delete()
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
        try:
            if active_requests[user_id].get('status'):
                await active_requests[user_id]['status'].stop()
        except Exception as e:
            logger.debug(f"Failed to stop status: {e}")
    
    try:
        await msg.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    
    await state.set_state(LukaSt.menu)
    await msg.answer("❌ Запрос отменён", reply_markup=kb.dialog_kb(user_id))


@router.callback_query(F.data == "luca:tg")
async def luka_telegraph(cb: CallbackQuery):
    user_id = cb.from_user.id
    
    if user_id not in last_messages:
        await cb.answer(texts.NO_TEXT_FOR_TELEGRAPH, show_alert=True)
        return
    
    await cb.answer(texts.PUBLISHING_TELEGRAPH)
    
    data = last_messages[user_id]
    text = data['text']
    char = data.get('char', 'Soul AI')
    
    url = await create_telegraph_page(f"🫧 Soul AI — {char}", text)
    
    if url:
        from keyboards.inline import titus_telegraph_kb  # Используем общую функцию
        await cb.message.answer(
            texts.TELEGRAPH_PUBLISHED,
            reply_markup=titus_telegraph_kb(url)
        )
    else:
        await cb.message.answer(texts.TELEGRAPH_FAILED)


# ========== ОБРАБОТКА СООБЩЕНИЙ ==========

async def process_luka_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    user_id = msg.from_user.id
    sent_msg = None
    
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
    active_requests[user_id] = request_state
    
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

    # Если включены голосовые ответы в текстовом чате — делаем ответ speech-friendly
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
    
    # Если есть картинка - обычный запрос
    if image_b64:
        status = await show_status(bot, msg.chat.id, "photo")
        request_state['status'] = status
        try:
            resp, stars_used = await ask(messages, model, image_b64)
        except Exception as e:
            # Удаляем смайлик ожидания при ошибке
            if waiting_msg:
                try:
                    await waiting_msg.delete()
                except (TelegramBadRequest, TelegramForbiddenError):
                    pass
            await msg.answer(f"❌ Ошибка: {e}")
            active_requests.pop(user_id, None)
            return
        finally:
            if status:
                await status.stop()
    else:
        # Единый стриминг
        # Удаляем смайлик ожидания ДО стриминга (stream_response показывает свой статус)
        if waiting_msg:
            try:
                await waiting_msg.delete()
            except (TelegramBadRequest, TelegramForbiddenError):
                pass
        
        try:
            resp, sent_msg = await stream_response(
                bot=bot,
                message=msg,
                messages=messages,
                model=model,
                status_type="text"
            )
            stars_used = calculate_stars(messages, resp)
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            active_requests.pop(user_id, None)
            return
    
    active_requests.pop(user_id, None)
    
    # Проверяем отмену запроса
    if is_cancelled(user_id):
        clear_cancel(user_id)
        return  # Не отправляем ответ
    
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
    last_messages[user_id] = {"text": resp, "char": char_name}
    cleanup_cache(last_messages)  # Предотвращаем утечку памяти
    
    resp_html = md_to_html(resp)
    
    # Проверяем, нужно ли превью
    needs_preview, display_text = should_show_preview(resp_html, max_length=3000)
    
    if needs_preview:
        display_text = md_to_html(display_text)
    
    # Получаем кнопку для просмотра диалога
    keyboard = get_chat_button(conv_id, len(resp_html))

    if user_settings['voice_enabled']:
        # === ГОЛОСОВОЙ ОТВЕТ ===
        # Удаляем текстовое сообщение от стриминга
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
                
                # Удаляем временный файл
                try:
                    os.remove(audio_path)
                except OSError:
                    pass
            else:
                # Fallback на текст если TTS не сработал
                footer = texts.RESPONSE_FOOTER.format(char_name=char_name)
                await msg.answer(f"{display_text}{footer}", reply_markup=keyboard)
                
        except Exception as e:
            logger.error(f"TTS error in text chat: {e}", exc_info=True)
            # Fallback на текст
            footer = texts.RESPONSE_FOOTER.format(char_name=char_name)
            await msg.answer(f"{display_text}{footer}", reply_markup=keyboard)
    else:
        # === ТЕКСТОВЫЙ ОТВЕТ ===
        footer = texts.RESPONSE_FOOTER.format(char_name=char_name)
        final_text = f"{display_text}{footer}"
        
        # Редактируем существующее сообщение вместо отправки нового
        if sent_msg:
            try:
                await sent_msg.edit_text(final_text, reply_markup=keyboard, parse_mode="HTML")
            except Exception:
                # Если не удалось отредактировать - отправляем новое
                await msg.answer(final_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await msg.answer(final_text, reply_markup=keyboard, parse_mode="HTML")
    
    # Возвращаем reply-клавиатуру (она не конфликтует с inline-кнопками выше)
    # Отправляем её отдельно чтобы пользователь видел кнопки "Завершить/Очистить"
    try:
        await msg.answer("💬", reply_markup=kb.dialog_chat_kb())
    except Exception:
        pass


@router.message(LukaSt.chat, F.text)
async def luka_chat_text(msg: Message, state: FSMContext):
    if msg.text in ["🛑 Завершить", "⏹ Стоп", CANCEL_REQUEST_BTN]:
        return
    await process_luka_message(msg, state, msg.text)


@router.message(LukaSt.chat, F.voice)
async def luka_chat_voice(msg: Message, state: FSMContext):
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
async def luka_chat_photo(msg: Message, state: FSMContext):
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


# ========== ГОЛОСОВОЙ ЧАТ - ОБРАБОТКА СООБЩЕНИЙ ==========

async def process_voice_message(msg: Message, state: FSMContext, text: str):
    """
    Обработка сообщения в голосовом режиме
    1. Проверки (антифлуд, звёзды)
    2. Получение ответа от AI
    3. Озвучка через TTS
    4. Отправка голосового сообщения
    """
    user_id = msg.from_user.id
    
    # Антифлуд
    allowed, error_msg = await ai_flood.check(user_id)
    if not allowed:
        await msg.answer(error_msg)
        return
    
    # Проверка звёзд с красивым сообщением
    if not await ensure_balance(msg, required=MIN_STARS):
        return
    
    # Статус запроса с кнопкой отмены
    request_state = {'cancelled': False, 'status': None}
    active_requests[user_id] = request_state
    
    # Меняем клавиатуру на "Отменить запрос"
    kb_msg = await msg.answer("⌛️", reply_markup=kb.voice_chat_loading_kb())
    try:
        await kb_msg.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    
    status = await show_status(bot, msg.chat.id, "voice")
    request_state['status'] = status
    
    try:
        # Получаем настройки пользователя из Redis (один раз)
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
            active_requests.pop(user_id, None)
            return
        
        # Запрос к AI
        resp, stars_used = await ask(messages, model)
        
        # Проверка на отмену
        if request_state['cancelled']:
            active_requests.pop(user_id, None)
            return
        
        if not resp:
            await msg.answer(texts.ERROR_NO_AI_RESPONSE)
            active_requests.pop(user_id, None)
            return
        
        # Очищаем ответ от эмодзи и markdown
        resp_clean = resp.replace("**", "").replace("*", "")
        # Удаляем эмодзи (упрощённо)
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
            active_requests.pop(user_id, None)
            return
        
        # Преобразуем в речь
        voice_tts = VOICE_MAP.get(voice_gender, "onyx")
        audio_path = await text_to_speech(resp_clean, voice=voice_tts)
        
        if not audio_path:
            await msg.answer(texts.ERROR_TTS_FAILED)
            # Отправляем текстом на всякий случай
            await msg.answer(f"📝 {resp_clean[:500]}")
            active_requests.pop(user_id, None)
            return
        
        # Проверка на отмену перед отправкой
        if request_state['cancelled']:
            try:
                os.remove(audio_path)
            except OSError:
                pass
            active_requests.pop(user_id, None)
            return
        
        # Отправляем голосовое сообщение с обычной клавиатурой
        voice_file = FSInputFile(audio_path)
        await msg.answer_voice(voice_file, reply_markup=kb.voice_chat_kb())
        
        # Удаляем временный файл
        try:
            os.remove(audio_path)
        except OSError:
            pass
        
        active_requests.pop(user_id, None)
        cleanup_cache(active_requests)  # Предотвращаем утечку памяти
            
    except Exception as e:
        logger.error(f"Voice processing error: {e}", exc_info=True)
        await msg.answer(f"❌ Ошибка: {str(e)[:100]}")
        active_requests.pop(user_id, None)
    finally:
        if status:
            await status.stop()


@router.message(LukaSt.voice_chat, F.voice)
async def voice_chat_voice(msg: Message, state: FSMContext):
    """Обработка голосового сообщения от пользователя"""
    if msg.text in ["🛑 Завершить", "🔄 Сменить голос", CANCEL_REQUEST_BTN]:
        return
    
    status = await show_status(bot, msg.chat.id, "voice")
    
    try:
        # Скачиваем и распознаём голос
        file_path = await download_voice(bot, msg.voice.file_id)
        if not file_path:
            await msg.answer(texts.ERROR_VOICE_DOWNLOAD)
            return
        
        text = await transcribe_voice(file_path)
        if not text:
            await msg.answer(texts.ERROR_VOICE_RECOGNITION)
            return
        
        # Показываем что распознали
        await msg.answer(texts.RECOGNIZED_TEXT.format(text=text))
        
        # Обрабатываем как текст
        await process_voice_message(msg, state, text)
        
    except Exception as e:
        logger.error(f"Voice recognition error: {e}", exc_info=True)
        await msg.answer(f"❌ Ошибка: {str(e)[:100]}")
    finally:
        if status:
            await status.stop()


@router.message(LukaSt.voice_chat, F.text)
async def voice_chat_text(msg: Message, state: FSMContext):
    """Обработка текстового сообщения (бот отвечает голосом)"""
    if msg.text in ["🛑 Завершить", "🔄 Сменить голос", CANCEL_REQUEST_BTN]:
        return
    
    await process_voice_message(msg, state, msg.text)
