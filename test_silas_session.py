#!/usr/bin/env python3
"""Тест функций сессий Silas"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(__file__))

async def test_functions():
    try:
        from database import postgres_db
        
        print("🔵 Тестирование функций сессий Silas...")
        print("=" * 50)
        
        # Тест 1: Проверка импорта
        print("\n1. Проверка импорта функций...")
        assert hasattr(postgres_db, 'start_session'), "❌ start_session не найдена"
        assert hasattr(postgres_db, 'end_session'), "❌ end_session не найдена"
        assert hasattr(postgres_db, 'get_mood_stats'), "❌ get_mood_stats не найдена"
        assert hasattr(postgres_db, 'set_mood'), "❌ set_mood не найдена"
        print("✅ Все функции найдены")
        
        # Тест 2: Проверка start_session
        print("\n2. Тест start_session...")
        try:
            # Инициализируем пул (если не инициализирован)
            try:
                await postgres_db.init_pool()
            except:
                pass
            
            test_uid = 999999999
            test_dur = 30
            sid = await postgres_db.start_session(test_uid, test_dur)
            print(f"✅ start_session работает: session_id = {sid}")
            
            # Тест 3: Проверка end_session
            print("\n3. Тест end_session...")
            await postgres_db.end_session(sid)
            print(f"✅ end_session работает")
            
        except Exception as e:
            print(f"❌ Ошибка при тестировании сессий: {e}")
            import traceback
            traceback.print_exc()
        
        # Тест 4: Проверка set_mood
        print("\n4. Тест set_mood...")
        try:
            await postgres_db.set_mood(test_uid, 'good')
            print("✅ set_mood работает")
        except Exception as e:
            print(f"❌ Ошибка set_mood: {e}")
            import traceback
            traceback.print_exc()
        
        # Тест 5: Проверка get_mood_stats
        print("\n5. Тест get_mood_stats...")
        try:
            stats = await postgres_db.get_mood_stats(test_uid)
            print(f"✅ get_mood_stats работает: {stats}")
        except Exception as e:
            print(f"❌ Ошибка get_mood_stats: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 50)
        print("✅ Тестирование завершено")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_functions())
