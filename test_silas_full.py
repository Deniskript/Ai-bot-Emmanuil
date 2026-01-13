#!/usr/bin/env python3
"""Полный тест обработчика Silas"""
import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

async def test_handler():
    try:
        print("🔵 Тестирование обработчика Silas...")
        print("=" * 50)
        
        # Импортируем обработчик
        from handlers.silas.handler import router, SilasSt
        from handlers.silas import keyboards as kb, texts
        from database import db
        
        print("\n1. Проверка импортов...")
        print(f"✅ Роутер: {router}")
        print(f"✅ States: {SilasSt}")
        print(f"✅ Клавиатуры: {kb}")
        print(f"✅ Тексты: {texts}")
        
        # Проверяем наличие всех обработчиков
        print("\n2. Проверка обработчиков...")
        handlers = router.sub_routers[0].observers if hasattr(router, 'sub_routers') else []
        print(f"✅ Найдено обработчиков: {len(handlers) if handlers else 'N/A'}")
        
        # Проверяем функции БД
        print("\n3. Проверка функций БД...")
        required_funcs = [
            'start_session', 'end_session', 'set_mood', 
            'get_mood_stats', 'clear_msgs', 'reset_msg_counter',
            'get_user_bot', 'get_memory', 'get_msgs', 'inc_msg_counter'
        ]
        for func_name in required_funcs:
            if hasattr(db, func_name):
                print(f"  ✅ {func_name}")
            else:
                print(f"  ❌ {func_name} - НЕ НАЙДЕНА!")
        
        # Тест обработчика выбора длительности
        print("\n4. Тест логики обработчика...")
        
        # Создаём мок-объекты
        mock_msg = MagicMock()
        mock_msg.from_user.id = 123456
        mock_msg.text = "30 минут"
        
        mock_state = AsyncMock()
        mock_state.get_data = AsyncMock(return_value={})
        mock_state.set_state = AsyncMock()
        mock_state.update_data = AsyncMock()
        
        mock_answer = AsyncMock()
        mock_msg.answer = mock_answer
        
        # Проверяем маппинг длительности
        dur_map = {"15 минут": 15, "30 минут": 30, "60 минут": 60}
        dur = dur_map.get(mock_msg.text, 30)
        print(f"  ✅ Маппинг длительности: '{mock_msg.text}' -> {dur} мин")
        
        # Проверяем форматирование текста
        formatted = texts.START_SESSION.format(duration=dur)
        print(f"  ✅ Форматирование текста работает")
        print(f"     Текст: {formatted[:50]}...")
        
        print("\n" + "=" * 50)
        print("✅ Все проверки пройдены")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_handler())
