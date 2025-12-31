from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import reply
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
    menu = State()
    mood = State()
    custom = State()
    duration = State()
    session = State()

MOODS = {'good': SILAS_GOOD, 'tired': SILAS_TIRED, 'pain': SILAS_PAIN}

@router.message(F.text == "🛋️ Silas")
async def silas_enter(msg: Message, state: FSMContext):
    cfg = await db.get_bot_cfg('silas')
    if not cfg['enabled']:
        await msg.answer("Silas временно недоступен")
        return
    await state.set_state(SilasSt.menu)
    await msg.answer(f"<b>Silas — психолог</b>\n\nМодель: {cfg['model']}", reply_markup=reply.silas_kb())

@router.message(SilasSt.menu, F.text == "🛋️ Начать сеанс")
async def silas_start_session(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.duration)
    await msg.answer("<b>Выберите длительность сеанса:</b>", reply_markup=reply.silas_dur_kb())

@router.message(SilasSt.menu, F.text == "📔 Настроение")
async def silas_mood_menu(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.mood)
    await msg.answer("<b>Дневник настроения</b>\n\nКак вы себя сейчас чувствуете?", reply_markup=reply.silas_mood_kb())

@router.message(SilasSt.menu, F.text == "❓ Помощь")
async def silas_help(msg: Message):
    text = await db.get_text('help_silas')
    if not text:
        text = "<b>Silas</b> — AI-психолог для поддержки и самопознания"
    await msg.answer(text)

@router.message(SilasSt.menu, F.text == "◀️ Назад")
async def silas_back(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Выберите бота:", reply_markup=reply.bots_menu_kb())

@router.message(SilasSt.duration, F.text.in_({"15 минут", "30 минут", "60 минут"}))
async def silas_set_duration(msg: Message, state: FSMContext):
    dur_map = {"15 минут": 15, "30 минут": 30, "60 минут": 60}
    dur = dur_map.get(msg.text, 30)
    sid = await db.start_session(msg.from_user.id, dur)
    await state.set_state(SilasSt.session)
    await state.update_data(bot='silas', sid=sid, dur=dur, start=datetime.now().timestamp())
    await db.clear_msgs(msg.from_user.id, 'silas')
    await db.reset_msg_counter(msg.from_user.id, 'silas')
    await msg.answer(f"<b>Сеанс начат</b>\n\nДлительность: {dur} мин\n\nМожете начинать:", reply_markup=reply.silas_chat_kb())

@router.message(SilasSt.duration, F.text == "◀️ Назад к Silas")
async def dur_back(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.menu)
    cfg = await db.get_bot_cfg('silas')
    await msg.answer(f"<b>Silas</b>\n\nМодель: {cfg['model']}", reply_markup=reply.silas_kb())

@router.message(SilasSt.mood, F.text == "Хорошо")
async def mood_good(msg: Message, state: FSMContext):
    await db.set_mood(msg.from_user.id, 'good')
    await state.set_state(SilasSt.menu)
    await msg.answer("Настроение сохранено: Хорошо", reply_markup=reply.silas_kb())

@router.message(SilasSt.mood, F.text == "Устал")
async def mood_tired(msg: Message, state: FSMContext):
    await db.set_mood(msg.from_user.id, 'tired')
    await state.set_state(SilasSt.menu)
    await msg.answer("Настроение сохранено: Устал", reply_markup=reply.silas_kb())

@router.message(SilasSt.mood, F.text == "Тяжело")
async def mood_pain(msg: Message, state: FSMContext):
    await db.set_mood(msg.from_user.id, 'pain')
    await state.set_state(SilasSt.menu)
    await msg.answer("Настроение сохранено: Тяжело", reply_markup=reply.silas_kb())

@router.message(SilasSt.mood, F.text == "✏️Ваше настроение")
async def mood_custom(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.custom)
    await msg.answer("Опишите ваше состояние (1-2 слова):")

@router.message(SilasSt.mood, F.text == "Статистика")
async def mood_stats(msg: Message):
    s = await db.get_mood_stats(msg.from_user.id)
    total = s['good'] + s['tired'] + s['pain']
    await msg.answer(f"<b>Статистика за месяц</b>\n\nХорошо: {s['good']}\nУстал: {s['tired']}\nТяжело: {s['pain']}\n\nВсего: {total}")

@router.message(SilasSt.mood, F.text == "◀️ Назад к Silas")
async def mood_back(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.menu)
    cfg = await db.get_bot_cfg('silas')
    await msg.answer(f"<b>Silas</b>\n\nМодель: {cfg['model']}", reply_markup=reply.silas_kb())

@router.message(SilasSt.custom)
async def custom_mood_input(msg: Message, state: FSMContext):
    words = len(msg.text.split())
    if words > 2:
        await msg.answer("Пожалуйста, только 1-2 слова:")
        return
    await db.set_mood(msg.from_user.id, 'custom', msg.text)
    await state.set_state(SilasSt.menu)
    await msg.answer(f"Настроение сохранено: <b>{msg.text}</b>", reply_markup=reply.silas_kb())

@router.message(SilasSt.session, F.text == "🛑 Завершить")
async def silas_stop(msg: Message, state: FSMContext):
    d = await state.get_data()
    await db.end_session(d.get('sid'))
    await state.set_state(SilasSt.menu)
    await msg.answer("Сеанс завершён. Спасибо за доверие.", reply_markup=reply.silas_kb())

@router.message(SilasSt.session, F.text == "🗑 Очистить")
async def silas_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'silas')
    await msg.answer("История очищена.")

async def process_silas_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    u = await db.get_user(msg.from_user.id)
    if not u or u['tokens'] < MIN_TOKENS:
        await msg.answer("Недостаточно токенов.")
        return
    d = await state.get_data()
    el = int((datetime.now().timestamp() - d['start']) / 60)
    rem = d['dur'] - el
    if rem <= 0:
        await db.end_session(d['sid'])
        await state.set_state(SilasSt.menu)
        await msg.answer("Время сеанса истекло. Спасибо за работу.", reply_markup=reply.silas_kb())
        return
    start_time = asyncio.get_event_loop().time()
    status_msg = await msg.answer("Обрабатываю...")
    async def update_status():
        while True:
            await asyncio.sleep(1)
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            try:
                await status_msg.edit_text(f"Silas думает... {elapsed} сек")
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
            sys += "\n\nОсталось мало времени — начинайте завершение."
        if cnt >= 20:
            sys += "\n\nСвяжите с предыдущими беседами."
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
    await msg.answer(f"{resp}\n\n<i>Silas | {elapsed} сек</i>")
    if rem <= 5 and rem > 0:
        await msg.answer(f"Осталось {rem} мин")

@router.message(SilasSt.session, F.text)
async def silas_text(msg: Message, state: FSMContext):
    await process_silas_message(msg, state, msg.text)

@router.message(SilasSt.session, F.voice)
async def silas_voice(msg: Message, state: FSMContext):
    st = await msg.answer("Распознаю голос...")
    try:
        fp = await download_voice(bot, msg.voice.file_id)
        text = await transcribe_voice(fp)
        if not text:
            await st.edit_text("Не удалось распознать")
            return
        await st.delete()
    except Exception as e:
        await st.edit_text(f"Ошибка: {e}")
        return
    await process_silas_message(msg, state, text)

@router.message(SilasSt.session, F.photo)
async def silas_photo(msg: Message, state: FSMContext):
    st = await msg.answer("Анализирую изображение...")
    try:
        photo = msg.photo[-1]
        file = await bot.get_file(photo.file_id)
        data = await bot.download_file(file.file_path)
        b64 = base64.b64encode(data.read()).decode()
        await st.delete()
    except Exception as e:
        await st.edit_text(f"Ошибка: {e}")
        return
    await process_silas_message(msg, state, msg.caption or "Опишите что вы видите", b64)
