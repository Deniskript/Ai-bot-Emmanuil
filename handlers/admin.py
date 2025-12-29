from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loader import bot
from database import db
from keyboards import inline
from config import ADMIN_IDS

router = Router()

class St(StatesGroup):
    user_id = State()
    tokens = State()
    broadcast = State()
    find = State()

def adm(uid): return uid in ADMIN_IDS
def fmt(n): return f"{n:,}".replace(",", " ")

async def get_spam_settings():
    enabled = await db.get_setting('spam_enabled')
    interval = await db.get_setting('spam_interval')
    max_req = await db.get_setting('spam_max_requests')
    return {
        'enabled': enabled != '0',
        'interval': int(interval) if interval else 2,
        'max_requests': int(max_req) if max_req else 1
    }

@router.message(Command("admin"))
async def panel(msg: Message, state: FSMContext):
    if not adm(msg.from_user.id): return
    await state.clear()
    await msg.answer("👑 <b>АДМИН</b>", reply_markup=inline.admin_keyboard())

@router.callback_query(F.data == "admin_close")
async def close(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    await state.clear()
    await cb.message.delete()

@router.callback_query(F.data == "admin_back")
async def back(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    await state.clear()
    await cb.message.edit_text("👑 <b>АДМИН</b>", reply_markup=inline.admin_keyboard())

@router.callback_query(F.data == "admin_give")
async def give_start(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    await cb.message.edit_text("💎 Введите ID:", reply_markup=inline.admin_cancel())
    await state.set_state(St.user_id)

@router.message(St.user_id)
async def got_id(msg: Message, state: FSMContext):
    if not adm(msg.from_user.id): return
    try: uid = int(msg.text)
    except: await msg.answer("❌ Число!"); return
    u = await db.get_user(uid)
    if not u: await msg.answer("❌ Не найден", reply_markup=inline.admin_cancel()); return
    await state.update_data(target=uid)
    await msg.answer(f"👤 {uid}\n💎 {fmt(u['tokens'])}", reply_markup=inline.give_keyboard())

@router.callback_query(F.data.startswith("give:"))
async def give(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    amt = int(cb.data.split(":")[1])
    d = await state.get_data()
    t = d.get('target')
    if not t: await cb.answer("Err"); return
    await db.add_tokens(t, amt)
    try: await bot.send_message(t, f"🎉 +{fmt(amt)} токенов!")
    except: pass
    await cb.message.edit_text(f"✅ +{fmt(amt)} для {t}", reply_markup=inline.admin_back())
    await state.clear()

@router.callback_query(F.data == "give_custom")
async def give_cust(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    await cb.message.edit_text("✏️ Сколько токенов?", reply_markup=inline.admin_cancel())
    await state.set_state(St.tokens)

@router.message(St.tokens)
async def got_tokens(msg: Message, state: FSMContext):
    if not adm(msg.from_user.id): return
    try: amt = int(msg.text)
    except: await msg.answer("❌ Число!"); return
    d = await state.get_data()
    t = d.get('target')
    if not t: await msg.answer("Err /admin"); await state.clear(); return
    await db.add_tokens(t, amt)
    try: await bot.send_message(t, f"🎉 +{fmt(amt)} токенов!")
    except: pass
    await msg.answer(f"✅ +{fmt(amt)}", reply_markup=inline.admin_back())
    await state.clear()

@router.callback_query(F.data == "admin_find")
async def find_start(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    await cb.message.edit_text("👤 ID:", reply_markup=inline.admin_cancel())
    await state.set_state(St.find)

@router.message(St.find)
async def found(msg: Message, state: FSMContext):
    if not adm(msg.from_user.id): return
    try: uid = int(msg.text)
    except: await msg.answer("❌"); return
    u = await db.get_user(uid)
    if not u: await msg.answer("❌", reply_markup=inline.admin_back()); await state.clear(); return
    m = await db.get_user_memory(uid)
    await msg.answer(f"👤 {uid}\n@{u['username'] or '-'}\n💎 {fmt(u['tokens'])}\n🧠 {'ВКЛ' if m['memory_enabled'] else 'ВЫКЛ'}", reply_markup=inline.user_keyboard(uid))
    await state.clear()

@router.callback_query(F.data.startswith("adm_give:"))
async def adm_give(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    uid = int(cb.data.split(":")[1])
    await state.update_data(target=uid)
    await cb.message.edit_text("Токены:", reply_markup=inline.give_keyboard())

@router.callback_query(F.data.startswith("adm_block:"))
async def block(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    uid = int(cb.data.split(":")[1])
    await db.block_user(uid)
    await cb.message.edit_text(f"🚫 {uid} заблокирован", reply_markup=inline.admin_back())

@router.callback_query(F.data.startswith("adm_mem:"))
async def mem(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    uid = int(cb.data.split(":")[1])
    m = await db.get_user_memory(uid)
    await cb.message.edit_text(f"🧠 {uid}\n\n{m['personal_prompt'] or 'Пусто'}", reply_markup=inline.admin_back())

@router.callback_query(F.data == "admin_broadcast")
async def bc_start(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    await cb.message.edit_text("📢 Текст:", reply_markup=inline.admin_cancel())
    await state.set_state(St.broadcast)

@router.message(St.broadcast)
async def bc_text(msg: Message, state: FSMContext):
    if not adm(msg.from_user.id): return
    await state.update_data(bc=msg.text)
    await msg.answer(f"📢 Превью:\n\n{msg.text}", reply_markup=inline.bc_keyboard())

@router.callback_query(F.data == "bc_confirm")
async def bc_send(cb: CallbackQuery, state: FSMContext):
    if not adm(cb.from_user.id): return
    d = await state.get_data()
    txt = d.get('bc')
    if not txt: await cb.answer("Err"); return
    await cb.message.edit_text("📤...")
    users = await db.get_all_users()
    ok, err = 0, 0
    for u in users:
        try: await bot.send_message(u['user_id'], txt); ok += 1
        except: err += 1
    await cb.message.edit_text(f"✅ {ok} / ❌ {err}", reply_markup=inline.admin_back())
    await state.clear()

@router.callback_query(F.data == "admin_maint")
async def maint(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    st = await db.get_setting('maintenance_mode')
    on = st == '1'
    await cb.message.edit_text(f"🔧 {'🔴 ВКЛ' if on else '🟢 ВЫКЛ'}", reply_markup=inline.maint_keyboard(on))

@router.callback_query(F.data == "toggle_maint")
async def tog_maint(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    st = await db.get_setting('maintenance_mode')
    new = '0' if st == '1' else '1'
    await db.set_setting('maintenance_mode', new)
    on = new == '1'
    await cb.message.edit_text(f"🔧 {'🔴 ВКЛ' if on else '🟢 ВЫКЛ'}", reply_markup=inline.maint_keyboard(on))

@router.callback_query(F.data == "admin_stats")
async def stats(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    s = await db.get_statistics()
    await cb.message.edit_text(f"📊 Юзеров: {s['total_users']}\nАктивных: {s['active_today']}\nНовых/нед: {s['new_this_week']}\n\n💬 Сегодня: {s['requests_today']}\nМесяц: {s['requests_month']}\nВсего: {s['total_requests']}\n\n💎 Токенов: {fmt(s['total_tokens_used'])}", reply_markup=inline.admin_back())

# ==================== АНТИСПАМ ====================

@router.callback_query(F.data == "admin_spam")
async def spam_menu(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    settings = await get_spam_settings()
    status = "🟢 Включён" if settings['enabled'] else "🔴 Выключен"
    text = f"""🗿 <b>Антиспам</b>

📊 <b>Статус:</b> {status}
⏱ <b>Интервал:</b> {settings['interval']} сек
🔄 <b>Макс. одновременно:</b> {settings['max_requests']}

<i>💡 Интервал — минимальное время между запросами
🔄 Макс. запросов — сколько запросов может обрабатываться одновременно</i>"""
    await cb.message.edit_text(text, reply_markup=inline.spam_keyboard(settings))

@router.callback_query(F.data == "spam_toggle")
async def spam_toggle(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    current = await db.get_setting('spam_enabled')
    new = '0' if current != '0' else '1'
    await db.set_setting('spam_enabled', new)
    await cb.answer(f"✅ Антиспам {'включён' if new == '1' else 'выключен'}")
    settings = await get_spam_settings()
    status = "🟢 Включён" if settings['enabled'] else "🔴 Выключен"
    text = f"""🗿 <b>Антиспам</b>

📊 <b>Статус:</b> {status}
⏱ <b>Интервал:</b> {settings['interval']} сек
🔄 <b>Макс. одновременно:</b> {settings['max_requests']}

<i>💡 Интервал — минимальное время между запросами
🔄 Макс. запросов — сколько запросов может обрабатываться одновременно</i>"""
    await cb.message.edit_text(text, reply_markup=inline.spam_keyboard(settings))

@router.callback_query(F.data == "spam_interval")
async def spam_interval(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    await cb.message.edit_text("⏱ <b>Выберите интервал между запросами:</b>\n\n<i>Чем больше интервал — тем меньше нагрузка на бота</i>", reply_markup=inline.spam_interval_keyboard())

@router.callback_query(F.data.startswith("set_interval:"))
async def set_interval(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    val = cb.data.split(":")[1]
    await db.set_setting('spam_interval', val)
    await cb.answer(f"✅ Интервал: {val} сек")
    settings = await get_spam_settings()
    status = "🟢 Включён" if settings['enabled'] else "🔴 Выключен"
    text = f"""🗿 <b>Антиспам</b>

📊 <b>Статус:</b> {status}
⏱ <b>Интервал:</b> {settings['interval']} сек
🔄 <b>Макс. одновременно:</b> {settings['max_requests']}

<i>💡 Интервал — минимальное время между запросами
🔄 Макс. запросов — сколько запросов может обрабатываться одновременно</i>"""
    await cb.message.edit_text(text, reply_markup=inline.spam_keyboard(settings))

@router.callback_query(F.data == "spam_max")
async def spam_max(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    await cb.message.edit_text("🔄 <b>Макс. одновременных запросов:</b>\n\n<i>Сколько запросов может обрабатываться одновременно от одного пользователя</i>", reply_markup=inline.spam_max_keyboard())

@router.callback_query(F.data.startswith("set_max:"))
async def set_max(cb: CallbackQuery):
    if not adm(cb.from_user.id): return
    val = cb.data.split(":")[1]
    await db.set_setting('spam_max_requests', val)
    await cb.answer(f"✅ Макс. запросов: {val}")
    settings = await get_spam_settings()
    status = "🟢 Включён" if settings['enabled'] else "🔴 Выключен"
    text = f"""🗿 <b>Антиспам</b>

📊 <b>Статус:</b> {status}
⏱ <b>Интервал:</b> {settings['interval']} сек
🔄 <b>Макс. одновременно:</b> {settings['max_requests']}

<i>💡 Интервал — минимальное время между запросами
🔄 Макс. запросов — сколько запросов может обрабатываться одновременно</i>"""
    await cb.message.edit_text(text, reply_markup=inline.spam_keyboard(settings))
