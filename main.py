import asyncio
import logging
import sys
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from loader import bot, dp
from database.db import init_db, init_subscription_tables
from database import db as database
from handlers import start, emmanuil, luca, silas, titus, admin, subscription
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
        # Инициализация БД
        await init_db()
        await database.init_texts_tables()
        await init_subscription_tables()
        await database.init_course_memory_table()
        
        # Установка команд бота
        await set_bot_commands()
        
        # Подключение роутеров
        dp.include_router(admin.router)
        dp.include_router(subscription.router)
        dp.include_router(start.router)
        dp.include_router(emmanuil.router)
        dp.include_router(luca.router)
        dp.include_router(silas.router)
        dp.include_router(titus.router)
        
        await bot.delete_webhook(drop_pending_updates=True)
        print("🤖 Soul AI запущен!")
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
        await bot.session.close()
        print("✅ Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
