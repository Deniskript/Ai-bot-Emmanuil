"""
Admin Panel Handler - Opens WebApp Admin Panel
Команда /admin открывает веб-админку через Telegram Mini App
"""

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command

from config import ADMIN_IDS

router = Router()


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_IDS


@router.message(Command("admin"))
async def admin_cmd(msg: Message):
    """
    /admin — открывает веб-админку Soul AI
    Доступно только администраторам из ADMIN_IDS
    """
    if not is_admin(msg.from_user.id):
        return
    
    # Создаём кнопку для открытия WebApp админки
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="👑 Открыть админ-панель",
                web_app=WebAppInfo(url="https://soul-bot.ru/admin/")
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Быстрая статистика",
                callback_data="admin:quick_stats"
            )
        ]
    ])
    
    await msg.answer(
        "👑 <b>Админ-панель Soul AI</b>\n\n"
        "Нажмите кнопку ниже для открытия полной админ-панели.\n\n"
        "📱 Админка откроется в Telegram Mini App с полным функционалом:\n"
        "• Статистика и графики\n"
        "• Управление пользователями\n"
        "• Подписки и токены\n"
        "• Рассылка\n"
        "• Память ботов\n"
        "• Финансы\n"
        "• Настройки",
        reply_markup=kb
    )


@router.callback_query(F.data == "admin:quick_stats")
async def quick_stats(cb):
    """Quick stats without opening WebApp"""
    if not is_admin(cb.from_user.id):
        return
    
    from database import postgres_db as db
    import psutil
    
    # Get stats
    total_users = await db.count_users()
    blocked = await db.get_blocked_count()
    mini_count = await db.count_subscribers_by_type('mini')
    standard_count = await db.count_subscribers_by_type('standard')
    premium_count = await db.count_subscribers_by_type('premium')
    stars_used = await db.get_total_stars_used()
    
    # Server load
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    
    # Format numbers
    def fmt(n):
        return f"{n:,}".replace(",", " ")
    
    text = (
        f"📊 <b>Быстрая статистика</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"├ Всего: {fmt(total_users)}\n"
        f"└ Заблокировано: {blocked}\n\n"
        f"⭐ <b>Подписки:</b>\n"
        f"├ 💎 Mini: {mini_count}\n"
        f"├ 👑 Standard: {standard_count}\n"
        f"├ ✨ Premium: {premium_count}\n"
        f"└ Всего: {mini_count + standard_count + premium_count}\n\n"
        f"📈 <b>Использование:</b>\n"
        f"└ Звёзд использовано: {fmt(stars_used)}\n\n"
        f"💻 <b>Сервер:</b>\n"
        f"├ CPU: {cpu}%\n"
        f"└ RAM: {mem.percent}%"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="👑 Полная админка",
                web_app=WebAppInfo(url="https://soul-bot.ru/admin/")
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="admin:quick_stats"
            )
        ]
    ])
    
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()
