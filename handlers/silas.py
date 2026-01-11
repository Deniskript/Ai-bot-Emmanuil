from aiogram import Router, F
import re
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import reply, inline
from utils.openrouter import ask
from utils.memory import update_memory, build_memory_context
from utils.voice import download_voice, transcribe_voice
from utils.antiflood import ai_flood
from utils.telegraph import create_telegraph_page, make_preview
from utils.conversations import save_message, clean_response, should_show_preview, get_chat_button
from prompts.silas_prompt import SILAS_SYSTEM, MOOD_GOOD, MOOD_TIRED, MOOD_PAIN
from config import MIN_TOKENS
from loader import bot
from datetime import datetime
import asyncio
import base64

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

MOODS = {'good': MOOD_GOOD, 'tired': MOOD_TIRED, 'pain': MOOD_PAIN}
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

@router.message(F.text.in_(["🛋️ Психолог", "🧘 Психолог"]))
async def silas_enter(msg: Message, state: FSMContext):
    cfg = await db.get_bot_cfg('silas')
    if not cfg['enabled']:
        await msg.answer("🔴 Психолог временно недоступен")
        return
    await state.set_state(SilasSt.menu)
    await msg.answer(
        "🛋️ <b>Психолог</b>\n\n"
        "✨ Выслушает и подведёт к ответам как настоящий психолог\n"
        "💭 Помнит контекст разговора\n"
        "🔄 Подстраивается под твоё состояние\n"
        "✅ Помогает разобраться в себе\n\n"
        "📖 Перед началом загляни в раздел «Помощь»",
        reply_markup=reply.psycho_kb(msg.from_user.id)
    )

@router.message(SilasSt.menu, F.text == "🛋️ Начать сеанс")
async def silas_start_session(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.duration)
    await msg.answer("⏱ <b>Выберите длительность сеанса:</b>", reply_markup=reply.psycho_dur_kb())

@router.message(SilasSt.menu, F.text == "📔 Настроение")
async def silas_mood_menu(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.mood)
    await msg.answer("📔 <b>Дневник настроения</b>\n\nКак вы себя сейчас чувствуете?", reply_markup=reply.psycho_mood_kb())

@router.message(SilasSt.menu, F.text == "🔍 Помощь")
async def silas_help(msg: Message):
    text = await db.get_text('help_psycho')
    if not text:
        text = "🛋️ <b>Психолог</b> — AI-помощник для поддержки и самопознания"
    await msg.answer(text)

@router.message(SilasSt.menu, F.text == "◀️ Назад")
async def silas_back(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("✨ Выберите помощника:", reply_markup=reply.bots_menu_kb())

@router.message(SilasSt.duration, F.text.in_({"15 минут", "30 минут", "60 минут"}))
async def silas_set_duration(msg: Message, state: FSMContext):
    dur_map = {"15 минут": 15, "30 минут": 30, "60 минут": 60}
    dur = dur_map.get(msg.text, 30)
    sid = await db.start_session(msg.from_user.id, dur)
    await state.set_state(SilasSt.session)
    await state.update_data(bot='silas', sid=sid, dur=dur, start=datetime.now().timestamp())
    await db.clear_msgs(msg.from_user.id, 'silas')
    await db.reset_msg_counter(msg.from_user.id, 'silas')
    await msg.answer(
        f"🛋️ <b>Сеанс начат</b>\n\n"
        f"⏱ Длительность: {dur} мин\n\n"
        f"💬 Расскажите, что вас беспокоит:",
        reply_markup=reply.psycho_chat_kb()
    )

@router.message(SilasSt.duration, F.text == "◀️ Назад к Психологу")
async def dur_back(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.menu)
    await msg.answer("🛋️ <b>Психолог</b>\n\n✨ Готов выслушать", reply_markup=reply.psycho_kb(msg.from_user.id))

@router.message(SilasSt.mood, F.text == "Хорошо")
async def mood_good(msg: Message, state: FSMContext):
    await db.set_mood(msg.from_user.id, 'good')
    await state.set_state(SilasSt.menu)
    await msg.answer("✅ Настроение сохранено: 😊 Хорошо", reply_markup=reply.psycho_kb(msg.from_user.id))

@router.message(SilasSt.mood, F.text == "Устал")
async def mood_tired(msg: Message, state: FSMContext):
    await db.set_mood(msg.from_user.id, 'tired')
    await state.set_state(SilasSt.menu)
    await msg.answer("✅ Настроение сохранено: 😔 Устал", reply_markup=reply.psycho_kb(msg.from_user.id))

@router.message(SilasSt.mood, F.text == "Тяжело")
async def mood_pain(msg: Message, state: FSMContext):
    await db.set_mood(msg.from_user.id, 'pain')
    await state.set_state(SilasSt.menu)
    await msg.answer("✅ Настроение сохранено: 😰 Тяжело", reply_markup=reply.psycho_kb(msg.from_user.id))

@router.message(SilasSt.mood, F.text == "✏️ Ваше настроение")
async def mood_custom(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.custom)
    await msg.answer("✏️ Опишите ваше состояние (1-2 слова):")

@router.message(SilasSt.mood, F.text == "Статистика")
async def mood_stats(msg: Message):
    s = await db.get_mood_stats(msg.from_user.id)
    total = s['good'] + s['tired'] + s['pain']
    await msg.answer(
        f"📊 <b>Статистика за месяц</b>\n\n"
        f"😊 Хорошо: {s['good']}\n"
        f"😔 Устал: {s['tired']}\n"
        f"😰 Тяжело: {s['pain']}\n\n"
        f"📈 Всего записей: {total}"
    )

@router.message(SilasSt.mood, F.text == "◀️ Назад к Психологу")
async def mood_back(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.menu)
    await msg.answer("🛋️ <b>Психолог</b>", reply_markup=reply.psycho_kb(msg.from_user.id))

@router.message(SilasSt.custom)
async def custom_mood_input(msg: Message, state: FSMContext):
    words = len(msg.text.split())
    if words > 2:
        await msg.answer("⚠️ Пожалуйста, только 1-2 слова:")
        return
    await db.set_mood(msg.from_user.id, 'custom', msg.text)
    await state.set_state(SilasSt.menu)
    await msg.answer(f"✅ Настроение сохранено: <b>{msg.text}</b>", reply_markup=reply.psycho_kb(msg.from_user.id))

@router.message(SilasSt.session, F.text == "🛑 Завершить")
async def silas_stop(msg: Message, state: FSMContext):
    d = await state.get_data()
    await db.end_session(d.get('sid'))
    await state.set_state(SilasSt.menu)
    await msg.answer(
        "🙏 <b>Сеанс завершён</b>\n\nСпасибо за доверие. Берегите себя.",
        reply_markup=reply.psycho_kb(msg.from_user.id)
    )

@router.message(SilasSt.session, F.text == "🗑 Очистить")
async def silas_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'silas')
    await msg.answer("🗑 История очищена")

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
            if active_requests[user_id].get('status_msg'):
                await active_requests[user_id]['status_msg'].delete()
        except:
            pass
        # Удаляем сообщение пользователя
        try:
            await msg.delete()
        except:
            pass
        await msg.answer("❌ Запрос отменён", reply_markup=reply.psycho_chat_kb())
    else:
        await msg.answer("Нет активного запроса", reply_markup=reply.psycho_chat_kb())

@router.callback_query(F.data == "silas:tg")
async def silas_telegraph(cb: CallbackQuery):
    user_id = cb.from_user.id
    if user_id not in last_messages:
        await cb.answer("❌ Нет текста", show_alert=True)
        return
    await cb.answer("📖 Публикую на Telegraph...")
    data = last_messages[user_id]
    text = data['text']
    url = await create_telegraph_page("🛋️ Психолог — Сеанс", text)
    if url:
        await cb.message.answer(
            "📖 <b>Полный текст опубликован</b>",
            reply_markup=inline.titus_telegraph_kb(url)
        )
    else:
        await cb.message.answer("❌ Не удалось опубликовать")

async def process_silas_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    allowed, error_msg = await ai_flood.check(msg.from_user.id)
    if not allowed:
        await msg.answer(error_msg)
        return
    
    remaining = await db.get_available_tokens(msg.from_user.id)
    if remaining < MIN_TOKENS:
        await msg.answer("❌ Токены закончились!\n\n💎 Докупите в разделе 💠 Подписка", reply_markup=reply.main_kb(msg.from_user.id))
        return
    
    model = await db.get_user_model(msg.from_user.id)
    
    d = await state.get_data()
    el = int((datetime.now().timestamp() - d['start']) / 60)
    rem = d['dur'] - el
    
    if rem <= 0:
        await db.end_session(d['sid'])
        await state.set_state(SilasSt.menu)
        await msg.answer(
            "⏱ <b>Время сеанса истекло</b>\n\nСпасибо за работу над собой.",
            reply_markup=reply.psycho_kb(msg.from_user.id)
        )
        return
    
    user_id = msg.from_user.id
    request_state = {'cancelled': False, 'kb_msg': None, 'status_msg': None}
    active_requests[user_id] = request_state
    
    status_msg = await msg.answer("⏳ Обрабатываю...")
    request_state['status_msg'] = status_msg
    
    resp = None
    
    try:
        if request_state['cancelled']:
            return
        
        s = await db.get_user_bot(msg.from_user.id, 'silas')
        mood = MOODS.get(s['mood'], s.get('custom_mood') or 'не указано')
        mem = await db.get_memory(msg.from_user.id, 'silas')
        hist = await db.get_msgs(msg.from_user.id, 'silas')
        cnt = await db.inc_msg_counter(msg.from_user.id, 'silas')
        sys = SILAS_SYSTEM.format(mood=mood, duration=d['dur'], elapsed=el, remaining=rem, msg_count=cnt)
        sys += build_memory_context(mem)
        
        if rem <= 5:
            sys += "\n\nОсталось мало времени — начинайте завершение."
        if cnt >= 20:
            sys += "\n\nСвяжите с предыдущими беседами."
            await db.reset_msg_counter(msg.from_user.id, 'silas')
        
        msgs = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": text}]
        
        if request_state['cancelled']:
            return
        
        # УЛУЧШЕННЫЙ STREAMING
        if image_b64:
            resp, tok = await ask(msgs, model, image_b64)
        else:
            from utils.openrouter import ask_stream
            from utils.tokens import calculate_tokens
            import time
            
            full_response = ""
            sentence_buffer = ""
            displayed_text = ""
            last_update = time.time()
            typing_phase = 0
            stream_msg = None
            
            async for chunk in ask_stream(msgs, model, max_tokens=4000):
                if request_state['cancelled']:
                    return
                if not chunk:
                    continue
                
                full_response += chunk
                sentence_buffer += chunk
                now = time.time()
                
                if typing_phase == 0 and len(full_response) > 20:
                    typing_phase = 1
                    try:
                        await status_msg.edit_text("✍️ Печатаю...")
                    except:
                        pass
                
                if typing_phase == 1 and len(full_response) > 100:
                    typing_phase = 2
                    try:
                        await status_msg.delete()
                    except:
                        pass
                    stream_msg = await msg.answer("_Печатаю..._", parse_mode=None)
                
                if typing_phase == 2 and stream_msg:
                    if sentence_buffer.rstrip().endswith(('.', '!', '?', '\n\n')):
                        displayed_text += sentence_buffer
                        sentence_buffer = ""
                        
                        if now - last_update >= 0.5:
                            formatted = md_to_html(displayed_text)
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
            if status_msg and typing_phase < 2:
                try:
                    await status_msg.delete()
                except:
                    pass
        
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
        
        asyncio.create_task(update_memory(msg.from_user.id, 'silas', text, resp))
        
        last_messages[user_id] = {"text": resp}
        cleanup_cache(last_messages)  # Предотвращаем утечку памяти
        
    finally:
        active_requests.pop(user_id, None)
    
    if resp:
        resp_html = md_to_html(resp)
        footer = "\n\n<i>🛋️ Психолог</i>"
        
        # Проверяем, нужно ли превью
        needs_preview, display_text = should_show_preview(resp_html, max_length=3000)
        
        if needs_preview:
            display_text = md_to_html(display_text)
        
        # Получаем кнопку для просмотра диалога
        keyboard = get_chat_button(conv_id, len(resp_html))
        
        # Отправляем ответ
        await msg.answer(f"{display_text}{footer}", reply_markup=keyboard)

@router.message(SilasSt.session, F.text)
async def silas_text(msg: Message, state: FSMContext):
    await process_silas_message(msg, state, msg.text)

@router.message(SilasSt.session, F.voice)
async def silas_voice(msg: Message, state: FSMContext):
    sec = 0
    st = await msg.answer("🎧 Слушаю... (0 сек)")
    
    running = True
    async def update_voice_counter():
        nonlocal sec
        while running:
            await asyncio.sleep(1)
            if not running:
                break
            sec += 1
            try:
                await st.edit_text(f"🎧 Слушаю... ({sec} сек)")
            except:
                break
    
    counter_task = asyncio.create_task(update_voice_counter())
    
    try:
        fp = await download_voice(bot, msg.voice.file_id)
        text = await transcribe_voice(fp)
        running = False
        counter_task.cancel()
        if not text:
            await st.edit_text("❌ Не распознано")
            return
        await st.delete()
    except Exception as e:
        running = False
        counter_task.cancel()
        await st.edit_text(f"❌ {e}")
        return
    await process_silas_message(msg, state, text)

@router.message(SilasSt.session, F.photo)
async def silas_photo(msg: Message, state: FSMContext):
    sec = 0
    st = await msg.answer("🔎 Смотрю фото... (0 сек)")
    
    running = True
    async def update_photo_counter():
        nonlocal sec
        while running:
            await asyncio.sleep(1)
            if not running:
                break
            sec += 1
            try:
                await st.edit_text(f"🔎 Смотрю фото... ({sec} сек)")
            except:
                break
    
    counter_task = asyncio.create_task(update_photo_counter())
    
    try:
        photo = msg.photo[-1]
        file = await bot.get_file(photo.file_id)
        data = await bot.download_file(file.file_path)
        b64 = base64.b64encode(data.read()).decode()
        running = False
        counter_task.cancel()
        await st.delete()
    except Exception as e:
        running = False
        counter_task.cancel()
        await st.edit_text(f"❌ {e}")
        return
    await process_silas_message(msg, state, msg.caption or "Опишите что вы видите", b64)
