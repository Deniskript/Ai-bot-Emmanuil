"""
Хендлеры для разделов Здоровье и Лайфстайл
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from keyboards import reply

router = Router()


# Здоровье теперь в отдельном хендлере handlers/health.py


# ========== ЛАЙФСТАЙЛ ==========

@router.message(F.text == "🏃 Лайфстайл")
async def lifestyle_menu(msg: Message, state: FSMContext):
    """Меню раздела Лайфстайл"""
    await msg.answer(
        "🏃 <b>Лайфстайл</b>\n\n"
        "Улучшай качество жизни:\n\n"
        "🎬 <b>Вирусный разбор</b> — анализ видео для соцсетей\n"
        "⏰ <b>Режим дня</b> — оптимизация расписания\n"
        "🎨 <b>Хобби</b> — развитие увлечений\n"
        "💰 <b>Финансы</b> — управление бюджетом\n"
        "🌟 <b>Саморазвитие</b> — личностный рост",
        reply_markup=reply.lifestyle_kb(msg.from_user.id),
        parse_mode="HTML"
    )


@router.message(F.text.in_(["⏰ Режим дня", "🎨 Хобби", "💰 Финансы", "🌟 Саморазвитие"]))
async def lifestyle_feature(msg: Message):
    """Функции раздела Лайфстайл"""
    await msg.answer(
        "⚠️ <b>Функция в разработке</b>\n\n"
        "Эта функция скоро будет доступна!\n"
        "Следите за обновлениями 🚀",
        parse_mode="HTML"
    )
