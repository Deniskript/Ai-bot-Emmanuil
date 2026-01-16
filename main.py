import asyncio
import logging
import sys
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from loader import bot, dp
from database import postgres_db  # PostgreSQL database
from handlers import start, admin, subscription, images, health, socials
from handlers import luca  # Автономный модуль Luca
from handlers import silas  # Автономный модуль Silas
from handlers import titus  # Автономный модуль Titus
from handlers import lifestyle  # Автономный модуль Lifestyle
from utils.magic_notifications import run_magic_horoscope_notifier
from config import ADMIN_IDS

logging.basicConfig(level=logging.INFO, stream=sys.stdout)


async def set_bot_commands():
    # Команды для всех пользователей
    user_commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="restart", description="🔄 Перезапустить бота"),
        BotCommand(command="help", description="❓ Помощь и поддержка"),
    ]
    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    
    # Команды для админов (включая /admin)
    admin_commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="restart", description="🔄 Перезапустить бота"),
        BotCommand(command="help", description="❓ Помощь и поддержка"),
        BotCommand(command="admin", description="👑 Админ-панель"),
    ]
    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            logging.warning(f"Не удалось установить команды для админа {admin_id}: {e}")


async def main():
    try:
        # Инициализация PostgreSQL
        print("🔵 Инициализация PostgreSQL...")
        await postgres_db.init_pool()
        await postgres_db.init_db()
        print("✅ PostgreSQL инициализирован")
        
        # Установка команд бота
        await set_bot_commands()
        
        # Подключение роутеров
        dp.include_router(images.router)  # Moved up for state priority
        dp.include_router(health.router)  # Health & Calories
        dp.include_router(socials.router)  # Соцсети (вирусный разбор + обложки)
        dp.include_router(lifestyle.router)  # Автономный модуль Lifestyle (режим дня, эзотерика)
        dp.include_router(admin.router)
        dp.include_router(subscription.router)
        dp.include_router(start.router)
        dp.include_router(luca.router)  # Автономный модуль Luca (Soul AI)
        dp.include_router(silas.router)
        dp.include_router(titus.router)
        
        # Фоновая отправка гороскопов
        asyncio.create_task(run_magic_horoscope_notifier(bot))
        
        await bot.delete_webhook(drop_pending_updates=True)
        print("🤖 Soul AI запущен с PostgreSQL!")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\n⚠️ Получен сигнал остановки...")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Graceful shutdown
        print("🔄 Закрытие соединений...")
        from utils.openrouter import close_client
        await close_client()
        await postgres_db.close_pool()  # Закрываем PostgreSQL pool
        await bot.session.close()
        print("✅ Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
