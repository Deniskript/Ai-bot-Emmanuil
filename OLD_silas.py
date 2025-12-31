from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import inline
from utils.ai_client import ask
from utils.memory import update_memory, build_memory_context
from utils.voice import download_voice, transcribe_voice
from prompts.all_prompts import SILAS_BASE, SILAS_GOOD, SILAS_TIRED, SILAS_PAIN
from config import MIN_TOKENS
from loader import bot
from datetime import datetime
import asyncio
import base64


router = Router()


class SilasSt(StatesGroup):
    session = State()
    custom = State()


MOODS = {'good': SILAS_GOOD, 'tired': SILAS_TIRED, 'pain': SILAS_PAIN}


@router.callback_query(F.data == "bot:silas")
async def silas_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    cfg = await db.get_bot_cfg('silas')
    if not cfg['enabled']:
        await cb.answer("🔴 Silas временно недоступен", show_alert=True)
        return
    await cb.message.edit_text(
        f"🧠 <b>Silas — психолог</b>\n\n"
        f"Модель: {cfg['model']}\n\n"
        f"Выберите действие:",
        reply_markup=inline.silas_kb()
    )


@router.callback_query(F.data == "silas:diary")
async def silas_diary(cb: CallbackQuery):
    await cb.message.edit_text("📔 <b>Дневник настроения</b>\n\nКак ты себя сейчас чувствуешь?", reply_markup=inline.silas_diary_kb())


@router.callback_query(F.data.startswith("mood:"))
async def set_mood(cb: CallbackQuery, state: FSMContext):
    m = cb.data.split(":")[1]
    if m == "custom":
        await cb.message.edit_text(
            "✏️ <b>Своё состояние</b>\n\n"
            "Напиши 1-2 слова.\n"
            "Например: «тревожно» или «странно пусто»",
            reply_markup=inline.back_kb("silas:diary")
        )
        await state.set_state(SilasSt.custom)
        return
    await db.set_mood(cb.from_user.id, m)
    mood_text = {'good': '😊 Хорошо/Спокойно', 'tired': '😔 Устал/Пусто', 'pain': '😰 Больно/Страшно'}
    await cb.answer(f"✅ Сохранено: {mood_text.get(m)}")
    await cb.message.edit_text("🧠 <b>Silas — психолог</b>\n\nВыберите действие:", reply_markup=inline.silas_kb())


@router.message(SilasSt.custom)
async def custom_mood(msg: Message, state: FSMContext):
    words = len(msg.text.split())
    if words > 2:
        await msg.answer("❌ Пожалуйста, напиши только 1-2 слова. Попробуй ещё раз.")
        return
    await db.set_mood(msg.from_user.id, 'custom', msg.text)
    await state.clear()
    await msg.answer(f"✅ Состояние сохранено: <b>{msg.text}</b>", reply_markup=inline.silas_kb())


@router.callback_query(F.data == "silas:stats")
async def silas_stats(cb: CallbackQuery):
    s = await db.get_mood_stats(cb.from_user.id)
    total = s['good'] + s['tired'] + s['pain']
    await cb.message.edit_text(
        f"📊 <b>Статистика за месяц</b>\n\n"
        f"😊 Хорошо/Спокойно: {s['good']} раз\n"
        f"😔 Устал/Пусто: {s['tired']} раз\n"
        f"😰 Больно/Страшно: {s['pain']} раз\n\n"
        f"Всего записей: {total}",
        reply_markup=inline.back_kb("silas:diary")
    )


@router.callback_query(F.data == "silas:session")
async def silas_session(cb: CallbackQuery):
    await cb.message.edit_text("⏱ <b>Выберите длительность сеанса:</b>", reply_markup=inline.silas_dur_kb())


@router.callback_query(F.data.startswith("ses:"))
async def start_ses(cb: CallbackQuery, state: FSMContext):
    dur = int(cb.data.split(":")[1])
    sid = await db.start_session(cb.from_user.id, dur)
    await state.set_state(SilasSt.session)
    await state.update_data(bot='silas', sid=sid, dur=dur, start=datetime.now().timestamp())
    await db.clear_msgs(cb.from_user.id, 'silas')
    await db.reset_msg_counter(cb.from_user.id, 'silas')
    await cb.message.edit_text(
        f"🎯 <b>Сеанс начат</b>\n\n"
        f"⏱ Длительность: {dur} мин\n\n"
        f"Можешь писать текст, отправлять голосовые или фото.\n\n"
        f"/stop — завершить сеанс"
    )


async def process_silas_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    """Обработка сообщения Silas"""
    u = await db.get_user(msg.from_user.id)
    if not u or u['tokens'] < MIN_TOKENS:
        await msg.answer("❌ Недостаточно токенов.")
        return
    
    d = await state.get_data()
    el = int((datetime.now().timestamp() - d['start']) / 60)
    rem = d['dur'] - el
    
    if rem <= 0:
        await db.end_session(d['sid'])
        await state.clear()
        await msg.answer("⏱ Время сеанса вышло.\n\nСпасибо за работу. До встречи!", reply_markup=inline.silas_kb())
        return
    
    # Статус с таймером
    start_time = asyncio.get_event_loop().time()
    status_msg = await msg.answer("🔎 Обрабатываю... 0 сек")
    
    async def update_status():
        while True:
            await asyncio.sleep(1)
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            try:
                await status_msg.edit_text(f"🧠 Silas думает... {elapsed} сек")
            except:
                break
    
    status_task = asyncio.create_task(update_status())
    
    try:
        cfg = await db.get_bot_cfg('silas')
        s = await db.get_user_bot(msg.from_user.id, 'silas')
        mood = MOODS.get(s['mood'], s.get('custom_mood') or 'не указано')
        mem = await db.get_memory(msg.from_user.id, 'silas')
        hist = await db.get_msgs(msg.from_user.id, 'silas')
        cnt = await db.inc_msg_counter(msg.from_user.id, 'silas')
        
        sys = SILAS_BASE.format(mood=mood, duration=d['dur'], elapsed=el, remaining=rem)
        sys += build_memory_context(mem)
        
        if rem <= 5:
            sys += "\n\n⚠️ Осталось мало времени — начинай завершение сеанса."
        if cnt >= 20:
            sys += "\n\n⚡ Пора связать с чем-то из прошлых бесед."
            await db.reset_msg_counter(msg.from_user.id, 'silas')
        
        msgs = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": text}]
        resp, tok = await ask(msgs, cfg['model'], image_b64)
        
        await db.update_tokens(msg.from_user.id, tok)
        await db.add_msg(msg.from_user.id, 'silas', 'user', text)
        await db.add_msg(msg.from_user.id, 'silas', 'assistant', resp)
        
        asyncio.create_task(update_memory(msg.from_user.id, 'silas', text, resp))
        
    finally:
        status_task.cancel()
        try:
            await status_msg.delete()
        except:
            pass
    
    elapsed = int(asyncio.get_event_loop().time() - start_time)
    await msg.answer(f"{resp}\n\n<i>🧠 Silas | ⏱ {elapsed} сек</i>")
    
    if rem <= 5 and rem > 0:
        await msg.answer(f"⏰ Осталось {rem} мин до конца сеанса")


@router.message(SilasSt.session, F.text)
async def silas_chat_text(msg: Message, state: FSMContext):
    if msg.text.startswith("/"):
        if msg.text == "/stop":
            d = await state.get_data()
            await db.end_session(d['sid'])
            await state.clear()
            await msg.answer("👋 Сеанс завершён.\n\nСпасибо за доверие. Береги себя.", reply_markup=inline.silas_kb())
        return
    
    await process_silas_message(msg, state, msg.text)


@router.message(SilasSt.session, F.voice)
async def silas_chat_voice(msg: Message, state: FSMContext):
    status = await msg.answer("🎤 Распознаю голос...")
    
    try:
        file_path = await download_voice(bot, msg.voice.file_id)
        if not file_path:
            await status.edit_text("❌ Не удалось скачать голосовое")
            return
        
        text = await transcribe_voice(file_path)
        if not text:
            await status.edit_text("❌ Не удалось распознать речь")
            return
        
        await status.delete()
        
    except Exception as e:
        await status.edit_text(f"❌ Ошибка: {e}")
        return
    
    await process_silas_message(msg, state, text)


@router.message(SilasSt.session, F.photo)
async def silas_chat_photo(msg: Message, state: FSMContext):
    status = await msg.answer("📷 Анализирую фото...")
    
    try:
        photo = msg.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_data = await bot.download_file(file.file_path)
        image_b64 = base64.b64encode(file_data.read()).decode()
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ Ошибка: {e}")
        return
    
    text = msg.caption or "Опиши что ты видишь на этом фото и как это может быть связано с моим состоянием."
    await process_silas_message(msg, state, text, image_b64)
