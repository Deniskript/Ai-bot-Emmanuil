"""
Обработчик раздела Соцсети
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from keyboards import reply
from handlers.lifestyle import viral

router = Router()

# Подключаем вирусный разбор в разделе Соцсети
router.include_router(viral.router)


@router.message(F.text == "📲 Соцсети")
async def socials_menu(msg: Message, state: FSMContext):
    """Меню раздела Соцсети"""
    await state.clear()
    await msg.answer(
        "📲 <b>Соцсети</b>\n\n"
        "Инструменты для роста и оформления:\n\n"
        "🎬 <b>Вирусный разбор</b> — анализ роликов\n"
        "🖼 <b>Обложки</b> — обложки / логотипы / презентации\n"
        "📖 <b>Как это работает?</b> — короткая инструкция",
        reply_markup=reply.socials_menu_kb(msg.from_user.id),
        parse_mode="HTML",
    )
