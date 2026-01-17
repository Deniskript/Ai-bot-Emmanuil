"""
Все тексты для Titus (Обучение)
"""

# ========== ТЕКСТЫ МЕНЮ ==========

MENU_TEXT = """📓 <b>Обучение будущего</b>

✨ Объясняет как лучший профессор
🧠 Помнит твои сложности
🔄 Адаптируется под тебя
✅ Проверяет понимание

📖 Перед началом загляни в раздел «Помощь»"""

COURSE_CREATED = "✅ Курс создан!"

COURSE_SAVED = """👋 <b>Курс сохранён!</b>

Продолжить можно в «📂 Ваши курсы»"""

COURSE_COMPLETED = """🎉 <b>Курс завершён!</b>

Поздравляю с достижением!"""

HISTORY_CLEARED = "🗑 История очищена"

NO_COURSES = "📂 Курсов пока нет\n\nСоздайте первый в «📝 Новый курс»"

NO_ACTIVE_COURSES = "📂 Нет активных курсов"

MAX_COURSES_REACHED = "❌ Максимум 5 курсов!\n\nУдалите старый в «📂 Ваши курсы»"

COURSE_DELETED = "🗑 Курс «{name}» удалён!"

# ========== СОЗДАНИЕ КУРСА ==========

NEW_COURSE_PROMPT = "📝 <b>Напиши тему курса:</b>\n\n<i>Например: Python для начинающих</i>"

SELECT_STEPS_PROMPT = "🎯 Выбери глубину изучения:"

COURSE_NAME_PROMPT = "📝 <b>Напиши тему курса:</b>"

# ========== ПРОДОЛЖЕНИЕ КУРСА ==========

CONTINUE_COURSE_PROMPT = "▶️ <b>Выберите курс:</b>"

COURSE_WELCOME = """👋 С возвращением, {name}!

📓 <b>{course_name}</b>

⚠️ <b>В прошлый раз были сложности с:</b>
{difficult_topics}

📍 Текущий прогресс: шаг {current_step} из {total_steps}"""

COURSE_WELCOME_NO_DIFFICULTIES = """👋 С возвращением, {name}!

📓 <b>{course_name}</b>

📍 Текущий прогресс: шаг {current_step} из {total_steps}"""

# ========== УДАЛЕНИЕ КУРСА ==========

DELETE_COURSE_PROMPT = "🗑 <b>Выберите курс для удаления:</b>"

# ========== ВИДЕО АНАЛИЗ ==========

VIDEO_ANALYSIS_START = """📹 <b>Анализ видео с YouTube</b>

Отправьте ссылку на YouTube видео, и я:
✅ Извлеку субтитры
✅ Проанализирую содержимое
✅ Составлю краткий конспект

📝 <i>Работает только с видео, у которых есть субтитры</i>"""

VIDEO_ANALYSIS_EXTRACTING = "⏳ Извлекаю субтитры..."

VIDEO_ANALYSIS_ANALYZING = "✅ Субтитры получены ({length} символов)\n⏳ Анализирую..."

VIDEO_ANALYSIS_COMPLETED = "✅ Анализ завершён!"

VIDEO_ANALYSIS_NO_SUBTITLES = "❌ У этого видео нет субтитров"

VIDEO_ANALYSIS_INVALID_LINK = """❌ Неверная ссылка!

Примеры:
• youtube.com/watch?v=VIDEO_ID
• youtu.be/VIDEO_ID"""

# ========== СИСТЕМНЫЕ СООБЩЕНИЯ ==========

BOT_DISABLED = "🔴 Обучение временно недоступно"

NO_TOKENS = """❌ Звёзды закончились!

⭐ Докупите в разделе 💠 Подписка"""

REQUEST_CANCELLED = "❌ Запрос отменён"

NO_ACTIVE_REQUEST = "Нет активного запроса"

# ========== ОШИБКИ ==========

ERROR_NO_RECOGNITION = "❌ Не распознано"

ERROR_VOICE_DOWNLOAD = "❌ Не удалось скачать голосовое"

ERROR_VOICE_RECOGNITION = "❌ Не удалось распознать речь"

ERROR_SELECT_COURSE = "❌ Выберите курс из списка"

# ========== КОНСПЕКТ ==========

NO_TEXT_FOR_SUMMARY = "❌ Нет текста для конспекта"

SUMMARY_CREATING = "📝 Создаю конспект..."

SUMMARY_NOT_ENOUGH_TOKENS = "❌ Недостаточно звёзд!"

# ========== FOOTER ==========

RESPONSE_FOOTER = "\n\n<i>📓 Обучение • Шаг {step}/{total_steps}</i>"

RESPONSE_FOOTER_NO_COURSE = "\n\n<i>📓 Обучение</i>"
