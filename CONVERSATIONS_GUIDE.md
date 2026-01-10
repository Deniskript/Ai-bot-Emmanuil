# 📖 Руководство по системе диалогов

## ✅ Что реализовано

### 1. База данных
- **Таблица `conversations`**: Хранит информацию о диалогах (user_id, bot, created_at, updated_at)
- **Таблица `messages`**: Хранит сообщения диалогов (conversation_id, role, content, model, timestamp)

### 2. Веб-интерфейс
- **URL**: `https://soul-bot.ru/chat/<ID>`
- **Дизайн**: Светлая тема, белые карточки с тенью
- **Функции**:
  - Кнопка "В браузер"
  - Кнопка "Скопировать ссылку"
  - Кнопка "Скопировать" (весь текст)
  - Блоки кода с кнопкой "Скопировать"
  - Автоматическое удаление строк "Модель: #Claude"

### 3. Логика показа
- **Ответ < 3000 символов**: Полный текст + кнопка "💬 Просмотреть весь диалог"
- **Ответ > 3000 символов**: Превью 800 символов + кнопка "💬 Читать полностью"

---

## 🔧 Как использовать в handlers

### Импорт модулей

```python
from utils.conversations import (
    save_message,
    get_chat_button,
    should_show_preview,
    clean_response
)
```

### Пример интеграции в handler

```python
@router.message(F.text)
async def handle_message(message: Message):
    user_id = message.from_user.id
    bot_name = "luca"  # или "silas", "titus"
    
    # 1. Сохраняем сообщение пользователя
    await save_message(
        user_id=user_id,
        role="user",
        content=message.text,
        bot=bot_name
    )
    
    # 2. Получаем ответ от AI
    response = await get_ai_response(message.text)
    
    # 3. Очищаем ответ от служебных строк
    clean_resp = clean_response(response)
    
    # 4. Сохраняем ответ ассистента
    conv_id = await save_message(
        user_id=user_id,
        role="assistant",
        content=clean_resp,
        bot=bot_name,
        model="anthropic/claude-sonnet-4"
    )
    
    # 5. Проверяем, нужно ли показывать превью
    needs_preview, display_text = should_show_preview(clean_resp)
    
    # 6. Создаем кнопку для просмотра диалога
    keyboard = get_chat_button(conv_id, len(clean_resp))
    
    # 7. Отправляем ответ
    await message.answer(
        display_text,
        reply_markup=keyboard
    )
```

---

## 📝 Функции API

### `save_message(user_id, role, content, bot, model=None)`
Сохраняет сообщение в базу данных.

**Параметры:**
- `user_id` (int): ID пользователя Telegram
- `role` (str): "user" или "assistant"
- `content` (str): Текст сообщения
- `bot` (str): Имя бота ("luca", "silas", "titus")
- `model` (str, optional): Название модели AI

**Возвращает:**
- `int`: ID диалога (conversation_id)

---

### `get_chat_button(conv_id, response_length)`
Создает кнопку для просмотра диалога.

**Параметры:**
- `conv_id` (int): ID диалога
- `response_length` (int): Длина ответа в символах

**Возвращает:**
- `InlineKeyboardMarkup`: Кнопка со ссылкой на диалог

**Логика текста кнопки:**
- < 3000 символов: "💬 Просмотреть весь диалог"
- ≥ 3000 символов: "💬 Читать полностью"

---

### `should_show_preview(content, max_length=3000)`
Определяет, нужно ли показывать превью.

**Параметры:**
- `content` (str): Текст сообщения
- `max_length` (int): Максимальная длина (по умолчанию 3000)

**Возвращает:**
- `tuple[bool, str]`: (нужно_превью, текст_для_показа)

**Логика:**
- Если длина ≤ 3000: возвращает `(False, полный_текст)`
- Если длина > 3000: возвращает `(True, первые_800_символов + "...")`

---

### `clean_response(content)`
Удаляет служебные строки из ответа.

**Параметры:**
- `content` (str): Исходный текст

**Возвращает:**
- `str`: Очищенный текст

**Удаляет:**
- "Модель: #Claude"
- "Model: #Claude"
- Подобные строки с любым названием модели

---

## 🚀 Статус сервисов

### Проверка статуса веб-приложения
```bash
systemctl status soul-bot-web
```

### Перезапуск веб-приложения
```bash
systemctl restart soul-bot-web
```

### Просмотр логов
```bash
journalctl -u soul-bot-web -f
```

### Проверка Nginx
```bash
nginx -t
systemctl status nginx
```

---

## 🔗 Ссылки

- **Главная страница**: https://soul-bot.ru
- **Просмотр диалога**: https://soul-bot.ru/chat/<ID>
- **Локальный Flask**: http://127.0.0.1:5000

---

## 📊 Структура базы данных

### Таблица `conversations`
```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    bot TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Таблица `messages`
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    model TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
```

---

## ⚠️ Важные замечания

1. **Telegraph удален**: Старая система Telegraph больше не используется
2. **Автоматическое сохранение**: Каждое сообщение автоматически сохраняется в БД
3. **Одна кнопка**: После каждого ответа показывается только одна кнопка для просмотра
4. **Очистка ответов**: Строки "Модель: #Claude" автоматически удаляются
5. **SSL/HTTPS**: Все ссылки используют HTTPS

---

## 🎯 TODO для handlers

Обновите следующие файлы:
- [ ] `handlers/luca.py`
- [ ] `handlers/silas.py`
- [ ] `handlers/titus.py`

В каждом добавьте:
1. Импорт функций из `utils.conversations`
2. Вызов `save_message()` для сохранения сообщений
3. Вызов `clean_response()` для очистки ответов
4. Вызов `should_show_preview()` для проверки длины
5. Вызов `get_chat_button()` для создания кнопки
6. Добавление `reply_markup=keyboard` в ответ

---

## 📞 Поддержка

Если возникли проблемы:
1. Проверьте статус сервисов: `systemctl status soul-bot-web nginx`
2. Просмотрите логи: `journalctl -u soul-bot-web -n 50`
3. Проверьте БД: `sqlite3 ai_bot.db "SELECT * FROM conversations LIMIT 5;"`

**Система готова к использованию!** 🎉
