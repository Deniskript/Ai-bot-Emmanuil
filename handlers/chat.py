import asyncio
import logging
import base64
import time
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatAction
from database import db
from utils.ai_client import get_ai_response, get_vision_response
from utils.voice import transcribe_voice
from utils.telegraph import create_telegraph_page
from utils.memory import get_messages_with_memory, update_memory
from config import MIN_TOKENS_FOR_REQUEST

logger = logging.getLogger(__name__)
router = Router()

active_requests = {}
user_last_request = {}

def fmt(n):
    return f"{n:,}".replace(",", " ")

def cancel_keyboard(request_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⌛️ Отменить запрос", callback_data=f"cancel:{request_id}")]
    ])

def response_keyboard(rid, telegraph_url=None):
    """Кнопки под ответом"""
    buttons = [[InlineKeyboardButton(text="📘 Отфильтрованный ответ", callback_data=f"filter:{rid}")]]
    if telegraph_url:
        buttons.insert(0, [InlineKeyboardButton(text="📖 Читать полностью", url=telegraph_url)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_spam_settings():
    enabled = await db.get_setting('spam_enabled')
    interval = await db.get_setting('spam_interval')
    max_req = await db.get_setting('spam_max_requests')
    return {
        'enabled': enabled != '0',
        'interval': int(interval) if interval else 2,
        'max_requests': int(max_req) if max_req else 1
    }

async def check_flood(user_id: int) -> tuple[bool, str]:
    settings = await get_spam_settings()
    if not settings['enabled']:
        return True, ""
    now = time.time()
    active_count = sum(1 for req_id, req_data in active_requests.items() 
                       if req_id.startswith(f"{user_id}_") and not req_data.get("cancelled"))
    if active_count >= settings['max_requests']:
        return False, "⏳ Подождите, обрабатываю предыдущий запрос..."
    last_time = user_last_request.get(user_id, 0)
    elapsed = now - last_time
    if elapsed < settings['interval']:
        wait = int(settings['interval'] - elapsed) + 1
        return False, f"⏳ Подождите {wait} сек..."
    user_last_request[user_id] = now
    return True, ""

async def send_response(msg, text, rid):
    text = text.strip()
    
    # Меньше 500 символов - просто текст + кнопка фильтра
    if len(text) <= 500:
        await msg.answer(text, reply_markup=response_keyboard(rid))
    
    # 500-3000 символов - полный текст + Telegraph + кнопка фильтра
    elif len(text) <= 3000:
        try:
            telegraph_url = await create_telegraph_page("Ответ", text)
            await msg.answer(text, reply_markup=response_keyboard(rid, telegraph_url))
        except:
            await msg.answer(text, reply_markup=response_keyboard(rid))
    
    # Больше 3000 символов - превью 500 символов + ссылка в тексте + кнопки
    else:
        try:
            telegraph_url = await create_telegraph_page("Ответ", text)
            preview = text[:500].rsplit(' ', 1)[0] + "..."
            
            formatted_text = f"""{preview}

━━━━━━━━━━━━━━━━━━━━
📚 <b>Полный ответ:</b> <a href="{telegraph_url}">читать в Telegraph →</a>
━━━━━━━━━━━━━━━━━━━━"""
            
            await msg.answer(formatted_text, reply_markup=response_keyboard(rid, telegraph_url), disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Telegraph error: {e}")
            # Если Telegraph не работает - отправляем частями
            for i in range(0, len(text), 4000):
                await msg.answer(text[i:i+4000])

async def status_updater(status_msg, prefix, request_id, stop_event, bot, chat_id):
    start_time = time.time()
    last_update = 0
    while not stop_event.is_set():
        elapsed = int(time.time() - start_time)
        if elapsed != last_update:
            last_update = elapsed
            try:
                await status_msg.edit_text(f"{prefix} ({elapsed} сек)", reply_markup=cancel_keyboard(request_id))
            except:
                pass
        if elapsed % 4 == 0:
            try:
                await bot.send_chat_action(chat_id, ChatAction.TYPING)
            except:
                pass
        await asyncio.sleep(1)

@router.callback_query(F.data.startswith("cancel:"))
async def cancel_request(cb: CallbackQuery):
    request_id = cb.data.split(":")[1]
    if request_id in active_requests:
        active_requests[request_id]["cancelled"] = True
        active_requests[request_id]["event"].set()
        await cb.answer("❌ Запрос отменён")
        try:
            await cb.message.delete()
        except:
            pass
    else:
        await cb.answer("Запрос уже завершён")

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(msg: Message):
    menu_buttons = ["✨ Начать диалог", "👤 Мой кабинет", "💰 Пополнить", "💡 Помощь"]
    if msg.text in menu_buttons:
        return
    
    can_send, flood_msg = await check_flood(msg.from_user.id)
    if not can_send:
        await msg.answer(flood_msg)
        return
    
    user = await db.get_user(msg.from_user.id)
    if not user:
        user = await db.create_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    
    if user['tokens'] < MIN_TOKENS_FOR_REQUEST:
        await msg.answer(f"Недостаточно токенов! Баланс: {fmt(user['tokens'])}")
        return
    
    request_id = f"{msg.from_user.id}_{msg.message_id}"
    stop_event = asyncio.Event()
    active_requests[request_id] = {"event": stop_event, "cancelled": False}
    
    status_msg = await msg.answer("✍️ Печатаю... (0 сек)", reply_markup=cancel_keyboard(request_id))
    status_task = asyncio.create_task(status_updater(status_msg, "✍️ Печатаю...", request_id, stop_event, msg.bot, msg.chat.id))
    
    try:
        messages = await get_messages_with_memory(msg.from_user.id)
        messages.append({"role": "user", "content": msg.text})
        
        response, tokens_used = await get_ai_response(messages)
        
        stop_event.set()
        status_task.cancel()
        
        if active_requests.get(request_id, {}).get("cancelled"):
            active_requests.pop(request_id, None)
            return
        
        active_requests.pop(request_id, None)
        
        try:
            await status_msg.delete()
        except:
            pass
        
        await db.add_message(msg.from_user.id, "user", msg.text)
        await db.add_message(msg.from_user.id, "assistant", response)
        await db.update_user_tokens(msg.from_user.id, tokens_used)
        await db.update_user_stats(msg.from_user.id)
        
        rid = await db.save_long_response(msg.from_user.id, msg.message_id, response, "")
        
        mem_data = await db.get_user_memory(msg.from_user.id)
        if mem_data and mem_data.get('memory_enabled'):
            asyncio.create_task(update_memory(msg.from_user.id, msg.text, response))
        
        await send_response(msg, response, rid)
        
    except Exception as e:
        stop_event.set()
        status_task.cancel()
        active_requests.pop(request_id, None)
        try:
            await status_msg.delete()
        except:
            pass
        logger.error(f"Text error: {e}", exc_info=True)
        await msg.answer(f"Ошибка: {e}")

@router.message(F.photo)
async def handle_photo(msg: Message):
    can_send, flood_msg = await check_flood(msg.from_user.id)
    if not can_send:
        await msg.answer(flood_msg)
        return
    
    user = await db.get_user(msg.from_user.id)
    if not user:
        user = await db.create_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    
    if user['tokens'] < MIN_TOKENS_FOR_REQUEST:
        await msg.answer("Недостаточно токенов!")
        return
    
    request_id = f"{msg.from_user.id}_{msg.message_id}"
    stop_event = asyncio.Event()
    active_requests[request_id] = {"event": stop_event, "cancelled": False}
    
    status_msg = await msg.answer("👀 Смотрю... (0 сек)", reply_markup=cancel_keyboard(request_id))
    status_task = asyncio.create_task(status_updater(status_msg, "👀 Смотрю...", request_id, stop_event, msg.bot, msg.chat.id))
    
    try:
        photo = msg.photo[-1]
        file = await msg.bot.get_file(photo.file_id)
        file_data = await msg.bot.download_file(file.file_path)
        b64 = base64.b64encode(file_data.read()).decode()
        
        prompt = msg.caption or "Что изображено на этой картинке?"
        response, tokens_used = await get_vision_response(b64, prompt)
        
        stop_event.set()
        status_task.cancel()
        
        if active_requests.get(request_id, {}).get("cancelled"):
            active_requests.pop(request_id, None)
            return
        
        active_requests.pop(request_id, None)
        
        try:
            await status_msg.delete()
        except:
            pass
        
        await db.update_user_tokens(msg.from_user.id, tokens_used)
        await db.update_user_stats(msg.from_user.id)
        
        rid = await db.save_long_response(msg.from_user.id, msg.message_id, response, "")
        await send_response(msg, response, rid)
        
    except Exception as e:
        stop_event.set()
        status_task.cancel()
        active_requests.pop(request_id, None)
        try:
            await status_msg.delete()
        except:
            pass
        logger.error(f"Photo error: {e}", exc_info=True)
        await msg.answer(f"Ошибка: {e}")

@router.message(F.voice)
async def handle_voice(msg: Message):
    can_send, flood_msg = await check_flood(msg.from_user.id)
    if not can_send:
        await msg.answer(flood_msg)
        return
    
    user = await db.get_user(msg.from_user.id)
    if not user:
        user = await db.create_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    
    if user['tokens'] < MIN_TOKENS_FOR_REQUEST:
        await msg.answer("Недостаточно токенов!")
        return
    
    request_id = f"{msg.from_user.id}_{msg.message_id}"
    stop_event = asyncio.Event()
    active_requests[request_id] = {"event": stop_event, "cancelled": False}
    
    status_msg = await msg.answer("🎧 Слушаю... (0 сек)", reply_markup=cancel_keyboard(request_id))
    status_task = asyncio.create_task(status_updater(status_msg, "🎧 Слушаю...", request_id, stop_event, msg.bot, msg.chat.id))
    
    try:
        file = await msg.bot.get_file(msg.voice.file_id)
        file_data = await msg.bot.download_file(file.file_path)
        voice_bytes = file_data.read()
        
        text = await transcribe_voice(voice_bytes)
        if not text:
            stop_event.set()
            status_task.cancel()
            active_requests.pop(request_id, None)
            await status_msg.edit_text("❌ Не удалось распознать речь")
            return
        
        await status_msg.edit_text(f"🎤 {text}\n\n✍️ Думаю... (0 сек)", reply_markup=cancel_keyboard(request_id))
        
        messages = await get_messages_with_memory(msg.from_user.id)
        messages.append({"role": "user", "content": text})
        response, tokens_used = await get_ai_response(messages)
        
        stop_event.set()
        status_task.cancel()
        
        if active_requests.get(request_id, {}).get("cancelled"):
            active_requests.pop(request_id, None)
            return
        
        active_requests.pop(request_id, None)
        
        try:
            await status_msg.delete()
        except:
            pass
        
        await db.add_message(msg.from_user.id, "user", text)
        await db.add_message(msg.from_user.id, "assistant", response)
        await db.update_user_tokens(msg.from_user.id, tokens_used)
        await db.update_user_stats(msg.from_user.id)
        
        rid = await db.save_long_response(msg.from_user.id, msg.message_id, response, "")
        await send_response(msg, response, rid)
        
    except Exception as e:
        stop_event.set()
        status_task.cancel()
        active_requests.pop(request_id, None)
        try:
            await status_msg.delete()
        except:
            pass
        logger.error(f"Voice error: {e}", exc_info=True)
        await msg.answer(f"Ошибка: {e}")

@router.callback_query(F.data.startswith("filter:"))
async def filter_callback(cb: CallbackQuery):
    await cb.answer()
    rid = int(cb.data.split(":")[1])
    
    resp_data = await db.get_long_response(rid)
    if not resp_data:
        await cb.message.answer("Ответ не найден")
        return
    
    user = await db.get_user(cb.from_user.id)
    if user['tokens'] < MIN_TOKENS_FOR_REQUEST:
        await cb.message.answer("Недостаточно токенов!")
        return
    
    request_id = f"{cb.from_user.id}_{cb.message.message_id}"
    stop_event = asyncio.Event()
    active_requests[request_id] = {"event": stop_event, "cancelled": False}
    
    status_msg = await cb.message.answer("📘 Фильтрую ответ... (0 сек)", reply_markup=cancel_keyboard(request_id))
    status_task = asyncio.create_task(status_updater(status_msg, "📘 Фильтрую ответ...", request_id, stop_event, cb.bot, cb.message.chat.id))
    
    try:
        messages = [
            {"role": "system", "content": "Ты помощник для фильтрации ответов. Твоя задача — взять длинный ответ и выделить из него только самое важное: ключевые факты, главные выводы, практические рекомендации. Убери воду, повторы и лишние детали. Ответ должен быть кратким, структурированным и по существу."},
            {"role": "user", "content": f"Отфильтруй этот ответ, оставь только самое важное:\n\n{resp_data['full_response'][:3000]}"}
        ]
        
        response, tokens_used = await get_ai_response(messages)
        
        stop_event.set()
        status_task.cancel()
        
        if active_requests.get(request_id, {}).get("cancelled"):
            active_requests.pop(request_id, None)
            return
        
        active_requests.pop(request_id, None)
        
        try:
            await status_msg.delete()
        except:
            pass
        
        await db.update_user_tokens(cb.from_user.id, tokens_used)
        await cb.message.answer(f"📘 <b>Отфильтрованный ответ:</b>\n\n{response}")
        
    except Exception as e:
        stop_event.set()
        status_task.cancel()
        active_requests.pop(request_id, None)
        try:
            await status_msg.delete()
        except:
            pass
        await cb.message.answer(f"Ошибка: {e}")
