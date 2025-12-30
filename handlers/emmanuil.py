from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from keyboards import inline

router = Router()

@router.message(F.text == "🤖 Emmanuil AI")
async def emmanuil(msg: Message):
    await msg.answer("🤖 <b>Emmanuil AI</b>\n\nВыберите собеседника:", reply_markup=inline.bots_kb())

@router.callback_query(F.data == "emmanuil")
async def emmanuil_cb(cb: CallbackQuery):
    await cb.message.edit_text("🤖 <b>Emmanuil AI</b>\n\nВыберите собеседника:", reply_markup=inline.bots_kb())
