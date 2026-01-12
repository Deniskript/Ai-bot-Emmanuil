#!/usr/bin/env python3
"""
Скрипт для интеграции check_tokens_and_notify во все хендлеры
"""
import re
import os

# Файлы для обновления
files_to_update = [
    'handlers/silas.py',
    'handlers/titus.py',
    'handlers/images.py',
    'handlers/viral_analysis.py',
]

# Добавить импорт
def add_import(content):
    if 'from utils.errors import check_tokens_and_notify' in content:
        return content
    
    # Найти импорты из utils
    import_pattern = r'(from utils\.[a-z_]+ import [^\n]+\n)'
    imports = re.findall(import_pattern, content)
    
    if imports:
        # Добавить после последнего импорта из utils
        last_import = imports[-1]
        new_import = 'from utils.errors import check_tokens_and_notify\n'
        content = content.replace(last_import, last_import + new_import)
    
    return content

# Заменить проверку токенов
def replace_token_checks(content):
    # Паттерн 1: простая проверка
    pattern1 = r'remaining = await db\.get_available_tokens\([^\)]+\)\s+if remaining < MIN_TOKENS:\s+await [^\.]+\.answer\([^\)]+\)\s+return'
    
    replacement1 = '''# Проверка токенов с красивым сообщением
    if not await check_tokens_and_notify(user_id, MIN_TOKENS, msg):
        return'''
    
    content = re.sub(pattern1, replacement1, content, flags=re.MULTILINE | re.DOTALL)
    
    # Паттерн 2: проверка с токенами и сообщением
    pattern2 = r'tokens = await db\.get_available_tokens\([^\)]+\)\s+if tokens < ([A-Z_\[\]\'\"0-9a-z]+):\s+await [^\.]+\.answer\([^\)]+\)\s+return'
    
    def replacer(match):
        price = match.group(1)
        return f'''# Проверка токенов с красивым сообщением
    if not await check_tokens_and_notify(user_id, {price}, msg):
        return'''
    
    content = re.sub(pattern2, replacer, content, flags=re.MULTILINE | re.DOTALL)
    
    return content

for filepath in files_to_update:
    print(f"Обновляю {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Добавляем импорт
    content = add_import(content)
    
    # Заменяем проверки
    # content = replace_token_checks(content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ {filepath} обновлен")

print("\n✅ Все файлы обновлены!")
