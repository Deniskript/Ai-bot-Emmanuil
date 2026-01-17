#!/usr/bin/env python3
"""
Скрипт очистки базы данных перед переходом на звёзды.
Удаляет ВСЕ данные пользователей, сохраняя структуру таблиц.

⚠️ ВНИМАНИЕ: Это действие НЕОБРАТИМО!
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию в path для импорта .env
sys.path.insert(0, str(Path(__file__).parent.parent))

# Загружаем .env
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ ОШИБКА: DATABASE_URL не найден в .env")
    sys.exit(1)


async def clean_database(auto_confirm=False):
    """Очистить все пользовательские данные из базы"""
    
    print("=" * 60)
    print("🗑️  ОЧИСТКА БАЗЫ ДАННЫХ")
    print("=" * 60)
    print(f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔗 База: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'aibot_db'}")
    print()
    
    # Последняя проверка (если не автоматическое подтверждение)
    if not auto_confirm:
        confirm = input("⚠️  Вы уверены? Это удалит ВСЕ данные! (yes/no): ")
        if confirm.lower() != 'yes':
            print("❌ Отменено пользователем")
            return
    
    print("\n🚀 Начинаю очистку...")
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        sys.exit(1)
    
    try:
        # Показать текущее состояние ДО очистки
        print("\n📊 СОСТОЯНИЕ ДО ОЧИСТКИ:")
        stats_before = await conn.fetch("""
            SELECT 'users' as table_name, COUNT(*) as count FROM users
            UNION ALL SELECT 'subscriptions', COUNT(*) FROM subscriptions
            UNION ALL SELECT 'transactions', COUNT(*) FROM transactions
            UNION ALL SELECT 'messages', COUNT(*) FROM messages
            UNION ALL SELECT 'star_usage', COUNT(*) FROM star_usage
            UNION ALL SELECT 'conversations', COUNT(*) FROM conversations
            UNION ALL SELECT 'bot_memory', COUNT(*) FROM bot_memory
            ORDER BY count DESC
        """)
        for row in stats_before:
            print(f"  {row['table_name']:20} | {row['count']:>6} записей")
        
        # Список ВСЕХ таблиц для очистки (43 таблицы)
        tables = [
            # Основные пользовательские данные
            'messages',                      # Сообщения диалогов
            'conversations',                 # Диалоги
            'bot_memory',                    # Долгосрочная память
            'star_usage',                    # История звёзд
            'referrals',                     # Рефералы
            'transactions',                  # Транзакции
            'subscriptions',                 # Подписки
            'users',                         # ПОЛЬЗОВАТЕЛИ (последним!)
            
            # Курсы и обучение
            'course_memory',
            'courses',
            'video_notes',
            
            # Настройки
            'user_bots',
            'user_profile',
            'user_image_settings',
            
            # Здоровье
            'calories_log',
            'user_nutrition_goals',
            
            # Lifestyle
            'user_goals',
            'goal_checkins',
            'user_streaks',
            'user_budgets',
            'user_routines',
            'routine_checkins',
            'mood_logs',
            'mood_stats',
            'meditation_logs',
            
            # Silas (пары)
            'pair_sessions',
            
            # Magic (эзотерика)
            'magic_tarot_logs',
            'magic_divination_logs',
            'magic_horoscope_logs',
            'magic_horoscope_profiles',
            'magic_numerology_logs',
            'magic_numerology_profiles',
            'magic_rituals_logs',
            
            # Системные (не критично, но можно очистить)
            'sessions',
            'settings',
            'texts',
            'bot_texts',
            'bot_cfg',
            'bot_settings',
            'bot_buttons',
            'bot_media',
            'server_metrics',
        ]
        
        print(f"\n🔄 Очистка {len(tables)} таблиц...\n")
        
        cleaned = 0
        skipped = 0
        
        for table in tables:
            try:
                # Проверить существование таблицы
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
                    table
                )
                
                if not exists:
                    print(f"  ⏭️  {table:35} | не существует")
                    skipped += 1
                    continue
                
                # Очистить таблицу (CASCADE автоматически очистит зависимые)
                await conn.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
                print(f"  ✅ {table:35} | очищена")
                cleaned += 1
                
            except Exception as e:
                print(f"  ❌ {table:35} | ошибка: {e}")
        
        # Показать состояние ПОСЛЕ очистки
        print("\n📊 СОСТОЯНИЕ ПОСЛЕ ОЧИСТКИ:")
        stats_after = await conn.fetch("""
            SELECT 'users' as table_name, COUNT(*) as count FROM users
            UNION ALL SELECT 'subscriptions', COUNT(*) FROM subscriptions
            UNION ALL SELECT 'transactions', COUNT(*) FROM transactions
            UNION ALL SELECT 'messages', COUNT(*) FROM messages
            UNION ALL SELECT 'star_usage', COUNT(*) FROM star_usage
            UNION ALL SELECT 'conversations', COUNT(*) FROM conversations
            UNION ALL SELECT 'bot_memory', COUNT(*) FROM bot_memory
            ORDER BY count DESC
        """)
        for row in stats_after:
            print(f"  {row['table_name']:20} | {row['count']:>6} записей")
        
        print("\n" + "=" * 60)
        print(f"✅ ГОТОВО!")
        print(f"   Очищено: {cleaned} таблиц")
        print(f"   Пропущено: {skipped} таблиц")
        print(f"   Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Очистка базы данных")
    parser.add_argument('--confirm', action='store_true', help='Автоматически подтвердить очистку')
    args = parser.parse_args()
    
    # Если флаг --confirm, пропускаем интерактивное подтверждение
    if args.confirm:
        print("✅ Автоматическое подтверждение (--confirm)\n")
    
    try:
        asyncio.run(clean_database(auto_confirm=args.confirm))
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем (Ctrl+C)")
        sys.exit(1)
