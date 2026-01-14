## VseGPT видео: настройка через `.env`

### 1) Создай файл окружения

Создай файл:

- `/root/ai-bot/.env`

И добавь в него переменные:

```bash
# PostgreSQL
DATABASE_URL=...

# Текущий провайдер изображений (ProxyAPI/OpenAI-compatible)
OPENAI_API_KEY=...

# VseGPT (видео)
VSEGPT_API_KEY=REPLACE_ME           # сюда вставь свой ключ VseGPT (НЕ хранить в репозитории/файлах)
VSEGPT_VIDEO_BASE_URL=https://api.vsegpt.ru/v1/video
```

Важно: **не коммить** `/root/ai-bot/.env` в git.

### 2) Перезагрузи systemd и сервисы

```bash
sudo systemctl daemon-reload
sudo systemctl restart aibot
sudo systemctl restart soul-bot-web
```

### 3) Проверка

- Открой в боте: **📸 Фото → ⚙️ Настройки → 🎬 Видео**
- Нажми **✅ Применить для видео**
  - Ошибка `expected str, got dict` больше не должна появляться.
- Нажми **▶️ Начать в боте**
  - Бот не должен писать “нужен API key”, если `VSEGPT_API_KEY` задан.

