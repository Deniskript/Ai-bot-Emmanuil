"""
Централизованная система кнопок для AI чатов
Кнопка отмены запроса + система флагов
"""
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext

router = Router()


# ========== КОНСТАНТА КНОПКИ ==========

CANCEL_REQUEST_BTN = "⌛️ Отмена запроса"


# ========== КЛАВИАТУРА ОЖИДАНИЯ ==========

def get_waiting_kb() -> ReplyKeyboardMarkup:
    """Клавиатура во время ожидания ответа от AI"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_REQUEST_BTN)]],
        resize_keyboard=True
    )


# ========== СИСТЕМА ФЛАГОВ ОТМЕНЫ ==========

cancelled_requests: set[int] = set()


def cancel_user_request(user_id: int):
    """Отменить запрос — ответ не будет отправлен"""
    cancelled_requests.add(user_id)


def is_cancelled(user_id: int) -> bool:
    """Проверить отменён ли запрос"""
    return user_id in cancelled_requests


def clear_cancel(user_id: int):
    """Очистить флаг отмены"""
    cancelled_requests.discard(user_id)


# ========== FALLBACK ХЭНДЛЕР ==========

@router.message(F.text == CANCEL_REQUEST_BTN)
async def fallback_cancel(message: Message, state: FSMContext):
    """
    Fallback обработчик отмены запроса
    Срабатывает если модуль не перехватил кнопку
    """
    from keyboards.reply import bots_menu_kb
    
    user_id = message.from_user.id
    cancel_user_request(user_id)
    
    # Удалить сообщение пользователя
    try:
        await message.delete()
    except:
        pass
    
    await state.clear()
    await message.answer("❌ Запрос отменён", reply_markup=bots_menu_kb())
