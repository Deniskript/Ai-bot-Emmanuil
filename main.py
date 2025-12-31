import asyncio
import logging
import sys
from loader import bot, dp
from database.db import init_db
from database import db as database
from handlers import start, emmanuil, luca, silas, titus, admin

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    await init_db()
    await database.init_texts_tables()
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(emmanuil.router)
    dp.include_router(luca.router)
    dp.include_router(silas.router)
    dp.include_router(titus.router)
    await bot.delete_webhook(drop_pending_updates=True)
    print("🤖 Emmanuil AI запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
