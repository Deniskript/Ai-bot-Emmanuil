#!/usr/bin/env python3
"""
Миграция данных из SQLite в PostgreSQL
Переносит все важные данные с сохранением целостности
"""

import asyncio
import aiosqlite
import os
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional


def parse_datetime(dt_string: Optional[str]):
    """Конвертирует строку datetime в объект datetime"""
    if not dt_string:
        return None
    try:
        # Пробуем несколько форматов
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d']:
            try:
                return datetime.strptime(dt_string, fmt)
            except ValueError:
                continue
        return None
    except:
        return None

# Загружаем .env
load_dotenv()

# Импортируем модули
from database import postgres_db

# Путь к SQLite базе
SQLITE_DB = "bot.db"


class MigrationStats:
    """Статистика миграции"""
    def __init__(self):
        self.tables = {}
        self.errors = []
    
    def add_success(self, table: str, count: int):
        self.tables[table] = {"success": count, "errors": 0}
    
    def add_error(self, table: str, error: str):
        if table not in self.tables:
            self.tables[table] = {"success": 0, "errors": 0}
        self.tables[table]["errors"] += 1
        self.errors.append(f"{table}: {error}")
    
    def print_report(self):
        print("\n" + "=" * 60)
        print("📊 ОТЧЁТ О МИГРАЦИИ")
        print("=" * 60)
        
        total_success = 0
        total_errors = 0
        
        for table, stats in sorted(self.tables.items()):
            success = stats["success"]
            errors = stats["errors"]
            total_success += success
            total_errors += errors
            
            status = "✅" if errors == 0 else "⚠️"
            print(f"{status} {table:30} {success:6} записей", end="")
            if errors > 0:
                print(f" ({errors} ошибок)", end="")
            print()
        
        print("-" * 60)
        print(f"Всего успешно:  {total_success}")
        print(f"Всего ошибок:   {total_errors}")
        
        if self.errors:
            print("\n❌ ОШИБКИ:")
            for error in self.errors[:10]:
                print(f"   - {error}")
            if len(self.errors) > 10:
                print(f"   ... и ещё {len(self.errors) - 10} ошибок")
        
        print("=" * 60)


stats = MigrationStats()


async def migrate_users():
    """Миграция пользователей"""
    print("\n📦 Миграция: users...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM users")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO users (user_id, username, first_name, tokens, total_used, 
                                          total_requests, is_blocked, agreement, created_at, referred_by)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (user_id) DO UPDATE SET
                            username = $2, first_name = $3, tokens = $4, total_used = $5,
                            total_requests = $6, is_blocked = $7, agreement = $8, referred_by = $10
                        """,
                        data['user_id'], data.get('username'), data.get('first_name'),
                        data.get('tokens', 5000), data.get('total_used', 0),
                        data.get('total_requests', 0), data.get('is_blocked', 0),
                        data.get('agreement', 0), parse_datetime(data.get('created_at')), data.get('referred_by')
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('users', str(e))
        
        stats.add_success('users', count)
        print(f"✅ Перенесено: {count} пользователей")


async def migrate_user_bots():
    """Миграция настроек ботов"""
    print("\n📦 Миграция: user_bots...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM user_bots")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO user_bots (user_id, bot, character, mood, custom_mood, msg_counter, voice_gender)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (user_id, bot) DO UPDATE SET
                            character = $3, mood = $4, custom_mood = $5, msg_counter = $6, voice_gender = $7
                        """,
                        data['user_id'], data['bot'], data.get('character', 'душевный'),
                        data.get('mood'), data.get('custom_mood'), data.get('msg_counter', 0),
                        data.get('voice_gender')
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('user_bots', str(e))
        
        stats.add_success('user_bots', count)
        print(f"✅ Перенесено: {count} настроек ботов")


async def migrate_bot_memory():
    """🧠 Миграция долгой памяти ботов (КРИТИЧНО!)"""
    print("\n📦 Миграция: bot_memory (🧠 ДОЛГАЯ ПАМЯТЬ БОТОВ!)...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM bot_memory")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO bot_memory (user_id, bot, facts)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id, bot) DO UPDATE SET facts = $3
                        """,
                        data['user_id'], data['bot'], data.get('facts', '[]')
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('bot_memory', str(e))
        
        stats.add_success('bot_memory', count)
        print(f"✅ Перенесено: {count} записей памяти ботов")


async def migrate_conversations():
    """Миграция диалогов"""
    print("\n📦 Миграция: conversations...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM conversations")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        # Маппинг старых ID на новые
        id_mapping = {}
        
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    new_id = await pg_conn.fetchval(
                        """
                        INSERT INTO conversations (user_id, bot, created_at, updated_at)
                        VALUES ($1, $2, $3, $4)
                        RETURNING id
                        """,
                        data['user_id'], data['bot'],
                        parse_datetime(data.get('created_at')), parse_datetime(data.get('updated_at'))
                    )
                    id_mapping[data['id']] = new_id
                    count += 1
                except Exception as e:
                    stats.add_error('conversations', str(e))
        
        stats.add_success('conversations', count)
        print(f"✅ Перенесено: {count} диалогов")
        
        return id_mapping


async def migrate_messages(conv_id_mapping):
    """Миграция сообщений"""
    print("\n📦 Миграция: messages...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM messages ORDER BY id")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                old_conv_id = data['conversation_id']
                
                # Пропускаем если conversation_id не найден
                if old_conv_id not in conv_id_mapping:
                    continue
                
                new_conv_id = conv_id_mapping[old_conv_id]
                
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO messages (conversation_id, role, content, model, timestamp)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        new_conv_id, data['role'], data['content'],
                        data.get('model'), parse_datetime(data.get('timestamp'))
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('messages', str(e))
        
        stats.add_success('messages', count)
        print(f"✅ Перенесено: {count} сообщений")


async def migrate_subscriptions():
    """Миграция подписок"""
    print("\n📦 Миграция: subscriptions...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM subscriptions")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO subscriptions (user_id, type, tokens_limit, tokens_used, 
                                                  started_at, expires_at, is_active)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (user_id) DO UPDATE SET
                            type = $2, tokens_limit = $3, tokens_used = $4,
                            started_at = $5, expires_at = $6, is_active = $7
                        """,
                        data['user_id'], data.get('type'), data.get('tokens_limit', 0),
                        data.get('tokens_used', 0), parse_datetime(data.get('started_at')),
                        parse_datetime(data.get('expires_at')), data.get('is_active', 0)
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('subscriptions', str(e))
        
        stats.add_success('subscriptions', count)
        print(f"✅ Перенесено: {count} подписок")


async def migrate_token_usage():
    """Миграция использования токенов"""
    print("\n📦 Миграция: token_usage...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM token_usage ORDER BY id")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO token_usage (user_id, tokens_used, created_at, bot_name)
                        VALUES ($1, $2, $3, $4)
                        """,
                        data['user_id'], data.get('tokens_used', 0),
                        parse_datetime(data.get('created_at')), data.get('bot_name', 'unknown')
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('token_usage', str(e))
        
        stats.add_success('token_usage', count)
        print(f"✅ Перенесено: {count} записей использования токенов")


async def migrate_referrals():
    """Миграция рефералов"""
    print("\n📦 Миграция: referrals...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM referrals")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO referrals (referrer_id, referred_id, tokens_earned, 
                                              subscription_type, created_at)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (referred_id) DO NOTHING
                        """,
                        data['referrer_id'], data['referred_id'], data.get('tokens_earned', 0),
                        data.get('subscription_type'), parse_datetime(data.get('created_at'))
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('referrals', str(e))
        
        stats.add_success('referrals', count)
        print(f"✅ Перенесено: {count} рефералов")


async def migrate_courses():
    """Миграция курсов"""
    print("\n📦 Миграция: courses...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM courses")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO courses (user_id, name, total, current, done, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        data['user_id'], data.get('name'), data.get('total', 0),
                        data.get('current', 1), data.get('done', 0), parse_datetime(data.get('created_at'))
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('courses', str(e))
        
        stats.add_success('courses', count)
        print(f"✅ Перенесено: {count} курсов")


async def migrate_goals():
    """Миграция целей"""
    print("\n📦 Миграция: user_goals...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM user_goals")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        id_mapping = {}
        
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    new_id = await pg_conn.fetchval(
                        """
                        INSERT INTO user_goals (user_id, title, description, frequency, 
                                               target_count, period_days, reminder_time, 
                                               is_active, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        RETURNING id
                        """,
                        data['user_id'], data.get('title'), data.get('description'),
                        data.get('frequency'), data.get('target_count', 1),
                        data.get('period_days', 7), data.get('reminder_time'),
                        data.get('is_active', 1), parse_datetime(data.get('created_at'))
                    )
                    id_mapping[data['id']] = new_id
                    count += 1
                except Exception as e:
                    stats.add_error('user_goals', str(e))
        
        stats.add_success('user_goals', count)
        print(f"✅ Перенесено: {count} целей")
        
        return id_mapping


async def migrate_goal_checkins(goal_id_mapping):
    """Миграция отметок целей"""
    print("\n📦 Миграция: goal_checkins...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM goal_checkins")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                old_goal_id = data['goal_id']
                
                if old_goal_id not in goal_id_mapping:
                    continue
                
                new_goal_id = goal_id_mapping[old_goal_id]
                
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO goal_checkins (goal_id, user_id, date, is_done, note, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        new_goal_id, data['user_id'], data.get('date'),
                        data.get('is_done', 1), data.get('note'), parse_datetime(data.get('created_at'))
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('goal_checkins', str(e))
        
        stats.add_success('goal_checkins', count)
        print(f"✅ Перенесено: {count} отметок целей")


async def migrate_user_streaks(goal_id_mapping):
    """Миграция серий целей"""
    print("\n📦 Миграция: user_streaks...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM user_streaks")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                old_goal_id = data['goal_id']
                
                if old_goal_id not in goal_id_mapping:
                    continue
                
                new_goal_id = goal_id_mapping[old_goal_id]
                
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO user_streaks (user_id, goal_id, current_streak, 
                                                 best_streak, last_checkin)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (user_id, goal_id) DO UPDATE SET
                            current_streak = $3, best_streak = $4, last_checkin = $5
                        """,
                        data['user_id'], new_goal_id, data.get('current_streak', 0),
                        data.get('best_streak', 0), data.get('last_checkin')
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('user_streaks', str(e))
        
        stats.add_success('user_streaks', count)
        print(f"✅ Перенесено: {count} серий целей")


async def migrate_routines():
    """Миграция рутин"""
    print("\n📦 Миграция: user_routines...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM user_routines")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO user_routines (user_id, routine_type, items, 
                                                  reminder_time, is_active, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (user_id, routine_type) DO UPDATE SET
                            items = $3, reminder_time = $4, is_active = $5
                        """,
                        data['user_id'], data.get('routine_type'), data.get('items'),
                        data.get('reminder_time'), data.get('is_active', 1),
                        parse_datetime(data.get('created_at'))
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('user_routines', str(e))
        
        stats.add_success('user_routines', count)
        print(f"✅ Перенесено: {count} рутин")


async def migrate_routine_checkins():
    """Миграция отметок рутин"""
    print("\n📦 Миграция: routine_checkins...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM routine_checkins")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO routine_checkins (user_id, routine_type, date, completed_items,
                                                     total_items, completion_percent, reflection, 
                                                     mood, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        """,
                        data['user_id'], data.get('routine_type'), data.get('date'),
                        data.get('completed_items'), data.get('total_items'),
                        data.get('completion_percent'), data.get('reflection'),
                        data.get('mood'), parse_datetime(data.get('created_at'))
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('routine_checkins', str(e))
        
        stats.add_success('routine_checkins', count)
        print(f"✅ Перенесено: {count} отметок рутин")


async def migrate_nutrition():
    """Миграция питания"""
    print("\n📦 Миграция: calories_log...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM calories_log")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO calories_log (user_id, date, time, food_name, portion,
                                                 calories, protein, fat, carbs, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                        data['user_id'], data.get('date'), data.get('time'),
                        data.get('food_name'), data.get('portion'), data.get('calories', 0),
                        data.get('protein', 0), data.get('fat', 0), data.get('carbs', 0),
                        parse_datetime(data.get('created_at'))
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('calories_log', str(e))
        
        stats.add_success('calories_log', count)
        print(f"✅ Перенесено: {count} записей питания")


async def migrate_nutrition_goals():
    """Миграция целей по питанию"""
    print("\n📦 Миграция: user_nutrition_goals...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM user_nutrition_goals")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO user_nutrition_goals (user_id, goal, daily_calories, 
                                                         daily_protein, daily_fat, daily_carbs,
                                                         weight, height, age, gender, activity, 
                                                         updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        ON CONFLICT (user_id) DO UPDATE SET
                            goal = $2, daily_calories = $3, daily_protein = $4,
                            daily_fat = $5, daily_carbs = $6, weight = $7, height = $8,
                            age = $9, gender = $10, activity = $11, updated_at = $12
                        """,
                        data['user_id'], data.get('goal'), data.get('daily_calories', 2000),
                        data.get('daily_protein', 80), data.get('daily_fat', 60),
                        data.get('daily_carbs', 200), data.get('weight'), data.get('height'),
                        data.get('age'), data.get('gender'), data.get('activity'),
                        parse_datetime(data.get('updated_at'))
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('user_nutrition_goals', str(e))
        
        stats.add_success('user_nutrition_goals', count)
        print(f"✅ Перенесено: {count} целей по питанию")


async def migrate_mental_health():
    """Миграция ментального здоровья"""
    print("\n📦 Миграция: mood_logs...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM mood_logs")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO mood_logs (user_id, date, mood, energy, note, tags, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        data['user_id'], data.get('date'), data.get('mood'),
                        data.get('energy'), data.get('note'), data.get('tags'),
                        parse_datetime(data.get('created_at'))
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('mood_logs', str(e))
        
        stats.add_success('mood_logs', count)
        print(f"✅ Перенесено: {count} записей настроения")


async def migrate_meditation():
    """Миграция медитаций"""
    print("\n📦 Миграция: meditation_logs...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM meditation_logs")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO meditation_logs (user_id, date, duration, type, created_at)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        data['user_id'], data.get('date'), data.get('duration'),
                        data.get('type'), parse_datetime(data.get('created_at'))
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('meditation_logs', str(e))
        
        stats.add_success('meditation_logs', count)
        print(f"✅ Перенесено: {count} медитаций")


async def migrate_finance():
    """Миграция финансов"""
    print("\n📦 Миграция: transactions...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM transactions")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO transactions (user_id, type, amount, currency, category,
                                                 description, date, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        data['user_id'], data.get('type'), data.get('amount'),
                        data.get('currency', 'RUB'), data.get('category'),
                        data.get('description'), data.get('date'), data.get('created_at')
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('transactions', str(e))
        
        stats.add_success('transactions', count)
        print(f"✅ Перенесено: {count} транзакций")


async def migrate_budgets():
    """Миграция бюджетов"""
    print("\n📦 Миграция: user_budgets...")
    
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        cursor = await sqlite_db.execute("SELECT * FROM user_budgets")
        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        count = 0
        async with postgres_db.get_connection() as pg_conn:
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    await pg_conn.execute(
                        """
                        INSERT INTO user_budgets (user_id, monthly_limit, category_limits, 
                                                 currency, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (user_id) DO UPDATE SET
                            monthly_limit = $2, category_limits = $3, currency = $4, updated_at = $6
                        """,
                        data['user_id'], data.get('monthly_limit'), data.get('category_limits'),
                        data.get('currency', 'RUB'), data.get('created_at'), data.get('updated_at')
                    )
                    count += 1
                except Exception as e:
                    stats.add_error('user_budgets', str(e))
        
        stats.add_success('user_budgets', count)
        print(f"✅ Перенесено: {count} бюджетов")


async def migrate_settings():
    """Миграция настроек и справочников"""
    print("\n📦 Миграция: настройки и справочники...")
    
    # bot_cfg
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        async with postgres_db.get_connection() as pg_conn:
            cursor = await sqlite_db.execute("SELECT * FROM bot_cfg")
            rows = await cursor.fetchall()
            count = 0
            for row in rows:
                try:
                    await pg_conn.execute(
                        "INSERT INTO bot_cfg (bot, enabled, model, version) VALUES ($1, $2, $3, $4) ON CONFLICT (bot) DO UPDATE SET enabled = $2, model = $3, version = $4",
                        row[0], row[1], row[2], row[3]
                    )
                    count += 1
                except: pass
            stats.add_success('bot_cfg', count)
    
    # bot_settings
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        async with postgres_db.get_connection() as pg_conn:
            cursor = await sqlite_db.execute("SELECT * FROM bot_settings")
            rows = await cursor.fetchall()
            count = 0
            for row in rows:
                try:
                    await pg_conn.execute(
                        "INSERT INTO bot_settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = $2",
                        row[0], row[1]
                    )
                    count += 1
                except: pass
            stats.add_success('bot_settings', count)
    
    # bot_texts
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        async with postgres_db.get_connection() as pg_conn:
            cursor = await sqlite_db.execute("SELECT * FROM bot_texts")
            rows = await cursor.fetchall()
            count = 0
            for row in rows:
                try:
                    await pg_conn.execute(
                        "INSERT INTO bot_texts (key, value, description) VALUES ($1, $2, $3) ON CONFLICT (key) DO UPDATE SET value = $2, description = $3",
                        row[0], row[1], row[2] if len(row) > 2 else None
                    )
                    count += 1
                except: pass
            stats.add_success('bot_texts', count)
    
    # bot_buttons
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        async with postgres_db.get_connection() as pg_conn:
            cursor = await sqlite_db.execute("SELECT * FROM bot_buttons")
            rows = await cursor.fetchall()
            count = 0
            for row in rows:
                try:
                    await pg_conn.execute(
                        "INSERT INTO bot_buttons (key, emoji, text, description) VALUES ($1, $2, $3, $4) ON CONFLICT (key) DO UPDATE SET emoji = $2, text = $3, description = $4",
                        row[0], row[1] if len(row) > 1 else None, row[2] if len(row) > 2 else None, row[3] if len(row) > 3 else None
                    )
                    count += 1
                except: pass
            stats.add_success('bot_buttons', count)
    
    # bot_media
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        async with postgres_db.get_connection() as pg_conn:
            cursor = await sqlite_db.execute("SELECT * FROM bot_media")
            rows = await cursor.fetchall()
            count = 0
            for row in rows:
                try:
                    await pg_conn.execute(
                        "INSERT INTO bot_media (key, type, file_id) VALUES ($1, $2, $3) ON CONFLICT (key) DO UPDATE SET type = $2, file_id = $3",
                        row[0], row[1] if len(row) > 1 else None, row[2] if len(row) > 2 else None
                    )
                    count += 1
                except: pass
            stats.add_success('bot_media', count)
    
    # settings
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        async with postgres_db.get_connection() as pg_conn:
            cursor = await sqlite_db.execute("SELECT * FROM settings")
            rows = await cursor.fetchall()
            count = 0
            for row in rows:
                try:
                    await pg_conn.execute(
                        "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = $2",
                        row[0], row[1]
                    )
                    count += 1
                except: pass
            stats.add_success('settings', count)
    
    # texts
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        async with postgres_db.get_connection() as pg_conn:
            cursor = await sqlite_db.execute("SELECT * FROM texts")
            rows = await cursor.fetchall()
            count = 0
            for row in rows:
                try:
                    await pg_conn.execute(
                        "INSERT INTO texts (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = $2",
                        row[0], row[1]
                    )
                    count += 1
                except: pass
            stats.add_success('texts', count)
    
    # user_profile
    async with aiosqlite.connect(SQLITE_DB) as sqlite_db:
        async with postgres_db.get_connection() as pg_conn:
            cursor = await sqlite_db.execute("SELECT * FROM user_profile")
            rows = await cursor.fetchall()
            count = 0
            for row in rows:
                try:
                    await pg_conn.execute(
                        "INSERT INTO user_profile (user_id, name, age, gender) VALUES ($1, $2, $3, $4) ON CONFLICT (user_id) DO UPDATE SET name = $2, age = $3, gender = $4",
                        row[0], row[1] if len(row) > 1 else None, row[2] if len(row) > 2 else None, row[3] if len(row) > 3 else None
                    )
                    count += 1
                except: pass
            stats.add_success('user_profile', count)
    
    print(f"✅ Перенесены все справочники и настройки")


async def main():
    """Основная функция миграции"""
    print("=" * 60)
    print("🚀 МИГРАЦИЯ SQLite → PostgreSQL")
    print("=" * 60)
    print(f"Начало: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Инициализируем PostgreSQL
        print("\n1️⃣ Подключение к PostgreSQL...")
        await postgres_db.init_pool()
        
        # Создаём таблицы
        print("\n2️⃣ Создание таблиц...")
        await postgres_db.init_db()
        
        # Миграция данных
        print("\n3️⃣ Миграция данных...")
        
        # Основные таблицы
        await migrate_users()
        await migrate_user_bots()
        await migrate_bot_memory()  # 🧠 КРИТИЧНО!
        
        # Диалоги
        conv_id_mapping = await migrate_conversations()
        await migrate_messages(conv_id_mapping)
        
        # Подписки и токены
        await migrate_subscriptions()
        await migrate_token_usage()
        await migrate_referrals()
        
        # Курсы
        await migrate_courses()
        
        # Цели
        goal_id_mapping = await migrate_goals()
        await migrate_goal_checkins(goal_id_mapping)
        await migrate_user_streaks(goal_id_mapping)
        
        # Рутины
        await migrate_routines()
        await migrate_routine_checkins()
        
        # Питание
        await migrate_nutrition()
        await migrate_nutrition_goals()
        
        # Ментальное здоровье
        await migrate_mental_health()
        await migrate_meditation()
        
        # Финансы
        await migrate_finance()
        await migrate_budgets()
        
        # Настройки и справочники
        await migrate_settings()
        
        # Отчёт
        stats.print_report()
        
        print(f"\n✅ Завершено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n🎉 МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Закрываем пул
        await postgres_db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
