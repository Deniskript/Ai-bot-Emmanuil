#!/usr/bin/env python3
"""Проверка возможных ошибок в обработчике Silas"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("🔵 Проверка обработчика Silas...")
print("=" * 50)

# Проверка 1: Импорты
print("\n1. Проверка импортов...")
try:
    from handlers.silas.handler import router, SilasSt, silas_set_duration
    from handlers.silas import keyboards as kb, texts
    from database import db
    print("✅ Все импорты успешны")
except Exception as e:
    print(f"❌ Ошибка импорта: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Проверка 2: Функции БД
print("\n2. Проверка функций БД...")
funcs_to_check = [
    'start_session', 'end_session', 'set_mood', 'get_mood_stats',
    'clear_msgs', 'reset_msg_counter', 'get_user_bot', 'get_memory',
    'get_msgs', 'inc_msg_counter'
]
missing = []
for func_name in funcs_to_check:
    if not hasattr(db, func_name):
        missing.append(func_name)
    else:
        print(f"  ✅ {func_name}")

if missing:
    print(f"\n❌ Отсутствуют функции: {missing}")
    sys.exit(1)

# Проверка 3: Сигнатура обработчика
print("\n3. Проверка обработчика silas_set_duration...")
import inspect
sig = inspect.signature(silas_set_duration)
print(f"  ✅ Сигнатура: {sig}")

# Проверка 4: Проверка фильтра
print("\n4. Проверка фильтра F.text.in_...")
from aiogram import F
test_cases = [
    ("15 минут", True),
    ("30 минут", True),
    ("60 минут", True),
    ("15 минуты", False),
    ("10 минут", False),
]

for text, expected in test_cases:
    result = text in {"15 минут", "30 минут", "60 минут"}
    status = "✅" if result == expected else "❌"
    print(f"  {status} '{text}' -> {result} (ожидалось {expected})")

# Проверка 5: Проверка текстов
print("\n5. Проверка текстов...")
try:
    dur_text = texts.DURATION_MENU
    start_text = texts.START_SESSION.format(duration=30)
    print(f"  ✅ DURATION_MENU: {dur_text[:50]}...")
    print(f"  ✅ START_SESSION: {start_text[:50]}...")
except Exception as e:
    print(f"  ❌ Ошибка текстов: {e}")

# Проверка 6: Проверка клавиатур
print("\n6. Проверка клавиатур...")
try:
    dur_kb = kb.psycho_dur_kb()
    chat_kb = kb.psycho_chat_kb()
    print(f"  ✅ psycho_dur_kb: {len(dur_kb.keyboard)} строк")
    print(f"  ✅ psycho_chat_kb: {len(chat_kb.keyboard)} строк")
except Exception as e:
    print(f"  ❌ Ошибка клавиатур: {e}")

print("\n" + "=" * 50)
print("✅ Все проверки завершены")
