from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from database import db
from keyboards import reply, inline
from prompts.all_prompts import AGREEMENT, HELP_LUCA, HELP_SILAS, HELP_TITUS, HELP_PAY

router = Router()

def fmt(n): return f"{n:,}".replace(",", " ")

async def get_text(key, default=""):
    """Получить текст из БД или вернуть default"""
    t = await db.get_text(key)
    return t if t else default

@router.message(CommandStart())
async def start(msg: Message, state: FSMContext):
    await state.clear()
    u = await db.get_user(msg.from_user.id)
    if not u:
        u = await db.create_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    if not u['agreement']:
        # Берём текст из БД или default
        agreement_text = await get_text("agreement", AGREEMENT)
        await msg.answer(agreement_text, reply_markup=inline.agree_kb())
    else:
        start_text = await get_text("start_message", "С возвращением!\n\nБаланс: <b>{tokens}</b>")
        start_text = start_text.replace("{tokens}", fmt(u['tokens']))
        await msg.answer(start_text, reply_markup=reply.main_kb())

@router.callback_query(F.data == "agree_yes")
async def agree_yes(cb: CallbackQuery):
    await db.accept_agreement(cb.from_user.id)
    u = await db.get_user(cb.from_user.id)
    welcome_text = await get_text("welcome_message", "✅ Добро пожаловать!\n\n🎁 Бонус: <b>{tokens}</b> токенов!")
    welcome_text = welcome_text.replace("{tokens}", fmt(u['tokens']))
    await cb.message.edit_text(welcome_text)
    await cb.message.answer("Выбери раздел:", reply_markup=reply.main_kb())

@router.callback_query(F.data == "agree_no")
async def agree_no(cb: CallbackQuery):
    await cb.message.edit_text("❌ Нажмите /start чтобы принять")

@router.message(F.text == "🤖 Emmanuil AI")
async def emmanuil_btn(msg: Message):
    await msg.answer("🤖 <b>Выберите бота:</b>", reply_markup=await inline.get_bots_kb_dynamic())

@router.callback_query(F.data == "bots")
async def bots_cb(cb: CallbackQuery):
    await cb.message.edit_text("🤖 <b>Выберите бота:</b>", reply_markup=await inline.get_bots_kb_dynamic())

@router.message(F.text == "👤 Кабинет")
async def cabinet(msg: Message):
    u = await db.get_user(msg.from_user.id)
    if not u: return
    cabinet_text = await get_text("cabinet_message", 
        "👤 <b>Мой кабинет</b>\n\n🆔 ID: <code>{user_id}</code>\n💎 Баланс: <b>{tokens}</b>\n📊 Запросов: {requests}")
    cabinet_text = cabinet_text.replace("{user_id}", str(msg.from_user.id))
    cabinet_text = cabinet_text.replace("{tokens}", fmt(u['tokens']))
    cabinet_text = cabinet_text.replace("{requests}", str(u['total_requests']))
    await msg.answer(cabinet_text, reply_markup=inline.cabinet_kb())

@router.callback_query(F.data == "topup")
async def topup_cb(cb: CallbackQuery):
    u = await db.get_user(cb.from_user.id)
    topup_text = await get_text("topup_message", "💰 <b>Пополнение</b>\n\n💎 Баланс: <b>{tokens}</b>")
    topup_text = topup_text.replace("{tokens}", fmt(u['tokens']))
    await cb.message.edit_text(topup_text, reply_markup=inline.topup_kb())

@router.message(F.text == "💰 Пополнить")
async def topup(msg: Message):
    u = await db.get_user(msg.from_user.id)
    topup_text = await get_text("topup_message", "💰 <b>Пополнение</b>\n\n💎 Баланс: <b>{tokens}</b>")
    topup_text = topup_text.replace("{tokens}", fmt(u['tokens']))
    await msg.answer(topup_text, reply_markup=inline.topup_kb())

@router.message(F.text == "💡 Помощь")
async def help_cmd(msg: Message):
    help_text = await get_text("help_message", "💡 <b>Помощь</b>")
    await msg.answer(help_text, reply_markup=inline.help_kb())

@router.callback_query(F.data.startswith("help:"))
async def help_section(cb: CallbackQuery):
    s = cb.data.split(":")[1]
    # Сначала пробуем из БД
    db_keys = {'luca': 'help_luca', 'silas': 'help_silas', 'titus': 'help_titus', 'pay': 'help_pay'}
    defaults = {'luca': HELP_LUCA, 'silas': HELP_SILAS, 'titus': HELP_TITUS, 'pay': HELP_PAY}
    back = {'luca': 'bot:luca', 'silas': 'bot:silas', 'titus': 'bot:titus', 'pay': 'help_back'}
    
    text = await get_text(db_keys.get(s, ""), defaults.get(s, "?"))
    await cb.message.edit_text(text, reply_markup=inline.back_kb(back.get(s, "help_back")))

@router.callback_query(F.data == "help_back")
async def help_back(cb: CallbackQuery):
    help_text = await get_text("help_message", "💡 <b>Помощь</b>")
    await cb.message.edit_text(help_text, reply_markup=inline.help_kb())

@router.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery):
    await cb.message.delete()
