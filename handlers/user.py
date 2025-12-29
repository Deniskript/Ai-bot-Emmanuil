from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from database import db
from keyboards import reply, inline

router = Router()

def fmt(n): return f"{n:,}".replace(",", " ")

@router.message(CommandStart())
async def cmd_start(msg: Message):
    u = await db.get_user(msg.from_user.id)
    if not u:
        u = await db.create_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
        txt = f"👋 <b>Добро пожаловать!</b>\n\n🎁 Вам начислено <b>{fmt(u['tokens'])}</b> бесплатных токенов!\n\nЯ — AI-ассистент, который помнит тебя как друг.\nНапишите мне что-нибудь или используйте кнопки ниже."
    else:
        txt = f"👋 <b>С возвращением!</b>\n\n💎 Ваш баланс: <b>{fmt(u['tokens'])}</b> токенов\n\nЧем могу помочь?"
    await msg.answer(txt, reply_markup=reply.main_keyboard(), parse_mode="HTML")

@router.message(F.text == "✨ Начать диалог")
async def new_dialog(msg: Message):
    await db.clear_message_history(msg.from_user.id)
    await msg.answer("✨ <b>Новый диалог начат!</b>\n\nНапишите ваш вопрос, отправьте фото или голосовое.", reply_markup=reply.main_keyboard(), parse_mode="HTML")

@router.message(F.text == "👤 Мой кабинет")
async def cabinet(msg: Message):
    u = await db.get_user(msg.from_user.id)
    if not u: u = await db.create_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    m = await db.get_user_memory(msg.from_user.id)
    mem_st = "🟢 Включена" if m['memory_enabled'] else "🔴 Выключена"
    created = u['created_at'][:10] if u['created_at'] else "—"
    
    txt = f"👤 <b>ВАШ КАБИНЕТ</b>\n\n🆔 ID: <code>{msg.from_user.id}</code>\n📅 Регистрация: {created}\n\n<b>💰 БАЛАНС</b>\n\n💎 Доступно: <b>{fmt(u['tokens'])}</b> токенов\n📉 Потрачено: <b>{fmt(u['total_tokens_used'])}</b> токенов\n📊 Всего получено: <b>{fmt(u['total_tokens_received'])}</b> токенов\n\n<b>📈 СТАТИСТИКА</b>\n\n💬 Запросов сегодня: {u['daily_requests']}\n📝 За месяц: {u['monthly_requests']}\n🔢 Всего: {u['total_requests']}\n\n<b>🧠 ПАМЯТЬ</b>\n\nСтатус: {mem_st}"
    await msg.answer(txt, reply_markup=inline.cabinet_keyboard(m['memory_enabled']), parse_mode="HTML")

@router.callback_query(F.data == "topup_balance")
async def topup_cb(cb: CallbackQuery):
    await cb.answer()
    u = await db.get_user(cb.from_user.id)
    txt = f"💰 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\n💎 Ваш баланс: <b>{fmt(u['tokens'])}</b> токенов\n\n<b>Выберите пакет:</b>\n\n🥉 <b>45 000 токенов</b> — 300 ₽\n≈ 220 запросов\n\n🥈 <b>90 000 токенов</b> — 600 ₽\n≈ 440 запросов\n\n🥇 <b>180 000 токенов</b> — 900 ₽\n≈ 880 запросов\n\n💡 1 запрос ≈ 200 токенов\n\n📌 <b>Как оплатить:</b>\n1️⃣ Нажмите на нужный тариф\n2️⃣ Нажмите «💬 Оплатить»\n3️⃣ Напишите менеджеру"
    await cb.message.edit_text(txt, reply_markup=inline.topup_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "toggle_memory")
async def toggle_mem(cb: CallbackQuery):
    new = await db.toggle_memory(cb.from_user.id)
    await cb.answer("🟢 Память включена" if new else "🔴 Память выключена")
    await cb.message.edit_reply_markup(reply_markup=inline.cabinet_keyboard(new))

@router.callback_query(F.data == "clear_memory")
async def clear_mem(cb: CallbackQuery):
    await cb.answer()
    await cb.message.edit_text("🗑 <b>Очистить память?</b>\n\nЭто удалит всю сохранённую информацию о вас.\nДействие нельзя отменить.", reply_markup=inline.confirm_clear_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "confirm_clear")
async def confirm_clear(cb: CallbackQuery):
    await db.clear_memory(cb.from_user.id)
    await cb.answer("✅ Память очищена")
    u = await db.get_user(cb.from_user.id)
    m = await db.get_user_memory(cb.from_user.id)
    mem_st = "🟢 Включена" if m['memory_enabled'] else "🔴 Выключена"
    created = u['created_at'][:10] if u['created_at'] else "—"
    txt = f"👤 <b>ВАШ КАБИНЕТ</b>\n\n🆔 ID: <code>{cb.from_user.id}</code>\n📅 Регистрация: {created}\n\n<b>💰 БАЛАНС</b>\n\n💎 Доступно: <b>{fmt(u['tokens'])}</b> токенов\n📉 Потрачено: <b>{fmt(u['total_tokens_used'])}</b> токенов\n📊 Всего получено: <b>{fmt(u['total_tokens_received'])}</b> токенов\n\n<b>📈 СТАТИСТИКА</b>\n\n💬 Запросов сегодня: {u['daily_requests']}\n📝 За месяц: {u['monthly_requests']}\n🔢 Всего: {u['total_requests']}\n\n<b>🧠 ПАМЯТЬ</b>\n\nСтатус: {mem_st}"
    await cb.message.edit_text(txt, reply_markup=inline.cabinet_keyboard(m['memory_enabled']), parse_mode="HTML")

@router.callback_query(F.data == "cancel_clear")
async def cancel_clear(cb: CallbackQuery):
    await cb.answer("Отменено")
    u = await db.get_user(cb.from_user.id)
    m = await db.get_user_memory(cb.from_user.id)
    mem_st = "🟢 Включена" if m['memory_enabled'] else "🔴 Выключена"
    created = u['created_at'][:10] if u['created_at'] else "—"
    txt = f"👤 <b>ВАШ КАБИНЕТ</b>\n\n🆔 ID: <code>{cb.from_user.id}</code>\n📅 Регистрация: {created}\n\n<b>💰 БАЛАНС</b>\n\n💎 Доступно: <b>{fmt(u['tokens'])}</b> токенов\n📉 Потрачено: <b>{fmt(u['total_tokens_used'])}</b> токенов\n📊 Всего получено: <b>{fmt(u['total_tokens_received'])}</b> токенов\n\n<b>📈 СТАТИСТИКА</b>\n\n💬 Запросов сегодня: {u['daily_requests']}\n📝 За месяц: {u['monthly_requests']}\n🔢 Всего: {u['total_requests']}\n\n<b>🧠 ПАМЯТЬ</b>\n\nСтатус: {mem_st}"
    await cb.message.edit_text(txt, reply_markup=inline.cabinet_keyboard(m['memory_enabled']), parse_mode="HTML")

@router.message(F.text == "💰 Пополнить")
async def topup(msg: Message):
    u = await db.get_user(msg.from_user.id)
    txt = f"💰 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\n💎 Ваш баланс: <b>{fmt(u['tokens'])}</b> токенов\n\n<b>Выберите пакет:</b>\n\n🥉 <b>45 000 токенов</b> — 300 ₽\n≈ 220 запросов\n\n🥈 <b>90 000 токенов</b> — 600 ₽\n≈ 440 запросов\n\n🥇 <b>180 000 токенов</b> — 900 ₽\n≈ 880 запросов\n\n💡 1 запрос ≈ 200 токенов\n\n📌 <b>Как оплатить:</b>\n1️⃣ Нажмите на нужный тариф\n2️⃣ Нажмите «💬 Оплатить»\n3️⃣ Напишите менеджеру"
    await msg.answer(txt, reply_markup=inline.topup_keyboard(), parse_mode="HTML")

@router.message(F.text == "💡 Помощь")
async def help_cmd(msg: Message):
    txt = "💡 <b>ПОМОЩЬ</b>\n\n🤝 Первый бот, который помнит тебя как друг\n\n<b>✨ ВОЗМОЖНОСТИ</b>\n\n🧭 Найти себя и свой путь\n💬 Ответ на любой вопрос\n📚 Обучение лучше курсов\n✅ Проверка знаний\n🌟 Связь с собой\n\n<b>📝 КАК ПИСАТЬ</b>\n\n💬 Текст — просто напишите\n📷 Фото — отправьте изображение\n🎤 Голос — запишите голосовое"
    await msg.answer(txt, reply_markup=inline.help_keyboard(), parse_mode="HTML")
