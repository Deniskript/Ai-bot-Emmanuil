from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import reply, inline
from utils.ai_client import ask
from utils.memory import update_memory, build_memory_context
from utils.voice import download_voice, transcribe_voice
from utils.antiflood import ai_flood
from utils.telegraph import create_telegraph_page, make_preview
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
active_requests = {}
last_messages = {}


@router.message(F.text == "🛋️ Психолог")
async def silas_enter(msg: Message, state: FSMContext):
    cfg = await db.get_bot_cfg('silas')
    if not cfg['enabled']:
        await msg.answer("🔴 Психолог временно недоступен")
        return
    await state.set_state(SilasSt.menu)
    await msg.answer(
        "🛋️ <b>Психолог — твоё безопасное пространство</b>\n\n"
        "🌙 Здесь можно быть собой\n"
        "✨ Без осуждений, только поддержка",
        reply_markup=reply.psycho_kb()
    )


@router.message(SilasSt.menu, F.text == "🛋️ Начать сеанс")
async def silas_start_session(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.duration)
    await msg.answer("⏱ <b>Выберите длительность сеанса:</b>", reply_markup=reply.psycho_dur_kb())


@router.message(SilasSt.menu, F.text == "📔 Настроение")
async def silas_mood_menu(msg: Message, state: FSMContext):
    await state.set_state(SilasSt.mood)
    await msg.answer("📔 <b>Дневник настроения</b>\n\nКак вы себя сейчас чувствуете?", reply_markup=reply.psycho_mood_kb())


@router.message(SilasSt.menu, F.text == "❓ Помощь")
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
    await msg.answer("🛋️ <b>Психолог</b>\n\n✨ Готов выслушать", reply_markup=reply.psycho_kb())


@router.message(SilasSt.mood, F.text == "Хорошо")
async def mood_good(msg: Message, state: FSMContext):
    await db.set_mood(msg.from_user.id, 'good')
    await state.set_state(SilasSt.menu)
    await msg.answer("✅ Настроение сохранено: 😊 Хорошо", reply_markup=reply.psycho_kb())


@router.message(SilasSt.mood, F.text == "Устал")
async def mood_tired(msg: Message, state: FSMContext):
    await db.set_mood(msg.from_user.id, 'tired')
    await state.set_state(SilasSt.menu)
    await msg.answer("✅ Настроение сохранено: 😔 Устал", reply_markup=reply.psycho_kb())


@router.message(SilasSt.mood, F.text == "Тяжело")
async def mood_pain(msg: Message, state: FSMContext):
    await db.set_mood(msg.from_user.id, 'pain')
    await state.set_state(SilasSt.menu)
    await msg.answer("✅ Настроение сохранено: 😰 Тяжело", reply_markup=reply.psycho_kb())


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
    await msg.answer("🛋️ <b>Психолог</b>", reply_markup=reply.psycho_kb())


@router.message(SilasSt.custom)
async def custom_mood_input(msg: Message, state: FSMContext):
    words = len(msg.text.split())
    if words > 2:
        await msg.answer("⚠️ Пожалуйста, только 1-2 слова:")
        return
    await db.set_mood(msg.from_user.id, 'custom', msg.text)
    await state.set_state(SilasSt.menu)
    await msg.answer(f"✅ Настроение сохранено: <b>{msg.text}</b>", reply_markup=reply.psycho_kb())


@router.message(SilasSt.session, F.text == "🛑 Завершить")
async def silas_stop(msg: Message, state: FSMContext):
    d = await state.get_data()
    await db.end_session(d.get('sid'))
    await state.set_state(SilasSt.menu)
    await msg.answer(
        "🙏 <b>Сеанс завершён</b>\n\nСпасибо за доверие. Берегите себя.",
        reply_markup=reply.psycho_kb()
    )


@router.message(SilasSt.session, F.text == "🗑 Очистить")
async def silas_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'silas')
    await msg.answer("🗑 История очищена")


@router.message(SilasSt.session, F.text == "⌛️ Отменить запрос")
async def silas_cancel(msg: Message):
    user_id = msg.from_user.id
    if user_id in active_requests:
        active_requests[user_id] = True
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
    
    u = await db.get_user(msg.from_user.id)
    if not u or u['tokens'] < MIN_TOKENS:
        await msg.answer("❌ Недостаточно токенов")
        return
    
    d = await state.get_data()
    el = int((datetime.now().timestamp() - d['start']) / 60)
    rem = d['dur'] - el
    
    if rem <= 0:
        await db.end_session(d['sid'])
        await state.set_state(SilasSt.menu)
        await msg.answer(
            "⏱ <b>Время сеанса истекло</b>\n\nСпасибо за работу над собой.",
            reply_markup=reply.psycho_kb()
        )
        return
    
    user_id = msg.from_user.id
    active_requests[user_id] = False
    
    status_msg = await msg.answer("✍️ Печатаю...", reply_markup=reply.cancel_kb())
    
    resp = None
    try:
        if active_requests.get(user_id, False):
            return
        
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
        
        if active_requests.get(user_id, False):
            return
        
        resp, tok = await ask(msgs, cfg['model'], image_b64)
        
        if active_requests.get(user_id, False):
            return
        
        await db.update_tokens(msg.from_user.id, tok)
        await db.add_msg(msg.from_user.id, 'silas', 'user', text)
        await db.add_msg(msg.from_user.id, 'silas', 'assistant', resp)
        asyncio.create_task(update_memory(msg.from_user.id, 'silas', text, resp))
        
        last_messages[user_id] = {"text": resp}
        
    finally:
        try:
            await status_msg.delete()
        except:
            pass
        active_requests.pop(user_id, None)
    
    if resp:
        has_tg = len(resp) >= 3000
        footer = f"\n\n<i>🛋️ Психолог</i>"
        if rem <= 5 and rem > 0:
            footer += f"\n⏱ Осталось {rem} мин"
        
        if has_tg:
            preview = make_preview(resp, 800)
            await msg.answer(
                f"{preview}{footer}",
                reply_markup=inline.silas_msg_kb(has_telegraph=True)
            )
        else:
            await msg.answer(f"{resp}{footer}", reply_markup=reply.psycho_chat_kb())


@router.message(SilasSt.session, F.text)
async def silas_text(msg: Message, state: FSMContext):
    await process_silas_message(msg, state, msg.text)


@router.message(SilasSt.session, F.voice)
async def silas_voice(msg: Message, state: FSMContext):
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
    await process_silas_message(msg, state, text)


@router.message(SilasSt.session, F.photo)
async def silas_photo(msg: Message, state: FSMContext):
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
    await process_silas_message(msg, state, msg.caption or "Опишите что вы видите", b64)
