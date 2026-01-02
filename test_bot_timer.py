import asyncio
import sys
sys.path.insert(0, '/root/ai-bot')

from loader import bot

async def test():
    # Твой chat_id (замени на свой)
    chat_id = 5186134966
    
    msg = await bot.send_message(chat_id, "✍️ Тест (0 сек)")
    
    for i in range(1, 6):
        await asyncio.sleep(1)
        try:
            await msg.edit_text(f"✍️ Тест ({i} сек)")
            print(f"Обновлено: {i} сек")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    await msg.delete()
    await bot.send_message(chat_id, "✅ Тест завершён!")
    print("Готово!")

asyncio.run(test())
