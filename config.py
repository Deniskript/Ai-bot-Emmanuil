import os
from dotenv import load_dotenv

# Загружаем .env ПЕРВЫМ ДЕЛОМ
load_dotenv(override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/channel")
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/support")

DATABASE_PATH = "database/bot.db"
NEW_USER_BONUS = 5000
MIN_TOKENS = 100
MEMORY_SIZE = 20
SPAM_INTERVAL = 2
SPAM_MAX_REQUESTS = 1
