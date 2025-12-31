from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from database import db
from keyboards import reply, inline
from prompts.all_prompts import AGREEMENT, HELP_LUCA, HELP_SILAS, HELP_TITUS, HELP_PAY

router = Router()

def fmt(n): return f"{n:,}".replace(",", " ")

@router.message(CommandStart())
async def start(msg: Message, state: FSMContext):
    await state.clear()
    u = await db.get_user(msg.from_user.id)
    if not u:
        u = await db.create_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    if not u['agreement']:
        await msg.answer(AGREEMENT, reply_markup=inline.agree_kb())
    else:
        await msg.answer(f"С возвращением!\n\nБаланс: <b>{fmt(u['tokens'])}</b>", reply_markup=reply.main_kb())

@router.callback_query(F.data == "agree_yes")
async def agree_yes(cb: CallbackQuery):
    await db.accept_agreement(cb.from_user.id)
    u = await db.get_user(cb.from_user.id)
    await cb.message.edit_text(f"✅ Добро пожаловать!\n\n🎁 Бонус: <b>{fmt(u['tokens'])}</b> токенов!")
    await cb.message.answer("Выбери раздел:", reply_markup=reply.main_kb())

@router.callback_query(F.data == "agree_no")
async def agree_no(cb: CallbackQuery):
    await cb.message.edit_text("❌ Нажмите /start чтобы принять")

@router.message(F.text == "🤖 Боты")
async def bots_menu(msg: Message):
    await msg.answer("🤖 <b>Выберите бота:</b>", reply_markup=inline.bots_kb())

@router.callback_query(F.data == "bots")
async def bots_cb(cb: CallbackQuery):
    await cb.message.edit_text("🤖 <b>Выберите бота:</b>", reply_markup=inline.bots_kb())

@router.message(F.text == "👤 Кабинет")
async def cabinet(msg: Message):
    u = await db.get_user(msg.from_user.id)
    if not u: return
    await msg.answer(
        f"👤 <b>Мой кабинет</b>\n\n"
        f"🆔 ID: <code>{msg.from_user.id}</code>\n"
        f"💎 Баланс: <b>{fmt(u['tokens'])}</b>\n"
        f"📊 Запросов: {u['total_requests']}",
        reply_markup=inline.cabinet_kb()
    )

@router.callback_query(F.data == "topup")
async def topup_cb(cb: CallbackQuery):
    u = await db.get_user(cb.from_user.id)
    await cb.message.edit_text(
        f"💰 <b>Пополнение</b>\n\n💎 Баланс: <b>{fmt(u['tokens'])}</b>",
        reply_markup=inline.topup_kb()
    )

@router.message(F.text == "💰 Пополнить")
async def topup(msg: Message):
    u = await db.get_user(msg.from_user.id)
    await msg.answer(
        f"💰 <b>Пополнение</b>\n\n💎 Баланс: <b>{fmt(u['tokens'])}</b>",
        reply_markup=inline.topup_kb()
    )

@router.message(F.text == "💡 Помощь")
async def help_cmd(msg: Message):
    await msg.answer("💡 <b>Помощь</b>", reply_markup=inline.help_kb())

@router.callback_query(F.data.startswith("help:"))
async def help_section(cb: CallbackQuery):
    s = cb.data.split(":")[1]
    texts = {'luca': HELP_LUCA, 'silas': HELP_SILAS, 'titus': HELP_TITUS, 'pay': HELP_PAY}
    back = {'luca': 'bot:luca', 'silas': 'bot:silas', 'titus': 'bot:titus', 'pay': 'help_back'}
    await cb.message.edit_text(texts.get(s, "?"), reply_markup=inline.back_kb(back.get(s, "help_back")))

@router.callback_query(F.data == "help_back")
async def help_back(cb: CallbackQuery):
    await cb.message.edit_text("💡 <b>Помощь</b>", reply_markup=inline.help_kb())

@router.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery):
    await cb.message.delete()
