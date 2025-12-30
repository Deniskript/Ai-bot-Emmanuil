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
    await cb.message.edit_text(
        f"📈 <b>Статистика</b>\n\n"
        f"👥 Пользователей: {s['users']}\n"
        f"💬 Запросов: {fmt(s['reqs'])}\n"
        f"💎 Токенов потрачено: {fmt(s['tokens'])}",
        reply_markup=inline.back_kb("adm:back")
    )

@router.callback_query(F.data == "adm:bots")
async def bots(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    l = await db.get_bot_cfg('luca')
    s = await db.get_bot_cfg('silas')
    t = await db.get_bot_cfg('titus')
    e = lambda x: "🟢 Работает" if x else "🔴 Выключен"
    await cb.message.edit_text(
        f"🤖 <b>Состояние ботов</b>\n\n"
        f"🧑 <b>Luca</b> ({l['model']})\n   {e(l['enabled'])} | Версия: {l['version']}\n\n"
        f"🧠 <b>Silas</b> ({s['model']})\n   {e(s['enabled'])} | Версия: {s['version']}\n\n"
        f"📚 <b>Titus</b> ({t['model']})\n   {e(t['enabled'])} | Версия: {t['version']}",
        reply_markup=inline.admin_bots_kb(l['enabled'], s['enabled'], t['enabled'])
    )

@router.callback_query(F.data.startswith("botcfg:"))
async def bot_cfg(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    b = cb.data.split(":")[1]
    cfg = await db.get_bot_cfg(b)
    names = {'luca': '🧑 Luca', 'silas': '🧠 Silas', 'titus': '📚 Titus'}
    await cb.message.edit_text(
        f"⚙️ <b>Настройки {names[b]}</b>\n\n"
        f"Статус: {'🟢 Работает' if cfg['enabled'] else '🔴 Выключен'}\n"
        f"AI модель: {cfg['model']}\n"
        f"Версия: {cfg['version']}",
        reply_markup=inline.bot_cfg_kb(b, cfg['enabled'])
    )

@router.callback_query(F.data.startswith("tog:"))
async def toggle(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    b = cb.data.split(":")[1]
    cfg = await db.get_bot_cfg(b)
    await db.set_bot_enabled(b, not cfg['enabled'])
    await cb.answer(f"{'🟢 Включен' if not cfg['enabled'] else '🔴 Выключен'}")
    await bot_cfg(cb)

@router.callback_query(F.data.startswith("model:"))
async def change_model(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    b = cb.data.split(":")[1]
    await state.update_data(bot=b)
    await state.set_state(Adm.model)
    await cb.message.edit_text(
        f"🔄 <b>Смена модели</b>\n\n"
        f"Введите название модели:\n"
        f"• gpt-4o-mini\n• gpt-4o\n• gpt-4-turbo"
    )

@router.message(Adm.model)
async def set_model(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id): return
    d = await state.get_data()
    await db.set_bot_model(d['bot'], msg.text)
    await state.clear()
    await msg.answer(f"✅ Модель изменена на: {msg.text}", reply_markup=inline.back_kb("adm:bots"))

@router.callback_query(F.data.startswith("ver:"))
async def change_ver(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    b = cb.data.split(":")[1]
    await state.update_data(bot=b)
    await state.set_state(Adm.version)
    await cb.message.edit_text("📝 <b>Версия</b>\n\nВведите новую версию (например: 1.0.1):")

@router.message(Adm.version)
async def set_ver(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id): return
    d = await state.get_data()
    await db.set_bot_version(d['bot'], msg.text)
    await state.clear()
    await msg.answer(f"✅ Версия: {msg.text}", reply_markup=inline.back_kb("adm:bots"))

@router.callback_query(F.data == "adm:load")
async def load(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    m = await db.get_metrics()
    warn = await db.get_setting('warn_threshold') or '70'
    crit = await db.get_setting('crit_threshold') or '90'
    if m:
        status = "🟢 Нормальная" if m['load_pct'] < int(warn) else "⚠️ Высокая" if m['load_pct'] < int(crit) else "🔴 Критическая"
        txt = (
            f"📊 <b>Нагрузка сервера</b>\n\n"
            f"⚡️ Текущая нагрузка: {m['load_pct']}%\n"
            f"👥 Активных: {m['active_users']}\n"
            f"📨 Запросов/мин: {m['rpm']}\n"
            f"⏱ Среднее время: {m['avg_time']:.1f} сек\n\n"
            f"Статус: {status}\n\n"
            f"Пороги: ⚠️{warn}% | 🔴{crit}%"
        )
    else:
        txt = "📊 <b>Нагрузка</b>\n\nДанных пока нет"
    await cb.message.edit_text(txt, reply_markup=inline.back_kb("adm:back"))

@router.callback_query(F.data == "adm:maint")
async def maint(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    c = await db.get_setting('maintenance')
    n = '0' if c == '1' else '1'
    await db.set_setting('maintenance', n)
    await cb.answer(f"🔧 Тех.работы: {'ВКЛ' if n == '1' else 'ВЫКЛ'}")
    await cb.message.edit_text("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=inline.admin_kb())

@router.callback_query(F.data == "adm:spam")
async def spam_settings(cb: CallbackQuery):
    if not is_adm(cb.from_user.id): return
    await cb.message.edit_text(
        "🗿 <b>Антиспам</b>\n\n"
        "Настройки антиспама в config.py:\n"
        "• SPAM_INTERVAL = 2 сек\n"
        "• SPAM_MAX_REQUESTS = 1",
        reply_markup=inline.back_kb("adm:back")
    )

@router.callback_query(F.data == "adm:find")
async def find_start(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    await cb.message.edit_text("👤 <b>Поиск</b>\n\nВведите ID пользователя:")
    await state.set_state(Adm.find)

@router.message(Adm.find)
async def find_user(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id): return
    try:
        uid = int(msg.text)
        u = await db.get_user(uid)
        if not u:
            await msg.answer("❌ Пользователь не найден", reply_markup=inline.back_kb("adm:back"))
        else:
            await msg.answer(
                f"👤 <b>Пользователь</b>\n\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"👤 @{u['username'] or '—'}\n"
                f"💎 Баланс: {fmt(u['tokens'])}\n"
                f"📊 Запросов: {u['total_requests']}\n"
                f"🚫 Заблокирован: {'Да' if u['is_blocked'] else 'Нет'}",
                reply_markup=inline.user_manage_kb(uid)
            )
        await state.clear()
    except:
        await msg.answer("❌ Введите корректный ID")

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
    await cb.message.edit_text("💎 <b>Выдать токены</b>\n\nВведите ID пользователя:")
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
        await msg.answer(
            f"👤 ID: {uid}\n💎 Баланс: {fmt(u['tokens'])}\n\nСколько выдать?",
            reply_markup=inline.give_kb()
        )
    except:
        await msg.answer("❌ Введите число")

@router.callback_query(F.data.startswith("gadd:"))
async def give_quick(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id): return
    amt = cb.data.split(":")[1]
    if amt == "custom":
        await cb.message.edit_text("✏️ Введите количество токенов:")
        await state.set_state(Adm.give_amt)
        return
    d = await state.get_data()
    await db.add_tokens(d['target'], int(amt))
    try: await bot.send_message(d['target'], f"🎉 Вам начислено <b>{fmt(int(amt))}</b> токенов!")
    except: pass
    await cb.message.edit_text(f"✅ Выдано {fmt(int(amt))} токенов", reply_markup=inline.back_kb("adm:back"))
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
    await cb.message.edit_text("📢 <b>Рассылка</b>\n\nВведите текст сообщения:")
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
        except:
            err += 1
    await cb.message.edit_text(f"✅ Отправлено: {ok}\n❌ Ошибок: {err}", reply_markup=inline.back_kb("adm:back"))
    await state.clear()
