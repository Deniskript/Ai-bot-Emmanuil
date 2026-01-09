from aiogram import Router, F
import psutil
import subprocess
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loader import bot
from database import db
from keyboards import inline
from config import ADMIN_IDS

router = Router()

class Adm(StatesGroup):
    find = State()
    bc_text = State()
    bc_filter = State()
    prompt_edit = State()
    git_msg = State()

class MemEdit(StatesGroup):
    search = State()
    edit_fact = State()
    add_fact = State()

class GiveSub(StatesGroup):
    user_id = State()

def is_adm(uid):
    return uid in ADMIN_IDS

def fmt(n):
    return f"{n:,}".replace(",", " ")

# === ОСНОВНОЕ ===

@router.message(Command("admin"))
async def admin_cmd(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    await state.clear()
    await msg.answer("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=inline.admin_kb())

@router.callback_query(F.data == "adm:close")
async def close(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    await state.clear()
    await cb.message.delete()

@router.callback_query(F.data == "adm:back")
async def back(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    await state.clear()
    await cb.message.edit_text("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=inline.admin_kb())

# === СТАТИСТИКА ===

@router.callback_query(F.data == "adm:stats")
async def stats(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    
    # Общая статистика
    total_users = await db.count_users()
    blocked = await db.get_blocked_count()
    
    # Подписки
    mini_count = await db.count_subscribers_by_type('mini')
    standard_count = await db.count_subscribers_by_type('standard')
    total_subs = mini_count + standard_count
    
    # Токены
    total_tokens_used = await db.get_total_tokens_used()
    
    await cb.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: {fmt(total_users)}\n"
        f"🚫 Заблокировано: {blocked}\n\n"
        f"💎 <b>Подписки:</b>\n"
        f"├ 🔵 Mini (Sonnet): {mini_count}\n"
        f"├ 🟣 Standard (Opus): {standard_count}\n"
        f"└ Всего: {total_subs}\n\n"
        f"📈 Токенов использовано: {fmt(total_tokens_used)}",
        reply_markup=inline.back_kb("adm:back"))

# === НАГРУЗКА ===

@router.callback_query(F.data == "adm:load")
async def load(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    if cpu < 50:
        status = "🟢 Нормальная"
    elif cpu < 80:
        status = "🟡 Средняя"
    else:
        status = "🔴 Высокая"
    
    await cb.message.edit_text(
        f"📈 <b>Нагрузка</b>\n\n"
        f"💻 CPU: {cpu}%\n"
        f"🧠 RAM: {mem.percent}% ({mem.used // (1024**3)}/{mem.total // (1024**3)} GB)\n"
        f"💾 Диск: {disk.percent}%\n\n"
        f"Статус: {status}",
        reply_markup=inline.back_kb("adm:back"))

# === АНТИФЛУД ===

@router.callback_query(F.data == "adm:spam")
async def spam_settings(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    interval = int(await db.get_setting('spam_interval') or '2')
    max_rpm = int(await db.get_setting('spam_max_rpm') or '8')
    blocked = await db.get_blocked_count()
    await cb.message.edit_text(
        f"🛡 <b>Антифлуд</b>\n\n"
        f"⏱ Интервал: {interval} сек\n"
        f"📨 Макс сообщений/мин: {max_rpm}\n"
        f"🚫 Заблокировано: {blocked}",
        reply_markup=inline.spam_kb(interval, max_rpm, blocked))

@router.callback_query(F.data == "sp:info")
async def sp_info(cb: CallbackQuery):
    await cb.answer("Используйте + и - для изменения")

@router.callback_query(F.data.startswith("sp:int:"))
async def sp_interval(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    act = cb.data.split(":")[2]
    cur = int(await db.get_setting('spam_interval') or '2')
    new = max(1, cur + (1 if act == "+1" else -1))
    await db.set_setting('spam_interval', str(new))
    await cb.answer(f"Интервал: {new} сек")
    await spam_settings(cb)

@router.callback_query(F.data.startswith("sp:rpm:"))
async def sp_rpm(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    act = cb.data.split(":")[2]
    cur = int(await db.get_setting('spam_max_rpm') or '8')
    new = max(1, cur + (1 if act == "+1" else -1))
    await db.set_setting('spam_max_rpm', str(new))
    await cb.answer(f"Макс/мин: {new}")
    await spam_settings(cb)

@router.callback_query(F.data == "spam:list")
async def spam_list(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    users = await db.get_blocked_users()
    if not users:
        await cb.answer("Нет заблокированных")
        return
    txt = "🚫 <b>Заблокированные:</b>\n\n"
    for u in users[:20]:
        txt += f"• {u['user_id']} (@{u['username'] or '—'})\n"
    await cb.message.edit_text(txt, reply_markup=inline.back_kb("adm:spam"))

@router.callback_query(F.data == "spam:unblock")
async def spam_unblock_menu(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    users = await db.get_blocked_users()
    if not users:
        await cb.answer("Нет заблокированных")
        return
    await cb.message.edit_text(
        "🔓 Введите ID для разблокировки:\n\n" +
        "\n".join([f"• {u['user_id']}" for u in users[:10]]),
        reply_markup=inline.back_kb("adm:spam"))

# === ЮЗЕРЫ ===

@router.callback_query(F.data == "adm:users")
async def users_list(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    users = await db.get_all_users()
    total = len(users)
    txt = f"👥 <b>Пользователи ({total})</b>\n\n"
    for u in users[:15]:
        status = "🚫" if u.get('is_blocked') else "✅"
        sub = await db.get_subscription(u['user_id'])
        sub_icon = ""
        if sub and sub.get('is_active'):
            sub_icon = "🔵" if sub['type'] == 'mini' else "🟣"
        txt += f"{status}{sub_icon} <code>{u['user_id']}</code>\n"
    if total > 15:
        txt += f"\n... и ещё {total - 15}"
    await cb.message.edit_text(txt, reply_markup=inline.back_kb("adm:back"))

@router.callback_query(F.data == "adm:find")
async def find_start(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    await cb.message.edit_text("🔍 <b>Поиск</b>\n\nВведите ID пользователя:")
    await state.set_state(Adm.find)

@router.message(Adm.find)
async def find_user(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    try:
        uid = int(msg.text)
        u = await db.get_user(uid)
        if not u:
            await msg.answer("❌ Не найден", reply_markup=inline.back_kb("adm:back"))
        else:
            sub = await db.get_subscription(uid)
            sub_info = "❌ Нет"
            if sub and sub.get('is_active'):
                sub_type = "🔵 Mini" if sub['type'] == 'mini' else "🟣 Standard"
                tokens_left = sub['tokens_limit'] - sub['tokens_used']
                sub_info = f"{sub_type}\n💎 Токенов: {fmt(tokens_left)}/{fmt(sub['tokens_limit'])}"
            
            await msg.answer(
                f"👤 <b>Пользователь</b>\n\n"
                f"🆔 <code>{uid}</code>\n"
                f"👤 @{u['username'] or '—'}\n"
                f"📊 Запросов: {u['total_requests']}\n"
                f"🚫 Бан: {'Да' if u['is_blocked'] else 'Нет'}\n\n"
                f"💎 <b>Подписка:</b> {sub_info}",
                reply_markup=inline.user_manage_kb(uid, u['is_blocked']))
        await state.clear()
    except:
        await msg.answer("❌ Введите число")

@router.callback_query(F.data.startswith("block:"))
async def block_user(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    uid = int(cb.data.split(":")[1])
    await db.block_user(uid)
    await cb.answer("🚫 Заблокирован")
    await cb.message.edit_text("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=inline.admin_kb())

@router.callback_query(F.data.startswith("unblock:"))
async def unblock_user(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    uid = int(cb.data.split(":")[1])
    await db.unblock_user(uid)
    await cb.answer("✅ Разблокирован")
    await cb.message.edit_text("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=inline.admin_kb())

# === ПОДПИСКИ ===

@router.callback_query(F.data == "adm:sub")
async def sub_menu(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    mini = await db.count_subscribers_by_type('mini')
    standard = await db.count_subscribers_by_type('standard')
    await cb.message.edit_text(
        f"💎 <b>Подписки</b>\n\n"
        f"🔵 Mini (Sonnet): {mini}\n"
        f"🟣 Standard (Opus): {standard}",
        reply_markup=inline.sub_admin_kb())

@router.callback_query(F.data == "sub:give")
async def sub_give_start(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    await cb.message.edit_text("💎 <b>Выдать подписку</b>\n\nВведите ID пользователя:")
    await state.set_state(GiveSub.user_id)

@router.message(GiveSub.user_id)
async def sub_give_id(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    try:
        uid = int(msg.text)
        u = await db.get_user(uid)
        if not u:
            await msg.answer("❌ Не найден", reply_markup=inline.back_kb("adm:sub"))
            await state.clear()
            return
        await msg.answer(
            f"👤 <b>{uid}</b> (@{u['username'] or '—'})\n\nВыберите тариф и срок:",
            reply_markup=inline.sub_give_type_kb(uid))
        await state.clear()
    except:
        await msg.answer("❌ Введите число")

@router.callback_query(F.data.startswith("adm:givesub:"))
async def sub_give_from_user(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    uid = int(cb.data.split(":")[2])
    await cb.message.edit_text(
        f"💎 <b>Выдать подписку</b>\n\n👤 ID: {uid}\n\nВыберите тариф и срок:",
        reply_markup=inline.sub_give_type_kb(uid))

@router.callback_query(F.data.startswith("gsub:"))
async def give_sub_select(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    sub_type = parts[1]
    days = int(parts[2])
    uid = int(parts[3])
    
    await db.give_subscription(uid, days, sub_type)
    
    type_name = "🔵 Mini (Sonnet)" if sub_type == "mini" else "🟣 Standard (Opus)"
    await cb.answer(f"✅ Подписка выдана!")
    
    try:
        await bot.send_message(uid, 
            f"🎉 <b>Вам выдана подписка!</b>\n\n"
            f"💎 Тариф: {type_name}\n"
            f"📅 Срок: {days} дней")
    except:
        pass
    
    await cb.message.edit_text(
        f"✅ <b>Подписка выдана!</b>\n\n"
        f"👤 ID: <code>{uid}</code>\n"
        f"💎 Тариф: {type_name}\n"
        f"📅 Срок: {days} дней",
        reply_markup=inline.back_kb("adm:sub"))

@router.callback_query(F.data.startswith("sub:list:"))
async def sub_list(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    filter_type = cb.data.split(":")[2]
    
    if filter_type == "all":
        users = await db.get_all_subscribers()
        title = "Все подписчики"
    elif filter_type == "mini":
        users = await db.get_subscribers_by_type('mini')
        title = "🔵 Mini подписчики"
    else:
        users = await db.get_subscribers_by_type('standard')
        title = "🟣 Standard подписчики"
    
    if not users:
        await cb.answer("Нет подписчиков")
        return
    
    txt = f"💎 <b>{title}</b> ({len(users)})\n\n"
    for u in users[:20]:
        tokens_left = u['tokens_limit'] - u['tokens_used']
        txt += f"• {u['user_id']} — {fmt(tokens_left)} токенов\n"
    
    await cb.message.edit_text(txt, reply_markup=inline.back_kb("adm:sub"))

# === РАССЫЛКА С ФИЛЬТРАМИ ===

@router.callback_query(F.data == "adm:bc")
async def bc_menu(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    await cb.message.edit_text(
        "📢 <b>Рассылка</b>\n\nВыберите аудиторию:",
        reply_markup=inline.bc_filter_kb())

@router.callback_query(F.data.startswith("bc:filter:"))
async def bc_filter(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    filter_type = cb.data.split(":")[2]
    
    filters = {
        "all": "всем пользователям",
        "sub": "с подпиской",
        "nosub": "без подписки",
        "mini": "Mini подписчикам",
        "standard": "Standard подписчикам"
    }
    
    await state.update_data(bc_filter=filter_type)
    await cb.message.edit_text(
        f"📢 <b>Рассылка {filters[filter_type]}</b>\n\nВведите текст:")
    await state.set_state(Adm.bc_text)

@router.message(Adm.bc_text)
async def bc_preview(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    d = await state.get_data()
    filter_type = d.get('bc_filter', 'all')
    
    # Считаем получателей
    if filter_type == "all":
        count = await db.count_users()
    elif filter_type == "sub":
        count = await db.count_subscribers_by_type('mini') + await db.count_subscribers_by_type('standard')
    elif filter_type == "nosub":
        count = await db.count_users() - await db.count_subscribers_by_type('mini') - await db.count_subscribers_by_type('standard')
    elif filter_type == "mini":
        count = await db.count_subscribers_by_type('mini')
    else:
        count = await db.count_subscribers_by_type('standard')
    
    await state.update_data(bc_text=msg.text)
    await msg.answer(
        f"📢 <b>Превью рассылки</b>\n\n"
        f"👥 Получателей: ~{count}\n\n"
        f"{msg.text}",
        reply_markup=inline.confirm_bc_kb())

@router.callback_query(F.data == "bc:send")
async def bc_send(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    d = await state.get_data()
    filter_type = d.get('bc_filter', 'all')
    text = d.get('bc_text')
    
    # Получаем список
    if filter_type == "all":
        users = await db.get_all_users()
    elif filter_type == "sub":
        users = await db.get_all_subscribers()
    elif filter_type == "nosub":
        users = await db.get_users_without_subscription()
    elif filter_type == "mini":
        users = await db.get_subscribers_by_type('mini')
    else:
        users = await db.get_subscribers_by_type('standard')
    
    await cb.message.edit_text("📤 Отправка...")
    ok, err = 0, 0
    for u in users:
        uid = u['user_id'] if isinstance(u, dict) else u
        try:
            await bot.send_message(uid, text)
            ok += 1
        except:
            err += 1
    
    await cb.message.edit_text(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"📤 Отправлено: {ok}\n"
        f"❌ Ошибок: {err}",
        reply_markup=inline.back_kb("adm:back"))
    await state.clear()

# === ПАМЯТЬ ===

@router.callback_query(F.data == "adm:memory")
async def memory_menu(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    total = await db.count_users_with_memory()
    await cb.message.edit_text(
        f"🧠 <b>Память пользователей</b>\n\n"
        f"Всего пользователей с памятью: {total}",
        reply_markup=inline.memory_admin_kb())

@router.callback_query(F.data == "mem:search")
async def mem_search(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    await cb.message.edit_text("🔍 Введите ID пользователя:")
    await state.set_state(MemEdit.search)

@router.message(MemEdit.search)
async def mem_search_result(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    try:
        uid = int(msg.text)
        bots = await db.get_user_all_memory(uid)
        if not bots:
            await msg.answer("❌ У пользователя нет памяти", reply_markup=inline.back_kb("adm:memory"))
        else:
            u = await db.get_user(uid)
            name = f"@{u['username']}" if u and u.get('username') else str(uid)
            total_facts = sum(len(f) for f in bots.values())
            await msg.answer(
                f"👤 <b>{name}</b>\n"
                f"🆔 <code>{uid}</code>\n\n"
                f"📊 Всего фактов: {total_facts}",
                reply_markup=inline.memory_user_bots_kb(uid, bots))
        await state.clear()
    except:
        await msg.answer("❌ Введите число")

@router.callback_query(F.data.startswith("mem:list:"))
async def memory_list(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    page = int(cb.data.split(":")[2])
    per_page = 10
    
    total = await db.count_users_with_memory()
    total_pages = max(1, (total + per_page - 1) // per_page)
    users = await db.get_users_with_memory(per_page, page * per_page)
    
    if not users:
        await cb.answer("Нет пользователей с памятью")
        return
    
    await cb.message.edit_text(
        f"🧠 <b>Пользователи с памятью</b>\n\nСтраница {page+1}/{total_pages}",
        reply_markup=inline.memory_users_kb(users, page, total_pages))

@router.callback_query(F.data.startswith("mem:user:"))
async def memory_user(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    uid = int(cb.data.split(":")[2])
    u = await db.get_user(uid)
    bots = await db.get_user_all_memory(uid)
    
    if not bots:
        await cb.answer("У пользователя нет памяти")
        return
    
    name = f"@{u['username']}" if u and u.get('username') else str(uid)
    total_facts = sum(len(f) for f in bots.values())
    
    await cb.message.edit_text(
        f"👤 <b>{name}</b>\n"
        f"🆔 <code>{uid}</code>\n\n"
        f"📊 Всего фактов: {total_facts}",
        reply_markup=inline.memory_user_bots_kb(uid, bots))

@router.callback_query(F.data.startswith("mem:bot:"))
async def memory_bot(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    uid = int(parts[2])
    bot_name = parts[3]
    
    facts = await db.get_memory(uid, bot_name)
    bot_names = {'luca': '💭 Диалог', 'silas': '🛋️ Психолог', 'titus': '📓 Обучение'}
    
    await cb.message.edit_text(
        f"🧠 <b>{bot_names.get(bot_name, bot_name)}</b>\n"
        f"👤 ID: <code>{uid}</code>\n\n"
        f"📋 Фактов: {len(facts)}",
        reply_markup=inline.memory_facts_kb(uid, bot_name, facts))

@router.callback_query(F.data.startswith("mem:facts:"))
async def memory_facts_page(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    uid = int(parts[2])
    bot_name = parts[3]
    page = int(parts[4])
    
    facts = await db.get_memory(uid, bot_name)
    await cb.message.edit_reply_markup(
        reply_markup=inline.memory_facts_kb(uid, bot_name, facts, page))

@router.callback_query(F.data.startswith("mem:view:"))
async def memory_view_fact(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    uid = int(parts[2])
    bot_name = parts[3]
    idx = int(parts[4])
    
    facts = await db.get_memory(uid, bot_name)
    if idx < len(facts):
        await cb.message.edit_text(
            f"📝 <b>Факт #{idx+1}</b>\n\n{facts[idx]}",
            reply_markup=inline.memory_fact_view_kb(uid, bot_name, idx))

@router.callback_query(F.data.startswith("mem:del:"))
async def memory_delete_fact(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    uid = int(parts[2])
    bot_name = parts[3]
    idx = int(parts[4])
    
    await db.delete_memory_fact(uid, bot_name, idx)
    await cb.answer("🗑 Факт удалён")
    
    facts = await db.get_memory(uid, bot_name)
    bot_names = {'luca': '💭 Диалог', 'silas': '🛋️ Психолог', 'titus': '📓 Обучение'}
    await cb.message.edit_text(
        f"🧠 <b>{bot_names.get(bot_name, bot_name)}</b>\n"
        f"👤 ID: <code>{uid}</code>\n\n"
        f"📋 Фактов: {len(facts)}",
        reply_markup=inline.memory_facts_kb(uid, bot_name, facts))

@router.callback_query(F.data.startswith("mem:edit:"))
async def memory_edit_start(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    uid = int(parts[2])
    bot_name = parts[3]
    idx = int(parts[4])
    
    facts = await db.get_memory(uid, bot_name)
    await state.update_data(mem_uid=uid, mem_bot=bot_name, mem_idx=idx)
    await state.set_state(MemEdit.edit_fact)
    
    await cb.message.edit_text(
        f"✏️ <b>Редактирование факта</b>\n\n"
        f"Текущий текст:\n<code>{facts[idx]}</code>\n\n"
        f"Введите новый текст:")

@router.message(MemEdit.edit_fact)
async def memory_edit_save(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    d = await state.get_data()
    await db.update_memory_fact(d['mem_uid'], d['mem_bot'], d['mem_idx'], msg.text)
    await state.clear()
    await msg.answer("✅ Факт обновлён!", reply_markup=inline.back_kb(f"mem:bot:{d['mem_uid']}:{d['mem_bot']}"))

@router.callback_query(F.data.startswith("mem:add:"))
async def memory_add_start(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    uid = int(parts[2])
    bot_name = parts[3]
    
    await state.update_data(mem_uid=uid, mem_bot=bot_name)
    await state.set_state(MemEdit.add_fact)
    await cb.message.edit_text("➕ <b>Добавить факт</b>\n\nВведите текст:")

@router.message(MemEdit.add_fact)
async def memory_add_save(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    d = await state.get_data()
    facts = await db.get_memory(d['mem_uid'], d['mem_bot'])
    facts.append(msg.text)
    await db.save_memory(d['mem_uid'], d['mem_bot'], facts)
    await state.clear()
    await msg.answer("✅ Факт добавлен!", reply_markup=inline.back_kb(f"mem:bot:{d['mem_uid']}:{d['mem_bot']}"))

@router.callback_query(F.data.startswith("mem:clear:"))
async def memory_clear_bot(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    uid = int(parts[2])
    bot_name = parts[3]
    
    await db.clear_user_memory(uid, bot_name)
    await cb.answer("🗑 Память очищена")
    
    bots = await db.get_user_all_memory(uid)
    if bots:
        await cb.message.edit_text(f"👤 ID: <code>{uid}</code>", reply_markup=inline.memory_user_bots_kb(uid, bots))
    else:
        await cb.message.edit_text("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=inline.admin_kb())

@router.callback_query(F.data.startswith("mem:clearall:"))
async def memory_clear_all(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    uid = int(cb.data.split(":")[2])
    await db.clear_user_memory(uid)
    await cb.answer("🗑 Вся память очищена")
    await cb.message.edit_text("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=inline.admin_kb())

@router.callback_query(F.data == "mem:info")
async def memory_info(cb: CallbackQuery):
    await cb.answer("Используйте ◀️ ▶️ для навигации")

# === ПРОМПТЫ ===

@router.callback_query(F.data == "adm:prompts")
async def prompts_menu(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    await cb.message.edit_text(
        "📝 <b>Промпты ботов</b>\n\n"
        "Выберите бота для просмотра/редактирования промпта:",
        reply_markup=inline.prompts_kb())

@router.callback_query(F.data.startswith("prompt:"))
async def prompt_view(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    
    parts = cb.data.split(":")
    action = parts[1]
    
    if action in ['luca', 'silas', 'titus']:
        # Показать промпт
        bot_name = action
        try:
            if bot_name == 'luca':
                from prompts.luca_prompt import SYSTEM_PROMPT
            elif bot_name == 'silas':
                from prompts.silas_prompt import SYSTEM_PROMPT
            else:
                from prompts.titus_prompt import SYSTEM_PROMPT
            
            prompt_preview = SYSTEM_PROMPT[:500] + "..." if len(SYSTEM_PROMPT) > 500 else SYSTEM_PROMPT
            
            bot_names = {'luca': '💭 Luca (Диалог)', 'silas': '🛋️ Silas (Психолог)', 'titus': '📓 Titus (Обучение)'}
            await cb.message.edit_text(
                f"📝 <b>{bot_names[bot_name]}</b>\n\n"
                f"<code>{prompt_preview}</code>\n\n"
                f"📊 Длина: {len(SYSTEM_PROMPT)} символов",
                reply_markup=inline.prompt_edit_kb(bot_name))
        except Exception as e:
            await cb.message.edit_text(f"❌ Ошибка: {e}", reply_markup=inline.back_kb("adm:prompts"))
    
    elif action == "edit":
        bot_name = parts[2]
        await state.update_data(prompt_bot=bot_name)
        await cb.message.edit_text(
            f"✏️ <b>Редактирование промпта</b>\n\n"
            f"Отправьте новый текст промпта.\n"
            f"⚠️ Это перезапишет файл!")
        await state.set_state(Adm.prompt_edit)
    
    elif action == "reset":
        await cb.answer("⚠️ Функция сброса недоступна")

@router.message(Adm.prompt_edit)
async def prompt_save(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    d = await state.get_data()
    bot_name = d.get('prompt_bot')
    
    try:
        file_path = f"/root/ai-bot/prompts/{bot_name}_prompt.py"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f'SYSTEM_PROMPT = """{msg.text}"""\n')
        
        await msg.answer(
            f"✅ Промпт {bot_name} обновлён!\n\n"
            f"⚠️ Перезапустите бота для применения.",
            reply_markup=inline.back_kb("adm:prompts"))
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}", reply_markup=inline.back_kb("adm:prompts"))
    
    await state.clear()

# === МОНИТОРИНГ ===

@router.callback_query(F.data == "adm:monitor")
async def monitor(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    
    # Статистика по моделям
    sonnet_usage = await db.get_tokens_by_model('mini')
    opus_usage = await db.get_tokens_by_model('standard')
    
    await cb.message.edit_text(
        f"📊 <b>Мониторинг моделей</b>\n\n"
        f"🔵 <b>Sonnet (Mini)</b>\n"
        f"└ Токенов использовано: {fmt(sonnet_usage)}\n\n"
        f"🟣 <b>Opus (Standard)</b>\n"
        f"└ Токенов использовано: {fmt(opus_usage)}\n\n"
        f"📈 Всего: {fmt(sonnet_usage + opus_usage)}",
        reply_markup=inline.monitor_kb())

# === МОЯ ПОДПИСКА (АДМИН) ===

@router.callback_query(F.data == "adm:mysub")
async def admin_mysub(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    
    sub = await db.get_subscription(cb.from_user.id)
    current = sub['type'] if sub and sub.get('is_active') else None
    
    await cb.message.edit_text(
        f"👑 <b>Моя подписка (админ)</b>\n\n"
        f"Текущий тариф: {current or 'нет'}\n\n"
        f"Выберите модель для использования:",
        reply_markup=inline.admin_mysub_kb(current))

@router.callback_query(F.data.startswith("adm:setmysub:"))
async def admin_set_mysub(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    
    sub_type = cb.data.split(":")[2]
    await db.give_subscription(cb.from_user.id, 36500, sub_type)  # 100 лет
    
    type_name = "🔵 Sonnet (Mini)" if sub_type == "mini" else "🟣 Opus (Standard)"
    await cb.answer(f"✅ Переключено на {type_name}")
    await admin_mysub(cb)

# === GIT ===

@router.callback_query(F.data == "adm:git")
async def git_menu(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    await cb.message.edit_text(
        "💾 <b>Git</b>\n\nВыберите действие:",
        reply_markup=inline.git_kb())

@router.callback_query(F.data == "git:status")
async def git_status(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    try:
        result = subprocess.run(['git', 'status', '--short'], cwd="/root/ai-bot", capture_output=True, text=True)
        status = result.stdout or "Нет изменений"
        
        branch = subprocess.run(['git', 'branch', '--show-current'], cwd="/root/ai-bot", capture_output=True, text=True)
        
        await cb.message.edit_text(
            f"📋 <b>Git статус</b>\n\n"
            f"🌿 Ветка: {branch.stdout.strip()}\n\n"
            f"<code>{status[:1000]}</code>",
            reply_markup=inline.back_kb("adm:git"))
    except Exception as e:
        await cb.message.edit_text(f"❌ Ошибка: {e}", reply_markup=inline.back_kb("adm:git"))

@router.callback_query(F.data == "git:push")
async def git_push_start(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    await cb.message.edit_text("💾 <b>Git Push</b>\n\nВведите комментарий к коммиту:")
    await state.set_state(Adm.git_msg)

@router.message(Adm.git_msg)
async def git_push_confirm(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    await state.update_data(git_msg=msg.text)
    await msg.answer(
        f"💾 <b>Подтверждение</b>\n\nКомментарий: {msg.text}\n\nСохранить?",
        reply_markup=inline.confirm_git_kb())

@router.callback_query(F.data == "git:confirm")
async def git_push_do(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    d = await state.get_data()
    msg_text = d.get('git_msg', 'Auto backup')
    
    await cb.message.edit_text("⏳ Сохранение...")
    try:
        subprocess.run(["git", "add", "."], cwd="/root/ai-bot", check=True)
        subprocess.run(["git", "commit", "-m", msg_text], cwd="/root/ai-bot", check=True)
        result = subprocess.run(["git", "push"], cwd="/root/ai-bot", capture_output=True, text=True)
        
        await cb.message.edit_text(
            f"✅ <b>Проект сохранён!</b>\n\n💬 {msg_text}",
            reply_markup=inline.back_kb("adm:git"))
    except Exception as e:
        await cb.message.edit_text(
            f"❌ <b>Ошибка</b>\n\n{str(e)[:200]}",
            reply_markup=inline.back_kb("adm:git"))
    await state.clear()

@router.callback_query(F.data == "git:pull")
async def git_pull(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    try:
        result = subprocess.run(['git', 'pull'], cwd="/root/ai-bot", capture_output=True, text=True)
        output = result.stdout + result.stderr
        await cb.message.edit_text(
            f"📥 <b>Git Pull</b>\n\n<code>{output[:1000]}</code>",
            reply_markup=inline.back_kb("adm:git"))
    except Exception as e:
        await cb.message.edit_text(f"❌ Ошибка: {e}", reply_markup=inline.back_kb("adm:git"))
