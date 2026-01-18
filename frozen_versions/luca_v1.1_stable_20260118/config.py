"""
Конфигурация модуля Luca (Soul AI)
Все настройки, лимиты и ссылки для автономности
"""

# ========== ИДЕНТИФИКАЦИЯ БОТА ==========
BOT_NAME = "luca"
BOT_DISPLAY_NAME = "💭 Диалог"
BOT_FULL_NAME = "💭 Luca (Диалог)"
BOT_DESCRIPTION = "Soul AI - друг и помощник"

# ========== ЛИМИТЫ ТОКЕНОВ ==========
MIN_STARS = 30  # Минимум звёзд для запроса
HISTORY_MESSAGES_COUNT = 20  # Сколько сообщений истории передавать в контекст

# ========== ПАМЯТЬ ==========
MAX_MEMORY_FACTS = 15  # Максимальное количество фактов о пользователе
MEMORY_UPDATE_ENABLED = True  # Включить автоматическое обновление памяти

# ========== МОДЕЛИ AI ==========
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"  # Модель по умолчанию
FALLBACK_MODEL = "gpt-4o-mini"  # Резервная модель

# ========== ГОЛОСОВОЙ РЕЖИМ ==========
VOICE_ENABLED = True  # Включить голосовой режим
VOICE_MAP = {
    "male": "onyx",  # Мужской голос OpenAI TTS
}

# ========== КЭШИРОВАНИЕ ==========
MAX_CACHE_SIZE = 1000  # Максимальное количество записей в кэше

# ========== TELEGRAPH ==========
TELEGRAPH_ENABLED = True  # Включить публикацию в Telegraph
TELEGRAPH_MIN_LENGTH = 1500  # Минимальная длина текста для предложения Telegraph

# ========== WEB ИНТЕРФЕЙС ==========
WEB_ENABLED = True  # Включить web интерфейс
WEB_BASE_URL = "https://soul-bot.ru"  # Базовый URL для web приложения
WEB_HELP_PATH = "/help"  # Путь к странице помощи
WEB_SETTINGS_PATH = "/luca/settings"  # Путь к настройкам Luca

# ========== РЕЖИМЫ ОБЩЕНИЯ ==========
CHARACTERS = {
    'soul': {
        'name': '🕊 Душа',
        'emoji': '🕊️',
        'description': 'Тёплый, понимающий, для разговоров по душам'
    },
    'mind': {
        'name': '💡 Разум',
        'emoji': '💡',
        'description': 'Чёткий, деловой, для задач и решений'
    }
}

DEFAULT_CHARACTER = 'soul'  # Характер по умолчанию

# ========== ИНТЕГРАЦИИ ==========
# Эти настройки берутся из главного config.py:
# - OPENROUTER_API_KEY (from config)
# - OPENAI_API_KEY (from config) для голосового режима
# - BOT_TOKEN (from config)
# - DATABASE связь через database.postgres_db
