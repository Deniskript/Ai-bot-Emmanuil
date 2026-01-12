"""
Сообщения об ошибках для пользователей
"""
from database import db


async def check_tokens_and_notify(user_id: int, required_tokens: int, message) -> bool:
    """
    Проверяет достаточно ли токенов и отправляет красивое сообщение если нет
    
    Returns:
        True - токенов достаточно, можно продолжать
        False - токенов недостаточно, сообщение отправлено
    """
    available = await db.get_available_tokens(user_id)
    
    # Если баланс отрицательный - блокируем
    if available < 0:
        error_msg = await get_no_tokens_message(user_id)
        await message.answer(error_msg, parse_mode="HTML")
        return False
    
    # Если токенов не хватает для операции
    if available < required_tokens:
        error_msg = await get_insufficient_tokens_message(user_id, required_tokens, available)
        await message.answer(error_msg, parse_mode="HTML")
        return False
    
    return True


async def get_no_tokens_message(user_id: int) -> str:
    """
    Возвращает красивое сообщение об отсутствии токенов
    - Если есть подписка (платная) -> предложить докупить токены
    - Если подписка подарочная/админская -> предложить оформить подписку
    - Если нет подписки -> предложить оформить подписку
    """
    has_sub = await db.has_active_subscription(user_id)
    
    if has_sub:
        # Проверяем, подарочная ли подписка
        is_gift = await db.is_gift_subscription(user_id)
        
        if is_gift:
            # Подарочная подписка закончилась
            return (
                "⚠️ <b>Токены закончились</b>\n\n"
                "💎 У вас была <b>подарочная подписка</b>, но токены израсходованы.\n\n"
                "🎯 <b>Что делать?</b>\n"
                "• Оформите <b>платную подписку</b> для безлимитного доступа\n"
                "• Или докупите токены в разделе 💠 Подписка\n\n"
                "💡 С подпиской вы получаете:\n"
                "✨ 400,000 - 900,000 токенов в месяц\n"
                "🎁 Доступ ко всем функциям\n"
                "⚡️ Приоритетная поддержка"
            )
        else:
            # Платная подписка, но токены закончились
            sub = await db.get_subscription(user_id)
            sub_name = "Mini" if sub['type'] == 'mini' else "Standard"
            
            return (
                "⚠️ <b>Токены закончились</b>\n\n"
                f"💎 Подписка: <b>{sub_name}</b>\n"
                f"📊 Месячный лимит исчерпан\n\n"
                "🎯 <b>Что делать?</b>\n"
                "• <b>Докупите токены</b> в разделе 💠 Подписка → 💰 Купить токены\n"
                "• Или <b>обновите подписку</b> на более высокий тариф\n"
                "• Токены обновятся автоматически в начале следующего месяца\n\n"
                "💡 <b>Цены на токены:</b>\n"
                "• 100,000 токенов — 149₽\n"
                "• 200,000 токенов — 249₽\n"
                "• 500,000 токенов — 499₽"
            )
    else:
        # Нет подписки, бонусные токены закончились
        return (
            "⚠️ <b>Токены закончились</b>\n\n"
            "🎁 Бонусные токены израсходованы.\n\n"
            "🎯 <b>Оформите подписку для продолжения:</b>\n\n"
            "🔵 <b>Mini</b> — 490₽/мес\n"
            "• 400,000 токенов\n"
            "• Claude Sonnet 4\n"
            "• Все функции бота\n\n"
            "🟣 <b>Standard</b> — 990₽/мес\n"
            "• 900,000 токенов\n"
            "• Claude Opus 4\n"
            "• Приоритетная поддержка\n\n"
            "💡 Или докупите токены без подписки в разделе 💠 Подписка"
        )


async def get_insufficient_tokens_message(user_id: int, required: int, available: int) -> str:
    """
    Сообщение когда токенов не хватает для операции
    """
    deficit = required - available
    has_sub = await db.has_active_subscription(user_id)
    
    if has_sub:
        return (
            f"⚠️ <b>Недостаточно токенов</b>\n\n"
            f"Требуется: <b>{required:,}</b> токенов\n"
            f"Доступно: <b>{available:,}</b> токенов\n"
            f"Не хватает: <b>{deficit:,}</b> токенов\n\n"
            f"💡 Докупите токены в разделе 💠 Подписка"
        ).replace(",", " ")
    else:
        return (
            f"⚠️ <b>Недостаточно токенов</b>\n\n"
            f"Требуется: <b>{required:,}</b> токенов\n"
            f"Доступно: <b>{available:,}</b> токенов\n"
            f"Не хватает: <b>{deficit:,}</b> токенов\n\n"
            f"💡 Оформите подписку в разделе 💠 Подписка"
        ).replace(",", " ")
