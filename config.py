import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/lukabotai")
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/dstarikovd")

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
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

# База данных
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")

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
