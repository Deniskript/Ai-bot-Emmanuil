from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import reply, inline
from utils.openrouter import ask, ask_stream
from utils.tokens import calculate_tokens
from utils.memory import update_memory, build_memory_context
from utils.voice import download_voice, transcribe_voice
from utils.antiflood import ai_flood
from utils.telegraph import create_telegraph_page, make_preview
from utils.conversations import save_message, clean_response, should_show_preview, get_chat_button
from prompts.luca_prompt import LUCA_BASE, CHARS, CHAR_NAMES
from config import MIN_TOKENS
from loader import bot
import asyncio
import base64
import time
import re


def md_to_html(text):
    """Конвертирует **bold** в <b>bold</b>"""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


router = Router()


class LucaSt(StatesGroup):
    menu = State()
    chat = State()
    char = State()


active_requests = {}
last_messages = {}


# ========== УЛУЧШЕННЫЙ СТРИМИНГ ==========

def format_streaming_text(text: str) -> list:
    """
    Разбивает текст на блоки по 1-2 предложения для красивого стриминга
    """
    import re
    
    # Разбиваем по предложениям
    sentences = re.split(r'([.!?]+\s+)', text)
    blocks = []
    current_block = ""
    
    for i, part in enumerate(sentences):
        current_block += part
        
        # Если это конец предложения и накопилось 1-2 предложения
        if part.strip().endswith(('.', '!', '?')) or (i > 0 and sentences[i-1].strip().endswith(('.', '!', '?'))):
            if len(current_block.strip()) > 30:  # Минимум символов в блоке
                blocks.append(current_block.strip())
                current_block = ""
    
    # Добавляем остаток
    if current_block.strip():
        blocks.append(current_block.strip())
    
    return blocks if blocks else [text]


# ========== МЕНЮ ==========

@router.message(F.text == "💭 Диалог")
async def luca_enter(msg: Message, state: FSMContext):
    cfg = await db.get_bot_cfg('luca')
    if not cfg['enabled']:
        await msg.answer("🔴 Soul AI временно недоступен")
        return
    await state.set_state(LucaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_key = s.get('character', 'soul')
    char_name = CHAR_NAMES.get(char_key, '🕊 Душа')
    await msg.answer(
        f"💬 <b>Диалог</b>\n\n"
        f"🫂 Поддержит, когда тяжело\n"
        f"🚀 Поможет найти силы двигаться дальше\n"
        f"💡 Вдохновит на новые идеи\n"
        f"💭 Помнит всё, что ты рассказывал\n"
        f"🤝 Как друг, который всегда рядом\n\n"
        f"🪞 <b>Режим:</b> {char_name}\n\n"
        f"📖 Перед началом загляни в раздел «Помощь»",
        reply_markup=reply.dialog_kb(msg.from_user.id)
    )

@router.message(LucaSt.menu, F.text == "☁️ Начать")
async def luca_start_chat(msg: Message, state: FSMContext):
    await db.clear_msgs(msg.from_user.id, 'luca')
    await db.reset_msg_counter(msg.from_user.id, 'luca')
    await state.set_state(LucaSt.chat)
    await msg.answer(
        "💬 <b>Диалог начат!</b>\n\nПиши что угодно — я рядом:",
        reply_markup=reply.dialog_chat_kb()
    )


@router.message(LucaSt.menu, F.text == "🔄 Режим")
async def luca_char_menu(msg: Message, state: FSMContext):
    await state.set_state(LucaSt.char)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_key = s.get('character', 'soul')
    char_name = CHAR_NAMES.get(char_key, '🕊 Душа')
    await msg.answer(
        f"⚙️ <b>Выбери режим общения:</b>\n\n"
        f"🕊 <b>Душа</b> — душевные разговоры, поддержка, чувства\n"
        f"💡 <b>Разум</b> — задачи, решения, конкретика\n\n"
        f"Сейчас: {char_name}",
        reply_markup=reply.dialog_char_kb()
    )


@router.message(LucaSt.menu, F.text == "🗑 Очистить")
async def luca_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'luca')
    await msg.answer("🗑 История очищена!")


@router.message(LucaSt.menu, F.text == "◀️ Назад")
async def luca_back(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("🫧 Выберите бота:", reply_markup=reply.bots_menu_kb())


# ========== ХАРАКТЕР ==========

@router.message(LucaSt.char, F.text == "🕊 Душа")
async def char_soul(msg: Message, state: FSMContext):
    await db.set_char(msg.from_user.id, 'soul')
    await state.set_state(LucaSt.menu)
    await msg.answer(
        "✅ Режим: 🕊 Душа\n\n"
        "<i>Тёплый, понимающий, для разговоров по душам</i>",
        reply_markup=reply.dialog_kb(msg.from_user.id)
    )


@router.message(LucaSt.char, F.text == "💡 Разум")
async def char_mind(msg: Message, state: FSMContext):
    await db.set_char(msg.from_user.id, 'mind')
    await state.set_state(LucaSt.menu)
    await msg.answer(
        "✅ Режим: 💡 Разум\n\n"
        "<i>Чёткий, деловой, для задач и решений</i>",
        reply_markup=reply.dialog_kb(msg.from_user.id)
    )


@router.message(LucaSt.char, F.text == "◀️ Назад к Диалогу")
async def char_back(msg: Message, state: FSMContext):
    await state.set_state(LucaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_key = s.get('character', 'soul')
    char_name = CHAR_NAMES.get(char_key, '🕊 Душа')
    await msg.answer(
        f"🫧 <b>Soul AI</b>\n\n🪞 Режим: {char_name}",
        reply_markup=reply.dialog_kb(msg.from_user.id)
    )


# ========== ЧАТ ==========

@router.message(LucaSt.chat, F.text == "🛑 Завершить")
async def luca_stop(msg: Message, state: FSMContext):
    await state.set_state(LucaSt.menu)
    s = await db.get_user_bot(msg.from_user.id, 'luca')
    char_key = s.get('character', 'soul')
    char_name = CHAR_NAMES.get(char_key, '🕊 Душа')
    await msg.answer(
        f"👋 Диалог завершён!\n\n🫧 <b>Soul AI</b>\n🪞 Режим: {char_name}",
        reply_markup=reply.dialog_kb(msg.from_user.id)
    )


@router.message(LucaSt.chat, F.text == "🗑 Очистить")
async def luca_chat_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'luca')
    await msg.answer("🗑 История очищена! Продолжай:")


@router.message(LucaSt.chat, F.text == "⌛️ Отменить запрос")
async def luca_cancel(msg: Message):
    user_id = msg.from_user.id
    if user_id in active_requests:
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
        await msg.answer("❌ Запрос отменён", reply_markup=reply.dialog_chat_kb())
    else:
        await msg.answer("Нет активного запроса", reply_markup=reply.dialog_chat_kb())


@router.callback_query(F.data == "luca:tg")
async def luca_telegraph(cb: CallbackQuery):
    user_id = cb.from_user.id
    
    if user_id not in last_messages:
        await cb.answer("❌ Нет текста", show_alert=True)
        return
    
    await cb.answer("📖 Публикую на Telegraph...")
    
    data = last_messages[user_id]
    text = data['text']
    char = data.get('char', 'Soul AI')
    
    url = await create_telegraph_page(f"🫧 Soul AI — {char}", text)
    
    if url:
        await cb.message.answer(
            "📖 <b>Полный текст опубликован</b>",
            reply_markup=inline.titus_telegraph_kb(url)
        )
    else:
        await cb.message.answer("❌ Не удалось опубликовать")


# ========== ОБРАБОТКА СООБЩЕНИЙ ==========

async def process_luca_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    user_id = msg.from_user.id
    
    # Антифлуд
    allowed, error_msg = await ai_flood.check(user_id)
    if not allowed:
        await msg.answer(error_msg)
        return
    
    remaining = await db.get_available_tokens(user_id)
    if remaining < MIN_TOKENS:
        await msg.answer("❌ Токены закончились!\n\n💎 Пополните в разделе 💎 Подписка", reply_markup=reply.main_kb(msg.from_user.id))
        return
    
    # Модель
    model = await db.get_user_model(user_id)
    
    # Статус запроса
    request_state = {'cancelled': False, 'loading_msg': None, 'status_msg': None}
    active_requests[user_id] = request_state
    
    # Получаем настройки пользователя
    s = await db.get_user_bot(user_id, 'luca')
    char_key = s.get('character', 'soul')
    char_prompt = CHARS.get(char_key, CHARS['soul'])
    char_name = CHAR_NAMES.get(char_key, '🕊 Душа')
    
    # Память
    mem = await db.get_memory(user_id, 'luca')
    memory_context = build_memory_context(mem)
    
    # История (последние 20 сообщений)
    hist = await db.get_msgs(user_id, 'luca', 20)
    
    # Счётчик для упоминания памяти
    cnt = await db.inc_msg_counter(user_id, 'luca')
    
    # Системный промпт
    system_prompt = f"""{LUCA_BASE}

{char_prompt}
{memory_context}

ВАЖНО: НЕ начинай ответ с приветствия если пользователь не здоровается первым. Отвечай по существу."""

    if cnt >= 20:
        system_prompt += "\n\n⚡ Упомяни что-то из памяти о пользователе!"
        await db.reset_msg_counter(user_id, 'luca')
    
    # Формируем сообщения для API
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(hist)
    messages.append({"role": "user", "content": text})
    
    # Если есть картинка - обычный запрос
    if image_b64:
        status_msg = await msg.answer("⌛️ Обрабатываю... Пожалуйста подождите...")
        request_state['status_msg'] = status_msg
        try:
            resp, tok = await ask(messages, model, image_b64)
        except Exception as e:
            await status_msg.edit_text(f"❌ Ошибка: {e}")
            active_requests.pop(user_id, None)
            return
    else:
        # УЛУЧШЕННЫЙ STREAMING с красивым форматированием
        status_msg = await msg.answer("⌛️ Обрабатываю...")
        request_state['status_msg'] = status_msg
        
        full_response = ""
        sentence_buffer = ""
        displayed_text = ""
        last_update = time.time()
        typing_phase = 0  # 0=loading, 1=typing, 2=streaming blocks
        stream_msg = None
        
        try:
            async for chunk in ask_stream(messages, model, max_tokens=4000):  # Увеличен лимит!
                if request_state['cancelled']:
                    try:
                        await status_msg.delete()
                    except:
                        pass
                    active_requests.pop(user_id, None)
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
                    # Создаём сообщение для стриминга
                    stream_msg = await msg.answer("_Печатаю..._", parse_mode=None)
                
                # Обновляем текст блоками когда накопилось 1-2 предложения
                if typing_phase == 2 and stream_msg:
                    # Проверяем конец предложения
                    if sentence_buffer.rstrip().endswith(('.', '!', '?', '\n\n')):
                        displayed_text += sentence_buffer
                        sentence_buffer = ""
                        
                        # Обновляем с небольшой задержкой (каждые 0.5 сек)
                        if now - last_update >= 0.5:
                            formatted = md_to_html(displayed_text)
                            try:
                                await stream_msg.edit_text(formatted + " ▌")
                                last_update = now
                                await asyncio.sleep(0.3)  # Пауза для читаемости
                            except:
                                pass
            
            # Добавляем остаток
            displayed_text += sentence_buffer
            resp = full_response.strip()
            
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
            
            # Точный подсчёт токенов
            tok = calculate_tokens(messages, resp)
            
        except Exception as e:
            print(f"Stream error: {e}")
            import traceback
            traceback.print_exc()
            try:
                if stream_msg:
                    await stream_msg.delete()
                if status_msg:
                    await status_msg.edit_text(f"❌ Ошибка: {e}")
            except:
                pass
            active_requests.pop(user_id, None)
            return
    
    active_requests.pop(user_id, None)
    
    if not resp:
        await msg.answer("❌ Пустой ответ от AI")
        return
    
    # Очищаем ответ от служебных строк
    resp = clean_response(resp)
    
    # Списываем токены с отслеживанием по боту
    await db.use_tokens_smart(user_id, tok, 'luca')
    await db.increment_requests(user_id)
    
    # Сохраняем в историю
    await db.add_msg(user_id, 'luca', 'user', text)
    await db.add_msg(user_id, 'luca', 'assistant', resp)
    
    # Сохраняем в систему диалогов
    await save_message(user_id, 'user', text, 'luca', model)
    conv_id = await save_message(user_id, 'assistant', resp, 'luca', model)
    
    # Обновляем память в фоне
    asyncio.create_task(update_memory(user_id, 'luca', text, resp))
    
    # Сохраняем для Telegraph
    last_messages[user_id] = {"text": resp, "char": char_name}
    
    resp_html = md_to_html(resp)
    
    # Проверяем, нужно ли превью
    needs_preview, display_text = should_show_preview(resp_html, max_length=3000)
    
    if needs_preview:
        display_text = md_to_html(display_text)
    
    # Получаем кнопку для просмотра диалога
    keyboard = get_chat_button(conv_id, len(resp_html))
    
    # Отправляем ответ
    if needs_preview:
        await msg.answer(f"{display_text}\n\n<i>🫧 Soul AI • {char_name}</i>", reply_markup=keyboard)
    else:
        await msg.answer(f"{display_text}\n\n<i>🫧 Soul AI • {char_name}</i>", reply_markup=keyboard)


@router.message(LucaSt.chat, F.text)
async def luca_chat_text(msg: Message, state: FSMContext):
    if msg.text in ["🛑 Завершить", "🗑 Очистить", "⏹ Стоп", "⌛️ Отменить запрос"]:
        return
    await process_luca_message(msg, state, msg.text)


@router.message(LucaSt.chat, F.voice)
async def luca_chat_voice(msg: Message, state: FSMContext):
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
    await process_luca_message(msg, state, text)


@router.message(LucaSt.chat, F.photo)
async def luca_chat_photo(msg: Message, state: FSMContext):
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
    await process_luca_message(msg, state, msg.caption or "Что на изображении?", b64)
