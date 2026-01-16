"""
Обработчик раздела Соцсети
"""
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
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
    
    # Отправляем баннер вместо текста
    banner = FSInputFile("assets/banner_socials.png")
    await msg.answer_photo(
        photo=banner,
        reply_markup=reply.socials_menu_kb(msg.from_user.id)
    )


@router.message(F.text == "📹 Анализ видео")
async def socials_video_analysis(message: Message, state: FSMContext):
    """Старт анализа видео (логика Titus)."""
    from handlers.titus.handler import video_analysis_start
    await video_analysis_start(message, state)
