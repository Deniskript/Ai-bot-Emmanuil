"""
Обработчик Lifestyle - объединяет все модули лайфстайла
100% автономный модуль
Оптимизирован с logging
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from keyboards import reply
from database import postgres_db as db
from utils.calories import format_calories_summary

logger = logging.getLogger(__name__)

# Локальные импорты модуля
from . import config as lifestyle_config
from . import routine
from . import mental
from . import magic

router = Router()

# Подключаем роутеры подмодулей
router.include_router(routine.router)
router.include_router(mental.router)
router.include_router(magic.router)

# Удалённые разделы оставляем закомментированными по требованиям
# from . import viral  # перенесено в соцсети
# from . import goals  # удалено из меню
# from . import finance  # удалено из меню
# router.include_router(viral.router)
# router.include_router(goals.router)
# router.include_router(finance.router)


# ========== ГЛАВНОЕ МЕНЮ ЛАЙФСТАЙЛ ==========

@router.message(F.text == "🏆 Лайфстайл")
async def lifestyle_menu(msg: Message, state: FSMContext):
    """Меню раздела Лайфстайл"""
    
    # Отправляем баннер вместо текста
    banner = FSInputFile("assets/banner_lifestyle.png")
    await msg.answer_photo(
        photo=banner,
        reply_markup=reply.lifestyle_kb(msg.from_user.id)
    )


# ========== ПЕРЕХОД В ЗДОРОВЬЕ ИЗ ЛЮБОГО СОСТОЯНИЯ ==========

@router.message(routine.RoutineStates.menu, F.text == "🍎 Здоровье")
@router.message(mental.MentalStates.menu, F.text == "🍎 Здоровье")
@router.message(magic.MagicSt.menu, F.text == "🍎 Здоровье")
async def go_to_health_from_lifestyle(msg: Message, state: FSMContext):
    """Переход в раздел Здоровье из состояний Lifestyle"""
    from handlers.health import HealthStates
    
    await state.set_state(HealthStates.menu)
    
    # Получаем статистику за сегодня
    today_stats = await db.get_today_calories(msg.from_user.id)
    goal = await db.get_nutrition_goal(msg.from_user.id)
    
    text = "🍎 <b>Здоровье</b>\n\n"
    text += "Следи за питанием и достигай целей!\n\n"
    
    if today_stats['calories'] > 0:
        text += "📊 <b>Сегодня:</b>\n"
        text += format_calories_summary(today_stats, goal)
    else:
        text += "<i>Сегодня ещё нет записей</i>"
    
    await msg.answer(text, parse_mode="HTML", reply_markup=reply.health_kb(msg.from_user.id))
