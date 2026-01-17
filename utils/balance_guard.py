"""
Централизованная система проверки баланса токенов.
Единое место для проверки и красивых сообщений о нехватке токенов.
"""

from functools import wraps
from typing import Optional, Union
from aiogram import types, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import db


# ============================================================================
# КРАСИВОЕ СООБЩЕНИЕ О НЕХВАТКЕ ТОКЕНОВ
# ============================================================================

NO_TOKENS_MESSAGE = """
😔 <b>Токены закончились</b>

У тебя недостаточно токенов для этого действия.

┌─────────────────────────┐
│  💎 Твой баланс: <b>{balance:,}</b>   │
│  📊 Нужно: <b>{required:,}</b>        │
└─────────────────────────┘

<b>Что делать?</b>
• Оформи подписку — получишь токены каждый месяц
• Пригласи друзей — получишь бонус за каждого

✨ <i>С подпиской ты сможешь пользоваться всеми возможностями Soul без ограничений!</i>
"""

NO_TOKENS_MESSAGE_SIMPLE = """
😔 <b>Токены закончились</b>

💎 Твой баланс: <b>{balance:,}</b>

Оформи подписку чтобы продолжить пользоваться Soul ✨
"""


def get_no_tokens_keyboard(has_subscription: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для сообщения о нехватке токенов"""
    buttons = []
    
    if not has_subscription:
        buttons.append([
            InlineKeyboardButton(
                text="⭐ Оформить подписку",
                callback_data="subscription_plans"
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="💎 Докупить токены",
                callback_data="buy_tokens"
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
    Проверить достаточно ли токенов.
    
    Args:
        user_id: ID пользователя
        required: Минимально необходимое количество токенов (0 = просто > 0)
        
    Returns:
        (can_proceed, current_balance)
        - can_proceed: True если можно продолжить
        - current_balance: Текущий баланс
    """
    balance = await db.get_available_tokens(user_id)
    
    # Если баланс отрицательный или 0 — нельзя
    if balance <= 0:
        return False, balance
    
    # Если указан required и баланс меньше — нельзя
    if required > 0 and balance < required:
        return False, balance
    
    return True, balance


async def send_no_tokens_message(
    target: Union[types.Message, types.CallbackQuery],
    balance: int,
    required: int = 0,
    bot: Bot = None
) -> types.Message:
    """
    Отправить красивое сообщение о нехватке токенов.
    
    Args:
        target: Message или CallbackQuery
        balance: Текущий баланс
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
            balance=max(0, balance),
            required=required
        )
    else:
        text = NO_TOKENS_MESSAGE_SIMPLE.format(
            balance=max(0, balance)
        )
    
    keyboard = get_no_tokens_keyboard(has_subscription)
    
    # Отправляем
    if isinstance(target, types.CallbackQuery):
        await target.answer("❌ Недостаточно токенов", show_alert=True)
        return await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        return await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


# ============================================================================
# ДЕКОРАТОР ДЛЯ HANDLERS
# ============================================================================

def balance_required(min_tokens: int = 0):
    """
    Декоратор для проверки баланса перед выполнением handler.
    
    Использование:
        @balance_required()  # Просто баланс > 0
        async def handler(message):
            ...
            
        @balance_required(min_tokens=200000)  # Минимум 200K токенов
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
            can_proceed, balance = await check_balance(user_id, min_tokens)
            
            if not can_proceed:
                await send_no_tokens_message(target, balance, min_tokens)
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
    Проверить баланс и отправить сообщение если не хватает.
    Для использования внутри handler без декоратора.
    
    Использование:
        async def handler(message):
            if not await ensure_balance(message, required=50000):
                return  # Сообщение уже отправлено
            
            # Продолжаем работу...
            
    Returns:
        True если баланс OK, False если отправлено сообщение о нехватке
    """
    if isinstance(target, types.CallbackQuery):
        user_id = target.from_user.id
    else:
        user_id = target.from_user.id
    
    can_proceed, balance = await check_balance(user_id, required)
    
    if not can_proceed:
        await send_no_tokens_message(target, balance, required)
        return False
    
    return True


async def get_balance_status(user_id: int) -> dict:
    """
    Получить полный статус баланса пользователя.
    
    Returns:
        {
            'balance': int,
            'can_use': bool,
            'has_subscription': bool,
            'subscription_type': str or None,
            'subscription_remaining': int or None
        }
    """
    balance = await db.get_available_tokens(user_id)
    subscription = await db.get_subscription(user_id)
    
    has_sub = subscription and subscription.get('is_active')
    
    return {
        'balance': balance,
        'can_use': balance > 0,
        'has_subscription': has_sub,
        'subscription_type': subscription.get('type') if has_sub else None,
        'subscription_remaining': (
            subscription.get('tokens_limit', 0) - subscription.get('tokens_used', 0)
        ) if has_sub else None
    }
