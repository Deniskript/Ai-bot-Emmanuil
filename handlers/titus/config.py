"""
Конфигурация модуля Titus (Обучение)
Только специфичные для Titus настройки.
Общие лимиты берутся из core/config.py
"""

# Ссылка на core для общих лимитов (не дублируем!)
# from core.config import CACHE_MAX_SIZE, RATE_LIMIT_REQUESTS

# ========== ИДЕНТИФИКАЦИЯ БОТА ==========
BOT_NAME = "titus"
BOT_DISPLAY_NAME = "📓 Обучение"
BOT_FULL_NAME = "📓 Titus (Обучение)"
BOT_DESCRIPTION = "Умный репетитор будущего"

# ========== ЛИМИТЫ (специфичные для Titus) ==========
MIN_STARS = 30  # Минимум звёзд для запроса (берётся из главного config)
MAX_RESPONSE_TOKENS = 4000  # Максимум токенов в ответе
HISTORY_MESSAGES_COUNT = 50  # Сколько сообщений истории передавать в контекст

# ========== КУРСЫ (специфично для Titus) ==========
MAX_ACTIVE_COURSES = 5  # Максимальное количество активных курсов
DEFAULT_STEPS_OPTIONS = [10, 40, 80]  # Варианты количества шагов

# ========== ПАМЯТЬ КУРСОВ (специфично для Titus) ==========
MAX_COMPLETED_TOPICS = 12  # Максимальное количество пройденных тем в контексте
MAX_PROBLEM_ZONES = 7  # Максимальное количество проблемных зон в контексте

# ========== МОДЕЛИ AI ==========
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"  # Модель по умолчанию
FALLBACK_MODEL = "gpt-4o-mini"  # Резервная модель
VIDEO_ANALYSIS_MODEL = "google/gemini-2.0-flash-exp:free"  # Бесплатная модель для анализа видео

# ========== КЭШИРОВАНИЕ ==========
# Берётся из core/config.py: CACHE_MAX_SIZE = 1000
MAX_CACHE_SIZE = 1000  # Для совместимости (deprecated, используй core)

# ========== ВИДЕО АНАЛИЗ (специфично для Titus) ==========
VIDEO_ANALYSIS_ENABLED = True  # Включить анализ видео
MAX_TRANSCRIPT_LENGTH = 50000  # Максимальная длина субтитров для анализа

# ========== ФОРМАТИРОВАНИЕ ==========
USE_HTML = True  # Использовать HTML форматирование
USE_MARKDOWN = False  # НЕ использовать Markdown
STREAMING_ENABLED = True  # Включить потоковую передачу ответов

# ========== СИСТЕМНЫЕ ==========
DEBUG_MODE = False  # Режим отладки
LOG_CONVERSATIONS = True  # Логировать разговоры в БД
