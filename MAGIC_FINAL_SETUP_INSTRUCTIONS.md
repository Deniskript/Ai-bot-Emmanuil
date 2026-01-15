# 🎯 ФИНАЛЬНАЯ НАСТРОЙКА РАЗДЕЛА "МАГИЯ"

**Дата:** 2026-01-15 18:38 UTC  
**Статус:** ⚠️ ТРЕБУЕТСЯ ПОСЛЕДНИЙ ШАГ

---

## ✅ ЧТО УЖЕ ИСПРАВЛЕНО

1. ✅ Гороскоп: сохранение и загрузка дат (ISO формат)
2. ✅ Таро: кнопка "Карта дня" не зелёная
3. ✅ Гадания: функция загрузки фото добавлена
4. ✅ Таро: функция загрузки фото работает
5. ✅ Картинки Таро: используют полный URL вместо base64
6. ✅ Все анимации "готовится..." работают
7. ✅ Кнопка "Вернуться" прикреплена к низу

---

## ⚠️ ПОСЛЕДНИЙ ШАГ: НАСТРОИТЬ ДОМЕН

### Проблема:
Картинки Таро сейчас используют `http://localhost:5000`, что **не работает в Telegram WebApp**.

### Текущий результат:
```json
{
  "image": "http://localhost:5000/assets/tarot/magician.svg"
}
```

### Нужный результат:
```json
{
  "image": "https://soul-bot.ru/assets/tarot/magician.svg"
}
```

---

## 🔧 РЕШЕНИЕ: УСТАНОВИТЬ ПЕРЕМЕННУЮ ОКРУЖЕНИЯ

### Вариант 1: Если есть домен с SSL (рекомендуется)
```bash
# В файле .env добавить:
WEBAPP_DOMAIN=https://soul-bot.ru
```

### Вариант 2: Если нет SSL, использовать IP
```bash
# В файле .env добавить:
WEBAPP_DOMAIN=http://YOUR_SERVER_IP:5000
```

### Вариант 3: Если используется nginx прокси
```bash
# В файле .env добавить:
WEBAPP_DOMAIN=https://soul-bot.ru  # nginx проксирует на :5000
```

---

## 📝 КАК НАСТРОИТЬ

### Шаг 1: Открыть .env файл
```bash
cd /root/ai-bot
nano .env
```

### Шаг 2: Добавить строку
Добавить в конец файла:
```bash
# Web App Domain для Telegram Mini Apps
WEBAPP_DOMAIN=https://soul-bot.ru
```

**Замените `https://soul-bot.ru` на ваш реальный домен!**

### Шаг 3: Сохранить и перезапустить
```bash
# Ctrl+O, Enter, Ctrl+X для выхода из nano
systemctl restart soul-bot-web.service
```

### Шаг 4: Проверить
```bash
curl -X POST http://localhost:5000/magic/tarot/spread \
  -H "Content-Type: application/json" \
  -d '{"user_id":999,"type":"card_day"}' | grep image
```

Должно показать:
```json
"image": "https://soul-bot.ru/assets/tarot/..."
```

---

## 🌐 НАСТРОЙКА NGINX (если используется)

Если используется nginx прокси, убедитесь что настроена раздача статических файлов:

```nginx
server {
    listen 443 ssl;
    server_name soul-bot.ru;
    
    location /assets/ {
        alias /root/ai-bot/assets/;
        add_header Access-Control-Allow-Origin *;
        expires 1d;
    }
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## ✅ ПРОВЕРКА РАБОТЫ

### Тест 1: Проверить URL картинок
```bash
curl -X POST http://localhost:5000/magic/tarot/spread \
  -d '{"user_id":999,"type":"card_day"}' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('Image URL:', data['cards'][0]['image'])
"
```

**Должно быть:** `https://soul-bot.ru/assets/tarot/...`  
**НЕ должно быть:** `http://localhost:5000/...`

### Тест 2: Проверить доступность через домен
```bash
curl -I https://soul-bot.ru/assets/tarot/fool.svg
```

**Ожидается:** `HTTP/2 200`

### Тест 3: Проверить в Telegram WebApp
1. Открыть бота в Telegram
2. Перейти в раздел "🔮 Магия"
3. Открыть "Таро"
4. Нажать "Карта дня"
5. **Картинка должна отобразиться!**

---

## 🐛 ЕСЛИ ВСЁ ЕЩЁ НЕ РАБОТАЕТ

### Вариант А: Картинки не отображаются в Telegram
**Причина:** CSP политика Telegram блокирует внешние ресурсы

**Решение:** Использовать data URI (base64) но НЕ SVG, а PNG:

```bash
pip install cairosvg
```

В `web_app.py`:
```python
from cairosvg import svg2png
import base64

def draw_tarot_cards(count: int) -> list:
    # ... выбор карт ...
    svg_path = f"assets/tarot/{c['slug']}.svg"
    png = svg2png(url=svg_path, output_width=300)
    png_base64 = base64.b64encode(png).decode()
    cards.append({
        "name": c["name"],
        "image": f"data:image/png;base64,{png_base64}"
    })
```

### Вариант Б: Отправлять через Telegram API
Вместо WebApp, бот может отправить картинки как фото через `send_photo()`.

---

## 📊 СТАТУС ВСЕХ ИСПРАВЛЕНИЙ

| Компонент | Статус | Действие |
|-----------|--------|----------|
| Backend (даты) | ✅ Исправлено | Нет |
| Frontend (UX) | ✅ Исправлено | Нет |
| Гадания (фото) | ✅ Добавлено | Нет |
| Таро (кнопка) | ✅ Исправлено | Нет |
| Таро (фото) | ✅ Работает | Нет |
| Таро (картинки) | ⚠️ Нужен домен | **Добавить WEBAPP_DOMAIN в .env** |

---

## 🎯 ИТОГОВАЯ КОМАНДА

```bash
# 1. Открыть .env
nano /root/ai-bot/.env

# 2. Добавить строку в конец:
WEBAPP_DOMAIN=https://soul-bot.ru

# 3. Сохранить и выйти (Ctrl+O, Enter, Ctrl+X)

# 4. Перезапустить сервер
systemctl restart soul-bot-web.service

# 5. Проверить
curl -X POST http://localhost:5000/magic/tarot/spread -d '{"user_id":999,"type":"card_day"}' | grep image
```

**Ожидаемый результат:**
```
"image": "https://soul-bot.ru/assets/tarot/magician.svg"
```

**Затем проверить в Telegram - картинки должны отображаться!**

---

✅ **После добавления WEBAPP_DOMAIN все картинки заработают!**
