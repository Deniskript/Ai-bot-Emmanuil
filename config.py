import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Валидация критических переменных
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не установлен в .env файле!")
    sys.exit(1)

# Безопасная обработка ADMIN_IDS
try:
    ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
    if not ADMIN_IDS:
        print("⚠️ ВНИМАНИЕ: ADMIN_IDS пуст, админ-панель будет недоступна")
except ValueError as e:
    print(f"❌ ОШИБКА: Неверный формат ADMIN_IDS: {e}")
    sys.exit(1)
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/lukabotai")
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/dstarikovd")

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("❌ ОШИБКА: OPENROUTER_API_KEY не установлен!")
    sys.exit(1)
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "https://t.me/lukabotai")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "Luka AI Bot")

# Модель по умолчанию
MODEL = os.getenv("MODEL", "anthropic/claude-sonnet-4.5")

# OpenAI/ProxyAPI для Whisper
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Робокасса
ROBOKASSA_LOGIN = os.getenv("ROBOKASSA_LOGIN")
ROBOKASSA_PASS1 = os.getenv("ROBOKASSA_PASS1")
ROBOKASSA_PASS2 = os.getenv("ROBOKASSA_PASS2")
ROBOKASSA_TEST_MODE = os.getenv("ROBOKASSA_TEST_MODE", "1") == "1"

# База данных (валидация пути)
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")
# Проверка на path traversal
if ".." in DATABASE_PATH or DATABASE_PATH.startswith("/etc") or DATABASE_PATH.startswith("/sys"):
    print("❌ ОШИБКА: Небезопасный путь к базе данных!")
    sys.exit(1)

# Бонус новым пользователям (токены)
NEW_USER_BONUS = int(os.getenv("NEW_USER_BONUS", "25000"))

# Минимум токенов для запроса
MIN_TOKENS = 3000

# Подписки
SUBSCRIPTIONS = {
    "mini": {
        "name": "Mini",
        "price": 490,
        "tokens": 400000,
        "model": MODEL
    },
    "standard": {
        "name": "Standard", 
        "price": 990,
        "tokens": 900000,
        "model": MODEL
    }
}

# Пакеты токенов
TOKEN_PACKAGES = {
    "100k": {"name": "100K токенов", "tokens": 100000, "price": 149},
    "200k": {"name": "200K токенов", "tokens": 200000, "price": 249}
}
