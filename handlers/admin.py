from aiogram import Router, F
import psutil
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
    give_id = State()
    give_amt = State()
    bc = State()
    model = State()
    version = State()

def is_adm(uid): return uid in ADMIN_IDS
def fmt(n): return f"{n:,}".replace(",", " ")

class Adm(StatesGroup):
    find = State()
    give_id = State()
    give_amt = State()
    bc = State()
    model = State()
    version = State()

def is_adm(uid): return uid in ADMIN_IDS
def fmt(n): return f"{n:,}".replace(",", " ")

@router.message(Command("admin"))
async def admin(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id): return
    await state.clear()
    await msg.answer("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=inline.admin_kb())

@router.callback_query(F.data == "adm:close")
async def close(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    await state.clear()
    await cb.message.delete()

@router.callback_query(F.data == "adm:back")
async def back(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    await state.clear()
    await cb.message.edit_text("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=inline.admin_kb())

@router.callback_query(F.data == "adm:stats")
async def stats(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    s = await db.get_stats()
    blocked = await db.get_blocked_count()
    await cb.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: {fmt(s['users'])}\n"
        f"🚫 Заблокировано: {blocked}\n"
        f"💬 Запросов: {fmt(s['reqs'])}\n"
        f"💎 Токенов: {fmt(s['tokens'])}",
        reply_markup=inline.back_kb("adm:back"))

@router.callback_query(F.data == "adm:load")
async def load(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    s = await db.get_stats()
    if cpu < 50: status = "🟢 Нормальная"
    elif cpu < 80: status = "🟡 Средняя"
    else: status = "🔴 Высокая"
    await cb.message.edit_text(
        f"📈 <b>Нагрузка</b>\n\n💻 CPU: {cpu}%\n🧠 RAM: {mem.percent}%\n"
        f"👥 Юзеров: {fmt(s['users'])}\n💬 Запросов: {fmt(s['reqs'])}\n\nСтатус: {status}",
        reply_markup=inline.back_kb("adm:back"))

@router.callback_query(F.data == "adm:bots")
async def bots(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    l = await db.get_bot_cfg('luca')
    s = await db.get_bot_cfg('silas')
    t = await db.get_bot_cfg('titus')
    e = lambda x: "🟢" if x else "🔴"
    await cb.message.edit_text(
        f"🤖 <b>Боты</b>\n\n{e(l['enabled'])} Luca — {l['model']}\n"
        f"{e(s['enabled'])} Silas — {s['model']}\n{e(t['enabled'])} Titus — {t['model']}",
        reply_markup=inline.admin_bots_kb(l['enabled'], s['enabled'], t['enabled']))

@router.callback_query(F.data.startswith("botcfg:"))
async def bot_cfg(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    b = cb.data.split(":")[1]
    cfg = await db.get_bot_cfg(b)
    names = {'luca': '🧑 Luca', 'silas': '🧠 Silas', 'titus': '📚 Titus'}
    await cb.message.edit_text(
        f"⚙️ <b>{names[b]}</b>\n\nСтатус: {'🟢' if cfg['enabled'] else '🔴'}\n"
        f"Модель: {cfg['model']}\nВерсия: {cfg['version']}",
        reply_markup=inline.bot_cfg_kb(b, cfg['enabled']))

@router.callback_query(F.data.startswith("tog:"))
async def toggle(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    b = cb.data.split(":")[1]
    cfg = await db.get_bot_cfg(b)
    await db.set_bot_enabled(b, not cfg['enabled'])
    await cb.answer(f"{'🟢 Вкл' if not cfg['enabled'] else '🔴 Выкл'}")
    cb.data = f"botcfg:{b}"
    await bot_cfg(cb)

@router.callback_query(F.data.startswith("model:"))
async def change_model(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    b = cb.data.split(":")[1]
    await state.update_data(bot=b)
    await state.set_state(Adm.model)
    await cb.message.edit_text(
        "🔄 <b>Выберите модель:</b>\n\n"
        "OpenAI: gpt-4o, gpt-4o-mini, gpt-4-turbo\n"
        "Claude: claude-3-opus, claude-3-sonnet\n\nВведите название:")

@router.message(Adm.model)
async def set_model(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id): return
    d = await state.get_data()
    await db.set_bot_model(d['bot'], msg.text)
    await state.clear()
    await msg.answer(f"✅ Модель: {msg.text}", reply_markup=inline.back_kb("adm:bots"))

@router.callback_query(F.data.startswith("ver:"))
async def change_ver(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    b = cb.data.split(":")[1]
    await state.update_data(bot=b)
    await state.set_state(Adm.version)
    await cb.message.edit_text("📝 Введите версию (например 1.0.1):")

@router.message(Adm.version)
async def set_ver(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id): return
    d = await state.get_data()
    await db.set_bot_version(d['bot'], msg.text)
    await state.clear()
    await msg.answer(f"✅ Версия: {msg.text}", reply_markup=inline.back_kb("adm:bots"))

@router.callback_query(F.data == "adm:spam")
async def spam_settings(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    interval = int(await db.get_setting('spam_interval') or '2')
    max_rpm = int(await db.get_setting('spam_max_rpm') or '8')
    blocked = await db.get_blocked_count()
    await cb.message.edit_text(
        f"🛡 <b>Антифлуд</b>\n\n⏱ Интервал: {interval} сек\n"
        f"📨 Макс/мин: {max_rpm}\n🚫 Заблокировано: {blocked}",
        reply_markup=inline.spam_kb(interval, max_rpm, blocked))

@router.callback_query(F.data == "sp:info")
async def sp_info(cb: CallbackQuery):
    await cb.answer("Используйте + и - для изменения")

@router.callback_query(F.data.startswith("sp:int:"))
async def sp_interval(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    act = cb.data.split(":")[2]
    cur = int(await db.get_setting('spam_interval') or '2')
    new = max(1, cur + (1 if act == "+1" else -1))
    await db.set_setting('spam_interval', str(new))
    await cb.answer(f"Интервал: {new} сек")
    await spam_settings(cb)

@router.callback_query(F.data.startswith("sp:rpm:"))
async def sp_rpm(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    act = cb.data.split(":")[2]
    cur = int(await db.get_setting('spam_max_rpm') or '8')
    new = max(1, cur + (1 if act == "+1" else -1))
    await db.set_setting('spam_max_rpm', str(new))
    await cb.answer(f"Макс/мин: {new}")
    await spam_settings(cb)

@router.callback_query(F.data == "spam:list")
async def spam_list(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
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
    if not is_adm(cb.from_user.id): return
    users = await db.get_blocked_users()
    if not users:
        await cb.answer("Нет заблокированных")
        return
    await cb.message.edit_text(
        "🔓 Введите ID для разблокировки:\n\n" +
        "\n".join([f"• {u['user_id']}" for u in users[:10]]),
        reply_markup=inline.back_kb("adm:spam"))

@router.callback_query(F.data == "adm:users")
async def users_list(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    users = await db.get_all_users()
    total = len(users)
    txt = f"👥 <b>Пользователи ({total})</b>\n\n"
    for u in users[:15]:
        status = "🚫" if u.get('is_blocked') else "✅"
        txt += f"{status} <code>{u['user_id']}</code> — {fmt(u['tokens'])} 💎\n"
    if total > 15:
        txt += f"\n... и ещё {total - 15}"
    await cb.message.edit_text(txt, reply_markup=inline.back_kb("adm:back"))

@router.callback_query(F.data == "adm:find")
async def find_start(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    await cb.message.edit_text("🔍 <b>Поиск</b>\n\nВведите ID пользователя:")
    await state.set_state(Adm.find)

@router.message(Adm.find)
async def find_user(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id): return
    try:
        uid = int(msg.text)
        u = await db.get_user(uid)
        if not u:
            await msg.answer("❌ Не найден", reply_markup=inline.back_kb("adm:back"))
        else:
            await msg.answer(
                f"👤 <b>Пользователь</b>\n\n🆔 <code>{uid}</code>\n"
                f"👤 @{u['username'] or '—'}\n💎 {fmt(u['tokens'])}\n"
                f"📊 Запросов: {u['total_requests']}\n🚫 Бан: {'Да' if u['is_blocked'] else 'Нет'}",
                reply_markup=inline.user_manage_kb(uid))
        await state.clear()
    except:
        await msg.answer("❌ Введите число")

@router.callback_query(F.data.startswith("block:"))
async def block_user(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    uid = int(cb.data.split(":")[1])
    await db.block_user(uid)
    await cb.answer("🚫 Заблокирован")
    await cb.message.edit_text("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=inline.admin_kb())

@router.callback_query(F.data == "adm:give")
async def give_start(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    await cb.message.edit_text("💎 <b>Выдать токены</b>\n\nВведите ID:")
    await state.set_state(Adm.give_id)

@router.message(Adm.give_id)
async def give_id(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id): return
    try:
        uid = int(msg.text)
        u = await db.get_user(uid)
        if not u:
            await msg.answer("❌ Не найден", reply_markup=inline.back_kb("adm:back"))
            await state.clear()
            return
        await state.update_data(target=uid)
        await msg.answer(f"👤 {uid}\n💎 {fmt(u['tokens'])}\n\nСколько выдать?", reply_markup=inline.give_kb())
    except:
        await msg.answer("❌ Введите число")

@router.callback_query(F.data.startswith("gadd:"))
async def give_quick(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    amt = cb.data.split(":")[1]
    if amt == "custom":
        await cb.message.edit_text("✏️ Введите количество:")
        await state.set_state(Adm.give_amt)
        return
    d = await state.get_data()
    await db.add_tokens(d['target'], int(amt))
    try: await bot.send_message(d['target'], f"🎉 Вам начислено <b>{fmt(int(amt))}</b> токенов!")
    except: pass
    await cb.message.edit_text(f"✅ Выдано {fmt(int(amt))}", reply_markup=inline.back_kb("adm:back"))
    await state.clear()

@router.message(Adm.give_amt)
async def give_custom(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id): return
    try:
        amt = int(msg.text)
        d = await state.get_data()
        await db.add_tokens(d['target'], amt)
        try: await bot.send_message(d['target'], f"🎉 Вам начислено <b>{fmt(amt)}</b> токенов!")
        except: pass
        await msg.answer(f"✅ Выдано {fmt(amt)}", reply_markup=inline.back_kb("adm:back"))
        await state.clear()
    except:
        await msg.answer("❌ Введите число")

@router.callback_query(F.data == "adm:bc")
async def bc_start(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    await cb.message.edit_text("📢 <b>Рассылка</b>\n\nВведите текст:")
    await state.set_state(Adm.bc)

@router.message(Adm.bc)
async def bc_preview(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id): return
    await state.update_data(bc_text=msg.text)
    await msg.answer(f"📢 <b>Превью:</b>\n\n{msg.text}", reply_markup=inline.confirm_bc_kb())

@router.callback_query(F.data == "bc:send")
async def bc_send(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    d = await state.get_data()
    users = await db.get_all_users()
    ok, err = 0, 0
    await cb.message.edit_text("📤 Отправка...")
    for u in users:
        try:
            await bot.send_message(u['user_id'], d['bc_text'])
            ok += 1
        except: err += 1
    await cb.message.edit_text(f"✅ Отправлено: {ok}\n❌ Ошибок: {err}", reply_markup=inline.back_kb("adm:back"))
    await state.clear()

@router.callback_query(F.data == "adm:maint")
async def maint(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    c = await db.get_setting('maintenance')
    n = '0' if c == '1' else '1'
    await db.set_setting('maintenance', n)
    await cb.answer(f"🔧 Тех.работы: {'ВКЛ' if n == '1' else 'ВЫКЛ'}")
    await cb.message.edit_text("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=inline.admin_kb())

@router.callback_query(F.data.startswith("setm:"))
async def set_model_btn(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    parts = cb.data.split(":")
    b, model = parts[1], parts[2]
    await db.set_bot_model(b, model)
    await cb.answer(f"✅ {model}")
    cb.data = f"botcfg:{b}"
    await bot_cfg(cb)
