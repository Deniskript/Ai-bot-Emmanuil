"""
Конфигурация модуля Lifestyle
Все настройки, лимиты и ссылки для автономности
"""

# ========== ИДЕНТИФИКАЦИЯ БОТА ==========
BOT_NAME = "lifestyle"
BOT_DISPLAY_NAME = "🏆 Лайфстайл"
BOT_FULL_NAME = "🏆 Lifestyle"
BOT_DESCRIPTION = "Улучшай качество жизни"

# ========== ПОДМОДУЛИ ==========
MODULES = {
    "routine": {
        "name": "🗓 Режим дня",
        "enabled": True
    },
    "magic": {
        "name": "🔮 Эзотерика",
        "enabled": True
    },
    # Удалённые разделы оставляем закомментированными по требованиям
    # "viral": {"name": "🎬 Вирусный разбор", "enabled": True},
    # "goals": {"name": "🎯 Трекер целей", "enabled": True},
    # "mental": {"name": "🧘 Ментальное", "enabled": True},
    # "finance": {"name": "💰 Финансы", "enabled": True},
}

# ========== ЛИМИТЫ ТОКЕНОВ ==========
MIN_TOKENS = 3000  # Минимум токенов для запроса
MAX_RESPONSE_TOKENS = 4000  # Максимум токенов в ответе

# ========== ВИРУСНЫЙ РАЗБОР ==========
VIRAL_PRICES = {
    "text_advice": 50,
    "video_analysis": 300,
    "link_analysis": 300
}

# ========== МОДЕЛИ AI ==========
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"
FALLBACK_MODEL = "gpt-4o-mini"
VIDEO_ANALYSIS_MODEL = "google/gemini-2.0-flash-exp:free"

# ========== КЭШИРОВАНИЕ ==========
MAX_CACHE_SIZE = 1000
CACHE_CLEANUP_PERCENT = 0.2

# ========== СИСТЕМНЫЕ ==========
DEBUG_MODE = False
LOG_CONVERSATIONS = True

# ========== ИНТЕГРАЦИИ ==========
# Эти настройки берутся из главного config.py
# - OPENROUTER_API_KEY (from config)
# - BOT_TOKEN (from config)
# - DATABASE связь через database.postgres_db и database.redis_db
