"""
Обработчик раздела Соцсети
Оптимизирован с logging
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import reply
from handlers.lifestyle import viral

logger = logging.getLogger(__name__)

router = Router()

# Подключаем вирусный разбор в разделе Соцсети
router.include_router(viral.router)


class SocialsStates(StatesGroup):
    """Состояния для раздела Соцсети"""
    menu = State()


@router.message(F.text == "📲 Соцсети")
async def socials_menu(msg: Message, state: FSMContext):
    """Меню раздела Соцсети"""
    await state.set_state(SocialsStates.menu)
    
    # Отправляем баннер вместо текста
    banner = FSInputFile("assets/banner_socials.png")
    await msg.answer_photo(
        photo=banner,
        reply_markup=reply.socials_menu_kb(msg.from_user.id)
    )


@router.message(SocialsStates.menu, F.text == "◀️ Назад")
async def socials_back_to_bots(msg: Message, state: FSMContext):
    """Возврат из Соцсетей в меню ботов"""
    await state.clear()
    await msg.answer("🫧 Soul AI", reply_markup=reply.bots_menu_kb())


@router.message(F.text == "📹 Анализ видео")
async def socials_video_analysis(message: Message, state: FSMContext):
    """Старт анализа видео (логика Titus)."""
    from handlers.titus.handler import video_analysis_start
    await video_analysis_start(message, state)
