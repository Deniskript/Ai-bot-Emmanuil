from aiogram import Router, F
import psutil
import aiosqlite
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loader import bot
from database import db
from keyboards import inline
from config import ADMIN_IDS
import subprocess


router = Router()


class Adm(StatesGroup):
    find = State()
    give_id = State()
    give_amt = State()
    bc = State()
    model = State()
    version = State()


class Editor(StatesGroup):
    text_key = State()
    text_val = State()
    btn_key = State()
    btn_emoji = State()
    btn_text = State()
    media_upload = State()
    git_msg = State()


def is_adm(uid):
    return uid in ADMIN_IDS


def fmt(n):
    return f"{n:,}".replace(",", " ")


@router.message(Command("admin"))
async def admin(msg: Message, state: FSMContext):
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


@router.callback_query(F.data == "adm:stats")
async def stats(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
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
    if not is_adm(cb.from_user.id):
        return
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    s = await db.get_stats()
    if cpu < 50:
        status = "🟢 Нормальная"
    elif cpu < 80:
        status = "🟡 Средняя"
    else:
        status = "🔴 Высокая"
    await cb.message.edit_text(
        f"📈 <b>Нагрузка</b>\n\n💻 CPU: {cpu}%\n🧠 RAM: {mem.percent}%\n"
        f"👥 Юзеров: {fmt(s['users'])}\n💬 Запросов: {fmt(s['reqs'])}\n\nСтатус: {status}",
        reply_markup=inline.back_kb("adm:back"))


@router.callback_query(F.data == "adm:bots")
async def bots(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
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
    if not is_adm(cb.from_user.id):
        return
    b = cb.data.split(":")[1]
    cfg = await db.get_bot_cfg(b)
    names = {'luca': '💭 Luca', 'silas': '🛋️ Silas', 'titus': '📓 Titus'}
    await cb.message.edit_text(
        f"⚙️ <b>{names[b]}</b>\n\nСтатус: {'🟢' if cfg['enabled'] else '🔴'}\n"
        f"Модель: {cfg['model']}\nВерсия: {cfg['version']}",
        reply_markup=inline.bot_cfg_kb(b, cfg['enabled'], cfg['model']))


@router.callback_query(F.data.startswith("tog:"))
async def toggle(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    b = cb.data.split(":")[1]
    cfg = await db.get_bot_cfg(b)
    await db.set_bot_enabled(b, not cfg['enabled'])
    await cb.answer(f"{'🟢 Вкл' if not cfg['enabled'] else '🔴 Выкл'}")
    cb.data = f"botcfg:{b}"
    await bot_cfg(cb)


@router.callback_query(F.data.startswith("prov:"))
async def select_provider(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    b = parts[1]
    provider = parts[2]
    cfg = await db.get_bot_cfg(b)
    current = cfg['model']
    if provider == "gpt":
        await cb.message.edit_text(
            f"🤖 <b>GPT модели для {b.title()}</b>\n\nТекущая: {current}",
            reply_markup=inline.gpt_models_kb(b, current))
    else:
        await cb.message.edit_text(
            f"🤖 <b>Claude модели для {b.title()}</b>\n\nТекущая: {current}",
            reply_markup=inline.claude_models_kb(b, current))


@router.callback_query(F.data.startswith("setm:"))
async def set_model_btn(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    b = parts[1]
    model = parts[2]
    await db.set_bot_model(b, model)
    await cb.answer(f"✅ {model}")
    cb.data = f"botcfg:{b}"
    await bot_cfg(cb)


@router.callback_query(F.data.startswith("ver:"))
async def change_ver(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    b = cb.data.split(":")[1]
    await state.update_data(bot=b)
    await state.set_state(Adm.version)
    await cb.message.edit_text("📝 Введите версию (например 1.0.1):")


@router.message(Adm.version)
async def set_ver(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    d = await state.get_data()
    await db.set_bot_version(d['bot'], msg.text)
    await state.clear()
    await msg.answer(f"✅ Версия: {msg.text}", reply_markup=inline.back_kb("adm:bots"))


@router.callback_query(F.data == "adm:spam")
async def spam_settings(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
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


@router.callback_query(F.data == "adm:users")
async def users_list(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
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
    if not is_adm(cb.from_user.id):
        return
    uid = int(cb.data.split(":")[1])
    await db.block_user(uid)
    await cb.answer("🚫 Заблокирован")
    await cb.message.edit_text("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=inline.admin_kb())


@router.callback_query(F.data == "adm:give")
async def give_start(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    await cb.message.edit_text("💎 <b>Выдать токены</b>\n\nВведите ID:")
    await state.set_state(Adm.give_id)


@router.message(Adm.give_id)
async def give_id(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
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
    if not is_adm(cb.from_user.id):
        return
    amt = cb.data.split(":")[1]
    if amt == "custom":
        await cb.message.edit_text("✏️ Введите количество:")
        await state.set_state(Adm.give_amt)
        return
    d = await state.get_data()
    await db.add_tokens(d['target'], int(amt))
    try:
        await bot.send_message(d['target'], f"🎉 Вам начислено <b>{fmt(int(amt))}</b> токенов!")
    except:
        pass
    await cb.message.edit_text(f"✅ Выдано {fmt(int(amt))}", reply_markup=inline.back_kb("adm:back"))
    await state.clear()


@router.message(Adm.give_amt)
async def give_custom(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    try:
        amt = int(msg.text)
        d = await state.get_data()
        await db.add_tokens(d['target'], amt)
        try:
            await bot.send_message(d['target'], f"🎉 Вам начислено <b>{fmt(amt)}</b> токенов!")
        except:
            pass
        await msg.answer(f"✅ Выдано {fmt(amt)}", reply_markup=inline.back_kb("adm:back"))
        await state.clear()
    except:
        await msg.answer("❌ Введите число")


@router.callback_query(F.data == "adm:bc")
async def bc_start(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    await cb.message.edit_text("📢 <b>Рассылка</b>\n\nВведите текст:")
    await state.set_state(Adm.bc)


@router.message(Adm.bc)
async def bc_preview(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    await state.update_data(bc_text=msg.text)
    await msg.answer(f"📢 <b>Превью:</b>\n\n{msg.text}", reply_markup=inline.confirm_bc_kb())


@router.callback_query(F.data == "bc:send")
async def bc_send(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
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


@router.callback_query(F.data == "adm:maint")
async def maint(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    c = await db.get_setting('maintenance')
    n = '0' if c == '1' else '1'
    await db.set_setting('maintenance', n)
    await cb.answer(f"🔧 Тех.работы: {'ВКЛ' if n == '1' else 'ВЫКЛ'}")
    await cb.message.edit_text("👑 <b>АДМИН-ПАНЕЛЬ</b>", reply_markup=inline.admin_kb())


@router.callback_query(F.data == "adm:editor")
async def editor_menu(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    await state.clear()
    await cb.message.edit_text(
        "✏️ <b>Редактор бота</b>\n\n"
        "📝 Тексты — изменить тексты сообщений\n"
        "🔘 Кнопки — изменить названия кнопок\n"
        "🖼 Медиа — фото/видео приветствия\n"
        "💾 Git — сохранить проект",
        reply_markup=inline.editor_kb())


@router.callback_query(F.data == "edit:texts")
async def texts_list(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    texts = await db.get_all_texts()
    if not texts:
        await db.set_text("start_message", "Привет! Я AI бот 🤖", "Приветствие /start")
        await db.set_text("help_message", "Выберите помощника", "Текст помощи")
        texts = await db.get_all_texts()
    await cb.message.edit_text(
        "📝 <b>Тексты бота</b>\n\nВыберите для редактирования:",
        reply_markup=inline.texts_list_kb(texts))


@router.callback_query(F.data.startswith("txt:"))
async def text_view(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    key = cb.data.split(":", 1)[1]
    if key == "add":
        await cb.message.edit_text("📝 Введите ключ нового текста (латиницей):")
        await state.set_state(Editor.text_key)
        return
    texts = await db.get_all_texts()
    t = next((x for x in texts if x['key'] == key), None)
    if t:
        await cb.message.edit_text(
            f"📝 <b>{t['key']}</b>\n\n{t['description'] or ''}\n\n"
            f"<code>{t['value'][:500]}</code>",
            reply_markup=inline.text_edit_kb(key))


@router.message(Editor.text_key)
async def text_add_key(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    await state.update_data(text_key=msg.text)
    await msg.answer("📝 Теперь введите текст:")
    await state.set_state(Editor.text_val)


@router.message(Editor.text_val)
async def text_add_val(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    d = await state.get_data()
    await db.set_text(d['text_key'], msg.text)
    await msg.answer(f"✅ Текст <b>{d['text_key']}</b> сохранён!", reply_markup=inline.back_kb("edit:texts"))
    await state.clear()


@router.callback_query(F.data.startswith("txte:"))
async def text_edit(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    key = cb.data.split(":", 1)[1]
    await state.update_data(text_key=key)
    await cb.message.edit_text(f"✏️ Введите новый текст для <b>{key}</b>:")
    await state.set_state(Editor.text_val)


@router.callback_query(F.data.startswith("txtd:"))
async def text_del(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    key = cb.data.split(":", 1)[1]
    async with aiosqlite.connect(db.DATABASE_PATH) as conn:
        await conn.execute("DELETE FROM bot_texts WHERE key=?", (key,))
        await conn.commit()
    await cb.answer(f"🗑 Удалено: {key}")
    await texts_list(cb)


@router.callback_query(F.data == "edit:buttons")
async def buttons_list(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    buttons = await db.get_all_buttons()
    if not buttons:
        await db.set_button("luca", "🧑", "Luca", "Кнопка Luca")
        await db.set_button("silas", "🧠", "Silas", "Кнопка Silas")
        await db.set_button("titus", "📚", "Titus", "Кнопка Titus")
        buttons = await db.get_all_buttons()
    await cb.message.edit_text(
        "🔘 <b>Кнопки бота</b>\n\nВыберите для редактирования:",
        reply_markup=inline.buttons_list_kb(buttons))


@router.callback_query(F.data.startswith("btn:"))
async def button_view(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    key = cb.data.split(":", 1)[1]
    if key == "add":
        await cb.message.edit_text("🔘 Введите ключ кнопки (латиницей):")
        await state.set_state(Editor.btn_key)
        return
    b = await db.get_button(key)
    await cb.message.edit_text(
        f"🔘 <b>{key}</b>\n\n😀 Эмодзи: {b['emoji']}\n✏️ Текст: {b['text']}",
        reply_markup=inline.button_edit_kb(key))


@router.message(Editor.btn_key)
async def btn_add_key(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    await state.update_data(btn_key=msg.text)
    await msg.answer("😀 Введите эмодзи:")
    await state.set_state(Editor.btn_emoji)


@router.message(Editor.btn_emoji)
async def btn_add_emoji(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    d = await state.get_data()
    if d.get('edit_mode') == 'emoji':
        b = await db.get_button(d['btn_key'])
        await db.set_button(d['btn_key'], msg.text, b['text'])
        await msg.answer("✅ Эмодзи изменён!", reply_markup=inline.back_kb("edit:buttons"))
        await state.clear()
    else:
        await state.update_data(btn_emoji=msg.text)
        await msg.answer("✏️ Введите текст кнопки:")
        await state.set_state(Editor.btn_text)


@router.message(Editor.btn_text)
async def btn_add_text(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    d = await state.get_data()
    if d.get('edit_mode') == 'text':
        b = await db.get_button(d['btn_key'])
        await db.set_button(d['btn_key'], b['emoji'], msg.text)
        await msg.answer("✅ Текст изменён!", reply_markup=inline.back_kb("edit:buttons"))
    else:
        await db.set_button(d['btn_key'], d['btn_emoji'], msg.text)
        await msg.answer(f"✅ Кнопка сохранена: {d['btn_emoji']} {msg.text}", reply_markup=inline.back_kb("edit:buttons"))
    await state.clear()


@router.callback_query(F.data.startswith("btne:"))
async def btn_edit_emoji(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    key = cb.data.split(":", 1)[1]
    await state.update_data(btn_key=key, edit_mode="emoji")
    await cb.message.edit_text(f"😀 Введите новый эмодзи для <b>{key}</b>:")
    await state.set_state(Editor.btn_emoji)


@router.callback_query(F.data.startswith("btnt:"))
async def btn_edit_text(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    key = cb.data.split(":", 1)[1]
    await state.update_data(btn_key=key, edit_mode="text")
    await cb.message.edit_text(f"✏️ Введите новый текст для <b>{key}</b>:")
    await state.set_state(Editor.btn_text)


@router.callback_query(F.data.startswith("btnd:"))
async def btn_delete(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    key = cb.data.split(":", 1)[1]
    async with aiosqlite.connect(db.DATABASE_PATH) as conn:
        await conn.execute("DELETE FROM bot_buttons WHERE key=?", (key,))
        await conn.commit()
    await cb.answer(f"🗑 Удалено: {key}")
    await buttons_list(cb)


@router.callback_query(F.data == "edit:media")
async def media_menu(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    await cb.message.edit_text(
        "🖼 <b>Медиа приветствия</b>\n\n"
        "Загрузите фото или видео для приветствий:",
        reply_markup=inline.media_kb())


@router.callback_query(F.data.startswith("media:"))
async def media_view(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    key = cb.data.split(":")[1]
    names = {'start': '/start', 'luca': 'Luca', 'silas': 'Silas', 'titus': 'Titus'}
    m = await db.get_media(key)
    has = m is not None
    status = f"✅ {m['type']}" if has else "❌ Не загружено"
    await cb.message.edit_text(
        f"🖼 <b>Медиа: {names.get(key, key)}</b>\n\nСтатус: {status}",
        reply_markup=inline.media_edit_kb(key, has))


@router.callback_query(F.data.startswith("mup:"))
async def media_upload_start(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    key = cb.data.split(":")[1]
    await state.update_data(media_key=key)
    await cb.message.edit_text("📤 Отправьте фото или видео:")
    await state.set_state(Editor.media_upload)


@router.message(Editor.media_upload, F.photo)
async def media_photo(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    d = await state.get_data()
    file_id = msg.photo[-1].file_id
    await db.set_media(d['media_key'], 'photo', file_id)
    await msg.answer("✅ Фото сохранено!", reply_markup=inline.back_kb("edit:media"))
    await state.clear()


@router.message(Editor.media_upload, F.video)
async def media_video(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    d = await state.get_data()
    file_id = msg.video.file_id
    await db.set_media(d['media_key'], 'video', file_id)
    await msg.answer("✅ Видео сохранено!", reply_markup=inline.back_kb("edit:media"))
    await state.clear()


@router.callback_query(F.data.startswith("mdel:"))
async def media_delete(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    key = cb.data.split(":")[1]
    await db.delete_media(key)
    await cb.answer("🗑 Удалено")
    await media_menu(cb)


@router.callback_query(F.data == "edit:git")
async def git_menu(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    await cb.message.edit_text(
        "💾 <b>Git бэкап</b>\n\n"
        "Сохранить текущее состояние проекта в Git?\n\n"
        "Введите комментарий к сохранению:",
        reply_markup=inline.back_kb("adm:editor"))
    await state.set_state(Editor.git_msg)


@router.message(Editor.git_msg)
async def git_msg(msg: Message, state: FSMContext):
    if not is_adm(msg.from_user.id):
        return
    await state.update_data(git_msg=msg.text)
    await msg.answer(
        f"💾 <b>Подтверждение</b>\n\nКомментарий: {msg.text}\n\nСохранить?",
        reply_markup=inline.confirm_git_kb())


@router.callback_query(F.data == "git:save")
async def git_save(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    d = await state.get_data()
    msg_text = d.get('git_msg', 'Auto backup')
    await cb.message.edit_text("⏳ Сохранение...")
    try:
        subprocess.run(["git", "add", "."], cwd="/root/ai-bot", check=True)
        subprocess.run(["git", "commit", "-m", msg_text], cwd="/root/ai-bot", check=True)
        subprocess.run(["git", "push"], cwd="/root/ai-bot", capture_output=True, text=True)
        await cb.message.edit_text(
            f"✅ <b>Проект сохранён!</b>\n\n💬 {msg_text}",
            reply_markup=inline.back_kb("adm:editor"))
    except Exception as e:
        await cb.message.edit_text(
            f"❌ <b>Ошибка Git</b>\n\n{str(e)[:200]}",
            reply_markup=inline.back_kb("adm:editor"))
    await state.clear()


# === УПРАВЛЕНИЕ ПАМЯТЬЮ ===
class MemEdit(StatesGroup):
    edit_fact = State()
    add_fact = State()


@router.callback_query(F.data == "adm:memory")
async def memory_menu(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    total = await db.count_users_with_memory()
    await cb.message.edit_text(
        f"🧠 <b>Память пользователей</b>\n\n"
        f"Всего пользователей с памятью: {total}",
        reply_markup=inline.memory_admin_kb())


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
    bot = parts[3]
    
    facts = await db.get_memory(uid, bot)
    bot_names = {'luca': '💭 Диалог', 'silas': '🧘 Психолог', 'titus': '📚 Репетитор'}
    
    await cb.message.edit_text(
        f"🧠 <b>{bot_names.get(bot, bot)}</b>\n"
        f"👤 ID: <code>{uid}</code>\n\n"
        f"📋 Фактов: {len(facts)}",
        reply_markup=inline.memory_facts_kb(uid, bot, facts))


@router.callback_query(F.data.startswith("mem:facts:"))
async def memory_facts_page(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    uid = int(parts[2])
    bot = parts[3]
    page = int(parts[4])
    
    facts = await db.get_memory(uid, bot)
    await cb.message.edit_reply_markup(
        reply_markup=inline.memory_facts_kb(uid, bot, facts, page))


@router.callback_query(F.data.startswith("mem:view:"))
async def memory_view_fact(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    uid = int(parts[2])
    bot = parts[3]
    idx = int(parts[4])
    
    facts = await db.get_memory(uid, bot)
    if idx < len(facts):
        await cb.message.edit_text(
            f"📝 <b>Факт #{idx+1}</b>\n\n{facts[idx]}",
            reply_markup=inline.memory_fact_view_kb(uid, bot, idx))


@router.callback_query(F.data.startswith("mem:del:"))
async def memory_delete_fact(cb: CallbackQuery):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    uid = int(parts[2])
    bot = parts[3]
    idx = int(parts[4])
    
    await db.delete_memory_fact(uid, bot, idx)
    await cb.answer("🗑 Факт удалён")
    
    # Обновляем список
    facts = await db.get_memory(uid, bot)
    bot_names = {'luca': '💭 Диалог', 'silas': '🧘 Психолог', 'titus': '📚 Репетитор'}
    await cb.message.edit_text(
        f"🧠 <b>{bot_names.get(bot, bot)}</b>\n"
        f"👤 ID: <code>{uid}</code>\n\n"
        f"📋 Фактов: {len(facts)}",
        reply_markup=inline.memory_facts_kb(uid, bot, facts))


@router.callback_query(F.data.startswith("mem:edit:"))
async def memory_edit_start(cb: CallbackQuery, state: FSMContext):
    if not is_adm(cb.from_user.id):
        return
    parts = cb.data.split(":")
    uid = int(parts[2])
    bot = parts[3]
    idx = int(parts[4])
    
    facts = await db.get_memory(uid, bot)
    await state.update_data(mem_uid=uid, mem_bot=bot, mem_idx=idx)
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
    bot = parts[3]
    
    await state.update_data(mem_uid=uid, mem_bot=bot)
    await state.set_state(MemEdit.add_fact)
    await cb.message.edit_text("➕ <b>Добавить факт</b>\n\nВведите текст нового факта:")


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
    bot = parts[3]
    
    await db.clear_user_memory(uid, bot)
    await cb.answer("🗑 Память бота очищена")
    
    # Возврат к пользователю
    bots = await db.get_user_all_memory(uid)
    if bots:
        await cb.message.edit_text(
            f"👤 ID: <code>{uid}</code>",
            reply_markup=inline.memory_user_bots_kb(uid, bots))
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
