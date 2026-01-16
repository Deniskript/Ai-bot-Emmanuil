"""
Обработчик Магия - автономный подмодуль Lifestyle
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import reply

router = Router()


class MagicSt(StatesGroup):
    """Состояния раздела Магия"""
    menu = State()


@router.message(F.text == "🔮 Эзотерика")
async def magic_menu(msg: Message, state: FSMContext):
    """Меню раздела Магия"""
    await state.set_state(MagicSt.menu)
    await msg.answer(
        "🔮 <b>Эзотерика</b>\n\n"
        "Выберите направление:\n\n"
        "✨ <b>Гороскоп</b> — персональные прогнозы\n"
        "🃏 <b>Таро</b> — расклады и карта дня\n"
        "🔮 <b>Гадания</b> — фото ладони/лица/кофе\n"
        "💫 <b>Нумерология</b> — числа судьбы и года\n"
        "🌙 <b>Лунный календарь</b> — фазы и советы\n"
        "⚡ <b>Ритуалы дня</b> — практики и аффирмации",
        reply_markup=reply.magic_kb(msg.from_user.id),
        parse_mode="HTML"
    )


@router.message(MagicSt.menu, F.text == "◀️ Назад")
async def magic_back(msg: Message, state: FSMContext):
    """Возврат в меню Лайфстайл"""
    await state.clear()
    await msg.answer(
        "🏆 <b>Лайфстайл</b>\n\n"
        "Улучшай качество жизни:\n\n"
        "🗓 <b>Режим дня</b> — оптимизация расписания\n"
        "🧘 <b>Ментальное</b> — забота о себе\n"
        "🔮 <b>Эзотерика</b> — гороскопы, таро и ритуалы\n"
        "🍎 <b>Здоровье</b> — калории и питание\n"
        "📖 <b>Как это работает?</b> — короткая инструкция",
        reply_markup=reply.lifestyle_kb(msg.from_user.id),
        parse_mode="HTML"
    )
