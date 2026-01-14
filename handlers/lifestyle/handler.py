"""
Обработчик Lifestyle - объединяет все модули лайфстайла
100% автономный модуль
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from keyboards import reply

# Локальные импорты модуля
from . import config as lifestyle_config
from . import viral
from . import routine
from . import goals
from . import mental
from . import finance

router = Router()

# Подключаем роутеры подмодулей
router.include_router(viral.router)
router.include_router(routine.router)
router.include_router(goals.router)
router.include_router(mental.router)
router.include_router(finance.router)


# ========== ГЛАВНОЕ МЕНЮ ЛАЙФСТАЙЛ ==========

@router.message(F.text == "🏃 Лайфстайл")
async def lifestyle_menu(msg: Message, state: FSMContext):
    """Меню раздела Лайфстайл"""
    await msg.answer(
        "🏃 <b>Лайфстайл</b>\n\n"
        "Улучшай качество жизни:\n\n"
        "🎬 <b>Вирусный разбор</b> — анализ видео для соцсетей\n"
        "🌅 <b>Режим дня</b> — оптимизация расписания\n"
        "🎯 <b>Трекер целей</b> — достижение целей\n"
        "🧘 <b>Ментальное</b> — забота о себе\n"
        "💰 <b>Финансы</b> — управление бюджетом",
        reply_markup=reply.lifestyle_kb(msg.from_user.id),
        parse_mode="HTML"
    )
