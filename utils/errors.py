"""
Сообщения об ошибках для пользователей
"""
from database import postgres_db as db


async def check_stars_and_notify(user_id: int, required_stars: int, message) -> bool:
    """
    Проверяет достаточно ли звёзд и отправляет красивое сообщение если нет
    
    Returns:
        True - звёзд достаточно, можно продолжать
        False - звёзд недостаточно, сообщение отправлено
    """
    available = await db.get_available_stars(user_id)
    
    # Если баланс отрицательный - блокируем
    if available < 0:
        error_msg = await get_no_stars_message(user_id)
        await message.answer(error_msg, parse_mode="HTML")
        return False
    
    # Если звёзд не хватает для операции
    if available < required_stars:
        error_msg = await get_insufficient_stars_message(user_id, required_stars, available)
        await message.answer(error_msg, parse_mode="HTML")
        return False
    
    return True


async def get_no_stars_message(user_id: int) -> str:
    """
    Возвращает красивое сообщение об отсутствии звёзд
    - Если есть подписка (платная) -> предложить докупить звёзды
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
                "⚠️ <b>Звёзды закончились</b>\n\n"
                "⭐ У вас была <b>подарочная подписка</b>, но звёзды израсходованы.\n\n"
                "🎯 <b>Что делать?</b>\n"
                "• Оформите <b>платную подписку</b> для безлимитного доступа\n"
                "• Или докупите звёзды в разделе 💠 Подписка\n\n"
                "💡 С подпиской вы получаете:\n"
                "✨ 4,000 - 9,000 ⭐ в месяц\n"
                "🎁 Доступ ко всем функциям\n"
                "⚡️ Приоритетная поддержка"
            )
        else:
            # Платная подписка, но токены закончились
            sub = await db.get_subscription(user_id)
            sub_name = "Mini" if sub['type'] == 'mini' else "Standard"
            
            return (
                "⚠️ <b>Звёзды закончились</b>\n\n"
                f"⭐ Подписка: <b>{sub_name}</b>\n"
                f"📊 Месячный лимит исчерпан\n\n"
                "🎯 <b>Что делать?</b>\n"
                "• <b>Докупите звёзды</b> в разделе 💠 Подписка → 💰 Купить звёзды\n"
                "• Или <b>обновите подписку</b> на более высокий тариф\n"
                "• Звёзды обновятся автоматически в начале следующего месяца\n\n"
                "💡 <b>Цены на звёзды:</b>\n"
                "• 1,000 ⭐ — 149₽\n"
                "• 2,000 ⭐ — 249₽\n"
                "• 5,000 ⭐ — 499₽"
            )
    else:
        # Нет подписки, бонусные звёзды закончились
        return (
            "⚠️ <b>Звёзды закончились</b>\n\n"
            "🎁 Бонусные звёзды израсходованы.\n\n"
            "🎯 <b>Оформите подписку для продолжения:</b>\n\n"
            "🔵 <b>Mini</b> — 490₽/мес\n"
            "• 4,000 ⭐\n"
            "• Claude Sonnet 4\n"
            "• Все функции бота\n\n"
            "🟣 <b>Standard</b> — 990₽/мес\n"
            "• 9,000 ⭐\n"
            "• Claude Opus 4\n"
            "• Приоритетная поддержка\n\n"
            "💡 Или докупите звёзды без подписки в разделе 💠 Подписка"
        )


async def get_insufficient_stars_message(user_id: int, required: int, available: int) -> str:
    """
    Сообщение когда звёзд не хватает для операции
    """
    deficit = required - available
    has_sub = await db.has_active_subscription(user_id)
    
    if has_sub:
        return (
            f"⚠️ <b>Недостаточно звёзд</b>\n\n"
            f"Требуется: <b>{required:,}</b> ⭐\n"
            f"Доступно: <b>{available:,}</b> ⭐\n"
            f"Не хватает: <b>{deficit:,}</b> ⭐\n\n"
            f"💡 Докупите звёзды в разделе 💠 Подписка"
        ).replace(",", " ")
    else:
        return (
            f"⚠️ <b>Недостаточно звёзд</b>\n\n"
            f"Требуется: <b>{required:,}</b> ⭐\n"
            f"Доступно: <b>{available:,}</b> ⭐\n"
            f"Не хватает: <b>{deficit:,}</b> ⭐\n\n"
            f"💡 Оформите подписку в разделе 💠 Подписка"
        ).replace(",", " ")
