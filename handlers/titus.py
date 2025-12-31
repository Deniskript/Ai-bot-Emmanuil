import re
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import reply
from utils.ai_client import ask
from utils.memory import update_memory, build_memory_context
from utils.voice import download_voice, transcribe_voice
from prompts.all_prompts import TITUS_BASE
from config import MIN_TOKENS
from loader import bot
import asyncio
import base64


router = Router()


class TitusSt(StatesGroup):
    menu = State()
    chat = State()
    new_course = State()
    select_steps = State()
    courses_menu = State()
    continue_course = State()
    delete_course = State()


@router.message(F.text == "📓 Titus")
async def titus_enter(msg: Message, state: FSMContext):
    cfg = await db.get_bot_cfg('titus')
    if not cfg['enabled']:
        await msg.answer("🔴 Titus временно недоступен")
        return
    await state.set_state(TitusSt.menu)
    await msg.answer(
        f"📚 <b>Titus — эксперт</b>\n\n🤖 Модель: {cfg['model']}",
        reply_markup=reply.titus_kb()
    )


# === НОВЫЙ КУРС ===
@router.message(TitusSt.menu, F.text == "📝 Новый курс")
async def titus_new_course(msg: Message, state: FSMContext):
    courses = await db.get_courses(msg.from_user.id)
    active = [c for c in courses if not c['done']]
    if len(active) >= 5:
        await msg.answer("❌ Максимум 5 курсов!\n\nУдалите старый в «📂 Ваши курсы»")
        return
    await state.set_state(TitusSt.new_course)
    await msg.answer("📝 <b>Напиши тему курса:</b>", reply_markup=reply.back_kb())


@router.message(TitusSt.new_course, F.text == "◀️ Назад")
async def new_course_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.menu)
    cfg = await db.get_bot_cfg('titus')
    await msg.answer(f"📚 <b>Titus</b>\n\n🤖 Модель: {cfg['model']}", reply_markup=reply.titus_kb())


@router.message(TitusSt.new_course, F.text)
async def titus_course_name(msg: Message, state: FSMContext):
    await state.update_data(cname=msg.text)
    await state.set_state(TitusSt.select_steps)
    await msg.answer(f"📓 <b>{msg.text}</b>\n\nВыбери глубину:", reply_markup=reply.titus_steps_kb())


@router.message(TitusSt.select_steps, F.text == "◀️ Назад")
async def steps_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.new_course)
    await msg.answer("📝 <b>Напиши тему курса:</b>", reply_markup=reply.back_kb())


@router.message(TitusSt.select_steps, F.text.in_({"🚀 10 шагов", "📘 40 шагов", "📖 80 шагов"}))
async def create_course(msg: Message, state: FSMContext):
    steps_map = {"🚀 10 шагов": 10, "📘 40 шагов": 40, "📖 80 шагов": 80}
    steps = steps_map[msg.text]
    data = await state.get_data()
    cname = data['cname']
    
    cid = await db.create_course(msg.from_user.id, cname, steps)
    await state.set_state(TitusSt.chat)
    await state.update_data(cid=cid)
    await db.clear_msgs(msg.from_user.id, 'titus')
    
    await msg.answer(f"✅ Курс создан!\n\n📓 {cname}\n📊 Шагов: {steps}", reply_markup=reply.titus_chat_kb())
    
    cfg = await db.get_bot_cfg('titus')
    sys = TITUS_BASE + f"\n\nКурс: {cname}. Шаг 1 из {steps}."
    msgs = [{"role": "system", "content": sys}, {"role": "user", "content": "Начни шаг 1"}]
    resp, tok = await ask(msgs, cfg['model'])
    await db.update_tokens(msg.from_user.id, tok)
    await db.add_msg(msg.from_user.id, 'titus', 'assistant', resp)
    await msg.answer(resp)


# === ВАШИ КУРСЫ ===
@router.message(TitusSt.menu, F.text == "📂 Ваши курсы")
async def my_courses(msg: Message, state: FSMContext):
    courses = await db.get_courses(msg.from_user.id)
    if not courses:
        await msg.answer("📂 Курсов пока нет")
        return
    await state.set_state(TitusSt.courses_menu)
    await state.update_data(courses=[dict(c) for c in courses])
    await msg.answer("📂 <b>Что сделать?</b>", reply_markup=reply.courses_action_kb())


@router.message(TitusSt.courses_menu, F.text == "◀️ Назад")
async def courses_menu_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.menu)
    cfg = await db.get_bot_cfg('titus')
    await msg.answer(f"📚 <b>Titus</b>", reply_markup=reply.titus_kb())


@router.message(TitusSt.courses_menu, F.text == "▶️ Продолжить курс")
async def continue_menu(msg: Message, state: FSMContext):
    data = await state.get_data()
    courses = [c for c in data.get('courses', []) if not c['done']]
    if not courses:
        await msg.answer("📂 Нет активных курсов")
        return
    await state.set_state(TitusSt.continue_course)
    await state.update_data(active_courses=courses)
    await msg.answer("▶️ <b>Выбери курс:</b>", reply_markup=reply.courses_list_kb(courses))


@router.message(TitusSt.courses_menu, F.text == "🗑 Удалить курс")
async def delete_menu(msg: Message, state: FSMContext):
    data = await state.get_data()
    courses = data.get('courses', [])
    if not courses:
        await msg.answer("📂 Нет курсов")
        return
    await state.set_state(TitusSt.delete_course)
    await state.update_data(del_courses=courses)
    await msg.answer("🗑 <b>Выбери курс для удаления:</b>", reply_markup=reply.courses_list_kb(courses))


# ПРОДОЛЖИТЬ
@router.message(TitusSt.continue_course, F.text == "◀️ Назад")
async def continue_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.courses_menu)
    await msg.answer("📂 <b>Что сделать?</b>", reply_markup=reply.courses_action_kb())


@router.message(TitusSt.continue_course, F.text)
async def continue_select(msg: Message, state: FSMContext):
    data = await state.get_data()
    courses = data.get('active_courses', [])
    try:
        num = int(msg.text.split(".")[0]) - 1
        if 0 <= num < len(courses):
            course = courses[num]
            await state.set_state(TitusSt.chat)
            await state.update_data(cid=course['id'], cname=course['name'])
            await db.clear_msgs(msg.from_user.id, 'titus')
            await msg.answer(
                f"📓 <b>{course['name']}</b>\n📊 Шаг {course['current']}/{course['total']}",
                reply_markup=reply.titus_chat_kb()
            )
            return
    except:
        pass
    await msg.answer("❌ Выбери курс из списка")


# УДАЛИТЬ
@router.message(TitusSt.delete_course, F.text == "◀️ Назад")
async def delete_back(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.courses_menu)
    await msg.answer("📂 <b>Что сделать?</b>", reply_markup=reply.courses_action_kb())


@router.message(TitusSt.delete_course, F.text)
async def delete_select(msg: Message, state: FSMContext):
    data = await state.get_data()
    courses = data.get('del_courses', [])
    
    # Извлекаем первую цифру из текста
    match = re.match(r'^(\d+)', msg.text.strip())
    if match:
        num = int(match.group(1)) - 1
        if 0 <= num < len(courses):
            course = courses[num]
            await db.delete_course(course['id'])
            await msg.answer(f"🗑 Курс «{course['name']}» удалён!")
            await state.set_state(TitusSt.menu)
            await msg.answer("📚 <b>Titus</b>", reply_markup=reply.titus_kb())
            return
    await msg.answer("❌ Выбери курс из списка")


# === ОСТАЛЬНОЕ ===
@router.message(TitusSt.menu, F.text == "❓ Помощь")
async def titus_help(msg: Message):
    await msg.answer("📚 <b>Titus</b>\n\n• 📝 Новый курс — создать\n• 📂 Ваши курсы — продолжить/удалить")


@router.message(TitusSt.menu, F.text == "◀️ Назад")
async def titus_back(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("🤖 Выбери бота:", reply_markup=reply.bots_menu_kb())


@router.message(TitusSt.chat, F.text == "🛑 Завершить")
async def titus_stop(msg: Message, state: FSMContext):
    await state.set_state(TitusSt.menu)
    await msg.answer("👋 Курс сохранён!", reply_markup=reply.titus_kb())


@router.message(TitusSt.chat, F.text == "🗑 Очистить")
async def titus_clear(msg: Message):
    await db.clear_msgs(msg.from_user.id, 'titus')
    await msg.answer("🗑 Очищено!")


async def process_titus_message(msg: Message, state: FSMContext, text: str, image_b64: str = None):
    u = await db.get_user(msg.from_user.id)
    if not u or u['tokens'] < MIN_TOKENS:
        await msg.answer("❌ Недостаточно токенов!")
        return
    
    data = await state.get_data()
    cid = data.get('cid')
    
    start_time = asyncio.get_event_loop().time()
    status_msg = await msg.answer("📓 Думаю...")
    
    async def update_status():
        while True:
            await asyncio.sleep(1)
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            try:
                await status_msg.edit_text(f"📓 Думаю... {elapsed} сек")
            except:
                break
    
    status_task = asyncio.create_task(update_status())
    try:
        cfg = await db.get_bot_cfg('titus')
        mem = await db.get_memory(msg.from_user.id, 'titus')
        hist = await db.get_msgs(msg.from_user.id, 'titus')
        
        course_info = ""
        if cid:
            course = await db.get_course(cid)
            if course:
                course_info = f"\n\nКурс: {course['name']}. Шаг {course['current']} из {course['total']}."
        
        sys = TITUS_BASE + build_memory_context(mem) + course_info
        msgs = [{"role": "system", "content": sys}] + hist + [{"role": "user", "content": text}]
        resp, tok = await ask(msgs, cfg['model'], image_b64)
        await db.update_tokens(msg.from_user.id, tok)
        await db.add_msg(msg.from_user.id, 'titus', 'user', text)
        await db.add_msg(msg.from_user.id, 'titus', 'assistant', resp)
        asyncio.create_task(update_memory(msg.from_user.id, 'titus', text, resp))
        
        if cid:
            course = await db.get_course(cid)
            if course and ("следующий шаг" in resp.lower() or "правильно" in resp.lower()):
                new_step = course['current'] + 1
                if new_step > course['total']:
                    await db.complete_course(cid)
                    await msg.answer("🎉 <b>Курс завершён!</b>")
                else:
                    await db.update_course_step(cid, new_step)
    finally:
        status_task.cancel()
        try:
            await status_msg.delete()
        except:
            pass
    
    elapsed = int(asyncio.get_event_loop().time() - start_time)
    await msg.answer(f"{resp}\n\n<i>📓 Titus | ⏱ {elapsed} сек</i>")


@router.message(TitusSt.chat, F.text)
async def titus_text(msg: Message, state: FSMContext):
    await process_titus_message(msg, state, msg.text)


@router.message(TitusSt.chat, F.voice)
async def titus_voice(msg: Message, state: FSMContext):
    status = await msg.answer("🎤 Распознаю...")
    try:
        file_path = await download_voice(bot, msg.voice.file_id)
        text = await transcribe_voice(file_path)
        if not text:
            await status.edit_text("❌ Не распознано")
            return
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ {e}")
        return
    await process_titus_message(msg, state, text)


@router.message(TitusSt.chat, F.photo)
async def titus_photo(msg: Message, state: FSMContext):
    status = await msg.answer("📷 Анализирую...")
    try:
        photo = msg.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_data = await bot.download_file(file.file_path)
        image_b64 = base64.b64encode(file_data.read()).decode()
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ {e}")
        return
    text = msg.caption or "Что на изображении?"
    await process_titus_message(msg, state, text, image_b64)
