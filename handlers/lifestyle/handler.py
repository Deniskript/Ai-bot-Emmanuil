"""
Обработчик Lifestyle - объединяет все модули лайфстайла
100% автономный модуль
"""
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from keyboards import reply

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
