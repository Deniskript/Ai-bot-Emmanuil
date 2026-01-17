"""
Централизованная система проверки баланса звёзд ⭐.
Единое место для проверки и красивых сообщений о нехватке звёзд.
"""

from functools import wraps
from typing import Optional, Union
from aiogram import types, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import postgres_db as db


# ============================================================================
# КРАСИВОЕ СООБЩЕНИЕ О НЕХВАТКЕ ЗВЁЗД
# ============================================================================

NO_TOKENS_MESSAGE = """
😔 <b>Звёзды закончились</b>

У тебя недостаточно звёзд для этого действия.

┌─────────────────────────┐
│  ⭐ Твой баланс: <b>{available:,}</b>  │
│  📊 Нужно: <b>{required:,}</b>        │
└─────────────────────────┘

<b>Что делать?</b>
• Оформи подписку — получишь звёзды каждый месяц
• Пригласи друзей — получишь бонус за каждого

✨ <i>С подпиской ты сможешь пользоваться всеми возможностями Soul без ограничений!</i>
"""

NO_TOKENS_MESSAGE_SIMPLE = """
😔 <b>Звёзды закончились</b>

⭐ Твой баланс: <b>{available:,}</b>

Оформи подписку чтобы продолжить пользоваться Soul ✨
"""


def get_no_stars_keyboard(has_subscription: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для сообщения о нехватке звёзд"""
    buttons = []
    
    if not has_subscription:
        buttons.append([
            InlineKeyboardButton(
                text="⭐ Подписка",
                callback_data="subscription_plans"
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="📦 Докупить звёзды",
                callback_data="buy_stars"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text="👥 Пригласить друзей",
            callback_data="referral_info"
        )
    ])
    
    buttons.append([
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================================
# ПРОВЕРКА БАЛАНСА
# ============================================================================

async def check_balance(user_id: int, required: int = 0) -> tuple[bool, int]:
    """
    Проверить достаточно ли звёзд.
    
    Args:
        user_id: ID пользователя
        required: Минимально необходимое количество звёзд (0 = просто > 0)
        
    Returns:
        (can_proceed, current_stars)
        - can_proceed: True если можно продолжить
        - current_stars: Текущий баланс звёзд
    """
    stars_balance = await db.get_available_stars(user_id)
    
    # Если баланс отрицательный или 0 — нельзя
    if stars_balance <= 0:
        return False, stars_balance
    
    # Если указан required и баланс меньше — нельзя
    if required > 0 and stars_balance < required:
        return False, stars_balance
    
    return True, stars_balance


async def send_no_stars_message(
    target: Union[types.Message, types.CallbackQuery],
    stars_balance: int,
    required: int = 0,
    bot: Bot = None
) -> types.Message:
    """
    Отправить красивое сообщение о нехватке звёзд.
    
    Args:
        target: Message или CallbackQuery
        stars_balance: Текущий баланс звёзд
        required: Требуемое количество (если известно)
        bot: Bot instance (опционально)
        
    Returns:
        Отправленное сообщение
    """
    # Получаем user_id
    if isinstance(target, types.CallbackQuery):
        user_id = target.from_user.id
        message = target.message
    else:
        user_id = target.from_user.id
        message = target
    
    # Проверяем есть ли подписка
    subscription = await db.get_subscription(user_id)
    has_subscription = subscription and subscription.get('is_active')
    
    # Формируем сообщение
    if required > 0:
        text = NO_TOKENS_MESSAGE.format(
            available=max(0, stars_balance),
            required=required
        )
    else:
        text = NO_TOKENS_MESSAGE_SIMPLE.format(
            available=max(0, stars_balance)
        )
    
    keyboard = get_no_stars_keyboard(has_subscription)
    
    # Отправляем
    if isinstance(target, types.CallbackQuery):
        await target.answer("❌ Недостаточно звёзд", show_alert=True)
        return await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        return await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


# ============================================================================
# ДЕКОРАТОР ДЛЯ HANDLERS
# ============================================================================

def balance_required(min_stars: int = 0):
    """
    Декоратор для проверки баланса звёзд перед выполнением handler.
    
    Использование:
        @balance_required()  # Просто баланс > 0
        async def handler(message):
            ...
            
        @balance_required(min_stars=2000)  # Минимум 2,000 звёзд
        async def expensive_handler(message):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(target: Union[types.Message, types.CallbackQuery], *args, **kwargs):
            # Получаем user_id
            if isinstance(target, types.CallbackQuery):
                user_id = target.from_user.id
            else:
                user_id = target.from_user.id
            
            # Проверяем баланс
            can_proceed, stars_balance = await check_balance(user_id, min_stars)
            
            if not can_proceed:
                await send_no_stars_message(target, stars_balance, min_stars)
                return None
            
            # Баланс OK — выполняем handler
            return await func(target, *args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================================
# БЫСТРЫЕ ПРОВЕРКИ ДЛЯ INLINE ИСПОЛЬЗОВАНИЯ
# ============================================================================

async def ensure_balance(
    target: Union[types.Message, types.CallbackQuery],
    required: int = 0
) -> bool:
    """
    Проверить баланс звёзд и отправить сообщение если не хватает.
    Для использования внутри handler без декоратора.
    
    Использование:
        async def handler(message):
            if not await ensure_balance(message, required=500):
                return  # Сообщение уже отправлено
            
            # Продолжаем работу...
            
    Returns:
        True если баланс OK, False если отправлено сообщение о нехватке звёзд
    """
    if isinstance(target, types.CallbackQuery):
        user_id = target.from_user.id
    else:
        user_id = target.from_user.id
    
    can_proceed, stars_balance = await check_balance(user_id, required)
    
    if not can_proceed:
        await send_no_stars_message(target, stars_balance, required)
        return False
    
    return True


async def get_balance_status(user_id: int) -> dict:
    """
    Получить полный статус баланса звёзд пользователя.
    
    Returns:
        {
            'stars': int,
            'can_use': bool,
            'has_subscription': bool,
            'subscription_type': str or None,
            'subscription_remaining': int or None
        }
    """
    stars_balance = await db.get_available_stars(user_id)
    subscription = await db.get_subscription(user_id)
    
    has_sub = subscription and subscription.get('is_active')
    
    return {
        'stars': stars_balance,
        'can_use': stars_balance > 0,
        'has_subscription': has_sub,
        'subscription_type': subscription.get('type') if has_sub else None,
        'subscription_remaining': (
            subscription.get('stars_limit', 0) - subscription.get('stars_used', 0)
        ) if has_sub else None
    }
