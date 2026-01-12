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
MIN_TOKENS = 3000  # Минимум токенов для запроса
MAX_RESPONSE_TOKENS = 4000  # Максимум токенов в ответе
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
    "male": "onyx",    # Мужской голос OpenAI TTS
    "female": "nova"   # Женский голос OpenAI TTS
}
VOICE_GENDER_NAMES = {
    "male": "👨 Мужской",
    "female": "👩 Женский"
}

# ========== КЭШИРОВАНИЕ ==========
MAX_CACHE_SIZE = 1000  # Максимальное количество записей в кэше
CACHE_CLEANUP_PERCENT = 0.2  # Процент удаляемых записей при переполнении

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

# ========== ФОРМАТИРОВАНИЕ ==========
USE_HTML = True  # Использовать HTML форматирование
USE_MARKDOWN = False  # Использовать Markdown форматирование
STREAMING_ENABLED = True  # Включить потоковую передачу ответов

# ========== АНТИФЛУД ==========
ANTIFLOOD_ENABLED = True  # Включить защиту от флуда
ANTIFLOOD_TIMEOUT = 3  # Секунд между запросами

# ========== СИСТЕМНЫЕ ==========
DEBUG_MODE = False  # Режим отладки
LOG_CONVERSATIONS = True  # Логировать разговоры в БД

# ========== ИНТЕГРАЦИИ ==========
# Эти настройки берутся из главного config.py
# Здесь только документация для понимания зависимостей:
# - OPENROUTER_API_KEY (from config)
# - OPENAI_API_KEY (from config) для голосового режима
# - BOT_TOKEN (from config)
# - DATABASE связь через database.db

# ========== СТАТУСЫ СОСТОЯНИЙ ==========
STATE_MENU = "menu"
STATE_CHAT = "chat"
STATE_CHAR_SELECT = "char"
STATE_VOICE_CHOOSE = "voice_choose"
STATE_VOICE_CHAT = "voice_chat"
