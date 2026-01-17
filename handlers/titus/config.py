"""
Конфигурация модуля Titus (Обучение)
Все настройки, лимиты и ссылки для автономности
"""

# ========== ИДЕНТИФИКАЦИЯ БОТА ==========
BOT_NAME = "titus"
BOT_DISPLAY_NAME = "📓 Обучение"
BOT_FULL_NAME = "📓 Titus (Обучение)"
BOT_DESCRIPTION = "Умный репетитор будущего"

# ========== ЛИМИТЫ ТОКЕНОВ ==========
MIN_STARS = 30  # Минимум звёзд для запроса
MAX_RESPONSE_TOKENS = 4000  # Максимум звёзд в ответе
HISTORY_MESSAGES_COUNT = 50  # Сколько сообщений истории передавать в контекст

# ========== КУРСЫ ==========
MAX_ACTIVE_COURSES = 5  # Максимальное количество активных курсов
DEFAULT_STEPS_OPTIONS = [10, 40, 80]  # Варианты количества шагов

# ========== ПАМЯТЬ КУРСОВ ==========
MAX_COMPLETED_TOPICS = 12  # Максимальное количество пройденных тем в контексте
MAX_PROBLEM_ZONES = 7  # Максимальное количество проблемных зон в контексте

# ========== МОДЕЛИ AI ==========
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"  # Модель по умолчанию
FALLBACK_MODEL = "gpt-4o-mini"  # Резервная модель
VIDEO_ANALYSIS_MODEL = "google/gemini-2.0-flash-exp:free"  # Модель для анализа видео

# ========== КЭШИРОВАНИЕ ==========
MAX_CACHE_SIZE = 1000  # Максимальное количество записей в кэше
CACHE_CLEANUP_PERCENT = 0.2  # Процент удаляемых записей при переполнении

# ========== TELEGRAPH ==========
# Telegraph удалён - теперь используется Web App для просмотра диалогов

# ========== ВИДЕО АНАЛИЗ ==========
VIDEO_ANALYSIS_ENABLED = True  # Включить анализ видео
MAX_TRANSCRIPT_LENGTH = 50000  # Максимальная длина субтитров для анализа

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
# - BOT_TOKEN (from config)
# - DATABASE связь через database.postgres_db

# ========== СТАТУСЫ СОСТОЯНИЙ ==========
STATE_MENU = "menu"
STATE_CHAT = "chat"
STATE_NEW_COURSE = "new_course"
STATE_SELECT_STEPS = "select_steps"
STATE_COURSES_MENU = "courses_menu"
STATE_CONTINUE_COURSE = "continue_course"
STATE_DELETE_COURSE = "delete_course"
STATE_VIDEO_ANALYSIS = "video_analysis"
