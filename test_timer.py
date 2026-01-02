import asyncio

async def test():
    print("Старт теста")
    
    async def timer():
        sec = 0
        while True:
            await asyncio.sleep(1)
            sec += 1
            print(f"Таймер: {sec} сек")
    
    async def long_task():
        print("Задача началась...")
        await asyncio.sleep(5)
        print("Задача завершена!")
        return "Результат"
    
    timer_task = asyncio.create_task(timer())
    result = await long_task()
    timer_task.cancel()
    
    print(f"Получен: {result}")

asyncio.run(test())
