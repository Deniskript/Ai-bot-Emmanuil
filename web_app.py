#!/usr/bin/env python3
"""
Веб-приложение для отображения диалогов
"""
from flask import Flask, render_template_string, render_template, abort, jsonify, request, send_from_directory
import asyncio
import logging
import os
from datetime import datetime
from database.postgres_db import get_conversation, get_conversation_messages, get_subscription, get_available_stars

# Web App Domain для Telegram Mini Apps
WEBAPP_DOMAIN = os.getenv("WEBAPP_DOMAIN", "http://localhost:5000")
from database.postgres_db import init_pool, init_db, get_user_pair_session, create_pair_session, join_pair_session, get_pair_session, cancel_pair_session, get_user, create_user, get_all_user_pair_sessions, delete_pair_session_by_id, delete_all_user_pair_sessions, get_pair_session_with_names
from database import redis_db
from database import postgres_db
from utils.openrouter import ask
from utils.magic_calculations import (
    destiny_number, name_number, day_number, personal_year_number, karma_number, reduce_number,
    zodiac_sign, moon_phase_info, moon_day_advice, moon_month_calendar, moon_month_grid
)
from utils.magic_vision import analyze_image_with_prompt
from prompts.magic_prompts import (
    HOROSCOPE_SYSTEM_PROMPT, TAROT_SYSTEM_PROMPT, TAROT_PHOTO_PROMPT,
    PALM_PROMPT, FACE_PROMPT, COFFEE_PROMPT, CRYSTAL_PROMPT, CANDLE_PROMPT,
    RITUALS
)
import html
import re


TAROT_CARDS = [
    {"name": "Шут", "slug": "fool"},
    {"name": "Маг", "slug": "magician"},
    {"name": "Верховная Жрица", "slug": "high_priestess"},
    {"name": "Императрица", "slug": "empress"},
    {"name": "Император", "slug": "emperor"},
    {"name": "Иерофант", "slug": "hierophant"},
    {"name": "Влюблённые", "slug": "lovers"},
    {"name": "Колесница", "slug": "chariot"},
    {"name": "Сила", "slug": "strength"},
    {"name": "Отшельник", "slug": "hermit"},
    {"name": "Колесо Фортуны", "slug": "wheel_of_fortune"},
    {"name": "Справедливость", "slug": "justice"},
    {"name": "Повешенный", "slug": "hanged_man"},
    {"name": "Смерть", "slug": "death"},
    {"name": "Умеренность", "slug": "temperance"},
    {"name": "Дьявол", "slug": "devil"},
    {"name": "Башня", "slug": "tower"},
    {"name": "Звезда", "slug": "star"},
    {"name": "Луна", "slug": "moon"},
    {"name": "Солнце", "slug": "sun"},
    {"name": "Суд", "slug": "judgement"},
    {"name": "Мир", "slug": "world"}
]


def draw_tarot_cards(count: int) -> list:
    """Выбрать случайные карты Таро."""
    import random
    
    chosen = random.sample(TAROT_CARDS, k=min(count, len(TAROT_CARDS)))
    cards = []
    for c in chosen:
        # Используем полный URL с доменом для Telegram WebApp
        cards.append({
            "name": c["name"],
            "image": f"{WEBAPP_DOMAIN}/assets/tarot/{c['slug']}.svg"
        })
    return cards

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates')

# Глобальный event loop для всех async операций
_global_loop = None
_pool_initialized = False

def get_or_create_loop():
    """Получить или создать глобальный event loop"""
    global _global_loop
    if _global_loop is None or _global_loop.is_closed():
        _global_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_global_loop)
    return _global_loop

def ensure_pool_initialized():
    """Убедиться что пул PostgreSQL инициализирован"""
    global _pool_initialized
    if _pool_initialized:
        return
    
    try:
        loop = get_or_create_loop()
        if not _pool_initialized:
            loop.run_until_complete(init_pool())
            loop.run_until_complete(init_db())
            print("✅ PostgreSQL pool initialized in web_app")
            _pool_initialized = True
    except Exception as e:
        print(f"⚠️ Failed to initialize PostgreSQL in web_app: {e}")
        import traceback
        traceback.print_exc()


def run_async(coro):
    """Запуск async функции в глобальном loop."""
    loop = get_or_create_loop()
    return loop.run_until_complete(coro)

# Инициализируем при импорте
ensure_pool_initialized()

# HTML темп лейт для отображения чата
CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Soul Bot - Диалог #{{ conv_id }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            line-height: 1.6;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .header h1 {
            font-size: 24px;
            color: #333;
            margin: 0;
        }
        
        .header-buttons {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 10px 20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: background 0.2s;
        }
        
        .btn:hover {
            background: #5568d3;
        }
        
        .btn-secondary {
            background: #6c757d;
        }
        
        .btn-secondary:hover {
            background: #5a6268;
        }
        
        .message {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 16px;
        }
        
        .message-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #e9ecef;
        }
        
        .role {
            font-weight: 600;
            font-size: 14px;
            padding: 4px 12px;
            border-radius: 6px;
        }
        
        .role-user {
            background: #e3f2fd;
            color: #1976d2;
        }
        
        .role-assistant {
            background: #f3e5f5;
            color: #7b1fa2;
        }
        
        .timestamp {
            font-size: 12px;
            color: #6c757d;
        }
        
        .content {
            color: #333;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        .content p {
            margin-bottom: 12px;
        }
        
        .content p:last-child {
            margin-bottom: 0;
        }
        
        .code-block {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 16px;
            margin: 12px 0;
            position: relative;
            overflow-x: auto;
        }
        
        .code-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            padding-bottom: 8px;
            border-bottom: 1px solid #dee2e6;
        }
        
        .code-lang {
            font-size: 12px;
            color: #6c757d;
            font-weight: 600;
        }
        
        .copy-btn {
            padding: 4px 12px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: background 0.2s;
        }
        
        .copy-btn:hover {
            background: #5568d3;
        }
        
        .copy-btn.copied {
            background: #28a745;
        }
        
        code {
            font-family: 'Courier New', Courier, monospace;
            font-size: 14px;
            line-height: 1.5;
            display: block;
        }
        
        .inline-code {
            background: #f8f9fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', Courier, monospace;
            font-size: 13px;
        }
        
        strong {
            color: #212529;
        }
        
        .footer {
            text-align: center;
            color: #6c757d;
            font-size: 14px;
            margin-top: 40px;
            padding: 20px;
        }
        
        @media (max-width: 768px) {
            body {
                padding: 10px;
            }
            
            .header {
                padding: 15px;
            }
            
            .header h1 {
                font-size: 20px;
                width: 100%;
            }
            
            .header-buttons {
                width: 100%;
            }
            
            .btn {
                flex: 1;
                justify-content: center;
            }
            
            .message {
                padding: 15px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💬 Soul Bot - Диалог</h1>
            <div class="header-buttons">
                <button class="btn" onclick="openInBrowser()">
                    🌐 В браузер
                </button>
                <button class="btn btn-secondary" onclick="copyLink()">
                    🔗 Скопировать ссылку
                </button>
                <button class="btn btn-secondary" onclick="copyAllText()">
                    📋 Скопировать
                </button>
            </div>
        </div>
        
        {% for msg in messages %}
        <div class="message">
            <div class="message-header">
                <span class="role role-{{ msg.role }}">
                    {{ '👤 Вы' if msg.role == 'user' else '🤖 Ассистент' }}
                </span>
                <span class="timestamp">{{ msg.timestamp }}</span>
            </div>
            <div class="content">{{ msg.formatted_content|safe }}</div>
        </div>
        {% endfor %}
        
        <div class="footer">
            <p>Powered by Soul Bot 🙏</p>
            <p><a href="https://soul-bot.ru" style="color: #667eea;">soul-bot.ru</a></p>
        </div>
    </div>
    
    <script>
        function openInBrowser() {
            window.location.href = window.location.href;
        }
        
        function copyLink() {
            const url = window.location.href;
            navigator.clipboard.writeText(url).then(() => {
                alert('✓ Ссылка скопирована!');
            });
        }
        
        function copyAllText() {
            const messages = document.querySelectorAll('.message .content');
            let text = '';
            messages.forEach(msg => {
                text += msg.textContent + '\\n\\n';
            });
            navigator.clipboard.writeText(text).then(() => {
                alert('✓ Текст скопирован!');
            });
        }
        
        function copyCode(btn) {
            const codeBlock = btn.closest('.code-block').querySelector('code');
            const text = codeBlock.textContent;
            navigator.clipboard.writeText(text).then(() => {
                const originalText = btn.textContent;
                btn.textContent = '✓ Скопировано';
                btn.classList.add('copied');
                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.classList.remove('copied');
                }, 2000);
            });
        }
    </script>
</body>
</html>
"""


def format_message_content(content: str) -> str:
    """Форматирование контента сообщения"""
    # Удаляем строку "Модель: #Claude" и подобные
    content = re.sub(r'Модель:\s*#\w+\s*', '', content)
    content = re.sub(r'Model:\s*#\w+\s*', '', content)
    
    # Экранируем HTML
    content = html.escape(content)
    
    # Обрабатываем блоки кода
    def replace_code_block(match):
        lang = match.group(1) or 'text'
        code = match.group(2)
        return f'''<div class="code-block">
            <div class="code-header">
                <span class="code-lang">{lang}</span>
                <button class="copy-btn" onclick="copyCode(this)">Скопировать</button>
            </div>
            <code>{code}</code>
        </div>'''
    
    content = re.sub(r'```(\w+)?\n(.*?)```', replace_code_block, content, flags=re.DOTALL)
    
    # Inline код
    content = re.sub(r'`([^`]+)`', r'<span class="inline-code">\1</span>', content)
    
    # Жирный текст
    content = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', content)
    
    # Параграфы
    paragraphs = content.split('\n\n')
    content = ''.join(f'<p>{p}</p>' for p in paragraphs if p.strip())
    
    return content


@app.route('/chat/<int:conv_id>')
def view_chat(conv_id):
    """Просмотр диалога"""
    try:
        ensure_pool_initialized()
        loop = get_or_create_loop()
        
        # Получаем диалог и сообщения
        conv = loop.run_until_complete(get_conversation(conv_id))
        if not conv:
            abort(404)
        
        messages = loop.run_until_complete(get_conversation_messages(conv_id))
        
        # Форматируем сообщения
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                'role': msg['role'],
                'content': msg['content'],
                'formatted_content': format_message_content(msg['content']),
                'timestamp': msg['timestamp'][:19].replace('T', ' ')  # 2024-01-10 12:30:00
            })
        
        return render_template_string(
            CHAT_TEMPLATE,
            conv_id=conv_id,
            messages=formatted_messages
        )
    except Exception as e:
        print(f"Error viewing chat: {e}")
        abort(500)


@app.route('/')
def index():
    """Главная страница"""
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Soul Bot</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                color: white;
                text-align: center;
                padding: 20px;
            }
            h1 {
                font-size: 3rem;
                margin-bottom: 1rem;
            }
            p {
                font-size: 1.2rem;
                opacity: 0.9;
            }
        </style>
    </head>
    <body>
        <div>
            <h1>🙏 Soul Bot</h1>
            <p>Система просмотра диалогов</p>
            <p style="font-size: 0.9rem; margin-top: 2rem;">Используйте /chat/&lt;id&gt; для просмотра диалогов</p>
        </div>
    </body>
    </html>
    """


@app.route('/assets/<path:filename>')
def assets_static(filename: str):
    """Статические файлы (assets)"""
    base_dir = os.path.join(os.path.dirname(__file__), "assets")
    return send_from_directory(base_dir, filename)


@app.route('/webapp')
def webapp():
    """Telegram Mini App - Личный кабинет"""
    try:
        return render_template('webapp.html')
    except Exception as e:
        print(f"Error loading webapp: {e}")
        return f"Error: {e}", 500


@app.route('/payment')
def payment():
    """Telegram Mini App - Оплата подписки"""
    try:
        return render_template('payment.html')
    except Exception as e:
        print(f"Error loading payment: {e}")
        return f"Error: {e}", 500


@app.route('/help')
def help_page():
    """Telegram Mini App - Помощь"""
    try:
        return render_template('help.html')
    except Exception as e:
        print(f"Error loading help: {e}")
        return f"Error: {e}", 500


@app.route('/how-it-works/dialog')
def how_it_works_dialog():
    """Telegram Mini App - Как это работает (Диалог)"""
    try:
        return render_template('how-it-works-dialog.html')
    except Exception as e:
        print(f"Error loading how-it-works dialog: {e}")
        return f"Error: {e}", 500


@app.route('/how-it-works/dialog-new')
def how_it_works_dialog_new():
    """Telegram Mini App - Как это работает (Диалог, новая версия)"""
    try:
        return render_template('how-it-works-dialog-new.html')
    except Exception as e:
        print(f"Error loading how-it-works dialog new: {e}")
        return f"Error: {e}", 500


@app.route('/how-it-works/psychologist')
def how_it_works_psychologist():
    """Telegram Mini App - Как это работает (Психолог)"""
    try:
        return render_template('how-it-works-psychologist.html')
    except Exception as e:
        print(f"Error loading how-it-works psychologist: {e}")
        return f"Error: {e}", 500


@app.route('/how-it-works/education')
def how_it_works_education():
    """Telegram Mini App - Как это работает (Обучение)"""
    try:
        return render_template('how-it-works-education.html')
    except Exception as e:
        print(f"Error loading how-it-works education: {e}")
        return f"Error: {e}", 500


@app.route('/how-it-works/lifestyle')
def how_it_works_lifestyle():
    """Telegram Mini App - Как это работает (Лайфстайл)"""
    try:
        return render_template('how-it-works-lifestyle.html')
    except Exception as e:
        print(f"Error loading how-it-works lifestyle: {e}")
        return f"Error: {e}", 500


@app.route('/how-it-works/creative')
def how_it_works_creative():
    """Telegram Mini App - Как это работает (Творчество)"""
    try:
        return render_template('how-it-works-creative.html')
    except Exception as e:
        print(f"Error loading how-it-works creative: {e}")
        return f"Error: {e}", 500


@app.route('/how-it-works/socials')
def how_it_works_socials():
    """Telegram Mini App - Как это работает (Соцсети)"""
    try:
        return render_template('how-it-works-socials.html')
    except Exception as e:
        print(f"Error loading how-it-works socials: {e}")
        return f"Error: {e}", 500


@app.route('/luca/settings')
def luca_settings():
    """Telegram Mini App - Настройки Luca"""
    user_id = request.args.get('user_id', '')
    return render_template('luca_settings.html', user_id=user_id)


@app.route('/silas/settings')
def silas_settings():
    """Telegram Mini App - Настройки Silas"""
    user_id = request.args.get('user_id', '')
    return render_template('silas_settings.html', user_id=user_id)


# Удалено: Настройки голоса Titus больше не нужны


@app.route('/luca/settings/save', methods=['POST'])
def luca_settings_save():
    """API для сохранения настроек Luca в Redis"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        success = redis_db.set_luca_settings(
            user_id=int(user_id),
            character=data.get('character', 'soul'),
            voice_enabled=data.get('voice_enabled', False)
        )
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Redis not available'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/luca/settings/load', methods=['GET'])
def luca_settings_load():
    """API для загрузки настроек Luca из Redis"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        settings = redis_db.get_luca_settings(int(user_id))
        return jsonify({'success': True, 'settings': settings})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== SILAS SETTINGS ==========

@app.route('/silas/settings/save', methods=['POST'])
def silas_settings_save():
    """API для сохранения настроек Silas"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        # Сохраняем в Redis кэш
        redis_db.set_silas_settings_cache(
            user_id=int(user_id),
            duration=data.get('duration', 30),
            voice_enabled=data.get('voice_enabled', False),
            mood=data.get('mood', ''),
            custom_mood=data.get('custom_mood', '')
        )
        
        return jsonify({'success': True})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/silas/settings/load', methods=['GET'])
def silas_settings_load():
    """API для загрузки настроек Silas"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        # Пробуем из Redis кэша
        settings = redis_db.get_silas_settings_cache(int(user_id))
        
        if not settings:
            # Дефолтные настройки
            settings = {
                'duration': 30,
                'voice_enabled': False,
                'mood': '',
                'custom_mood': ''
            }
        
        return jsonify({'success': True, 'settings': settings})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== TITUS SETTINGS ==========

# Удалено: API сохранения настроек голоса Titus


# Удалено: API загрузки настроек голоса Titus


# ========== MAGIC WEBAPP ==========

@app.route('/magic/horoscope')
def magic_horoscope():
    """Telegram Mini App - Гороскоп"""
    user_id = request.args.get('user_id', '')
    return render_template('magic_horoscope.html', user_id=user_id)


@app.route('/magic/tarot')
def magic_tarot():
    """Telegram Mini App - Таро"""
    user_id = request.args.get('user_id', '')
    return render_template('magic_tarot.html', user_id=user_id)


@app.route('/magic/divination')
def magic_divination():
    """Telegram Mini App - Гадания"""
    user_id = request.args.get('user_id', '')
    return render_template('magic_divination.html', user_id=user_id)


@app.route('/magic/numerology')
def magic_numerology():
    """Telegram Mini App - Нумерология"""
    user_id = request.args.get('user_id', '')
    return render_template('magic_numerology.html', user_id=user_id)


@app.route('/magic/moon')
def magic_moon():
    """Telegram Mini App - Лунный календарь"""
    user_id = request.args.get('user_id', '')
    return render_template('magic_moon.html', user_id=user_id)


@app.route('/magic/rituals')
def magic_rituals():
    """Telegram Mini App - Ритуалы дня"""
    user_id = request.args.get('user_id', '')
    return render_template('magic_rituals.html', user_id=user_id)


@app.route('/magic/horoscope/save', methods=['POST'])
def magic_horoscope_save():
    """Сохранить профиль гороскопа"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400

        birth_date = data.get('birth_date')
        if not birth_date:
            return jsonify({'success': False, 'error': 'birth_date required'}), 400

        # Конвертация даты если передана
        if birth_date:
            if not isinstance(birth_date, str) or not birth_date.strip():
                return jsonify({'success': False, 'error': 'Неверный формат даты рождения'}), 400
            try:
                birth_date = datetime.strptime(birth_date.strip(), "%Y-%m-%d").date()
            except Exception:
                return jsonify({'success': False, 'error': 'Неверный формат даты рождения'}), 400

        ensure_pool_initialized()
        run_async(postgres_db.save_magic_horoscope_profile(
            user_id=int(user_id),
            birth_date=birth_date,
            birth_time=data.get('birth_time'),
            birth_place=data.get('birth_place'),
            notify_time=data.get('notify_time'),
            tz_offset=int(data.get('tz_offset', 0))
        ))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/horoscope/load', methods=['GET'])
def magic_horoscope_load():
    """Загрузить профиль гороскопа"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400

        ensure_pool_initialized()
        profile = run_async(postgres_db.get_magic_horoscope_profile(int(user_id)))
        return jsonify({'success': True, 'profile': profile or {}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/horoscope/predict', methods=['POST'])
def magic_horoscope_predict():
    """Получить прогноз"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        ftype = data.get('type', 'today')
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400

        ensure_pool_initialized()
        profile = run_async(postgres_db.get_magic_horoscope_profile(int(user_id)))
        if not profile:
            return jsonify({'success': False, 'error': 'profile not found'}), 400

        zodiac = zodiac_sign(profile.get('birth_date', ''))
        type_map = {
            "today": "Гороскоп на сегодня",
            "week": "Прогноз на неделю",
            "compat": "Совместимость знаков",
            "finance": "Финансовый гороскоп",
            "love": "Любовный гороскоп",
            "natal": "Натальная карта"
        }
        prompt = (
            f"{type_map.get(ftype, 'Гороскоп')}. "
            f"Знак зодиака: {zodiac}. "
            f"Дата рождения: {profile.get('birth_date')}. "
            f"Время рождения: {profile.get('birth_time')}. "
            f"Место рождения: {profile.get('birth_place')}."
        )

        messages = [
            {"role": "system", "content": HOROSCOPE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        text, _ = run_async(ask(messages, model="anthropic/claude-sonnet-4.5"))
        ensure_pool_initialized()
        run_async(postgres_db.save_magic_horoscope_log(int(user_id), ftype, text))
        return jsonify({'success': True, 'text': text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/tarot/spread', methods=['POST'])
def magic_tarot_spread():
    """Расклад Таро"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        spread_type = data.get('type', 'card_day')
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400

        spread_map = {
            "card_day": "Сделай расклад «Карта дня» (1 карта).",
            "yes_no": "Сделай расклад «Да/Нет» (3 карты).",
            "celtic": "Сделай расклад «Кельтский крест» (10 карт)."
        }
        cards_count = {"card_day": 1, "yes_no": 3, "celtic": 10}.get(spread_type, 1)
        cards = draw_tarot_cards(cards_count)
        card_names = ", ".join(c["name"] for c in cards)
        messages = [
            {"role": "system", "content": TAROT_SYSTEM_PROMPT},
            {"role": "user", "content": f"{spread_map.get(spread_type, 'Сделай расклад Таро.')} Карты: {card_names}."}
        ]
        text, _ = run_async(ask(messages, model="anthropic/claude-sonnet-4.5"))
        ensure_pool_initialized()
        run_async(postgres_db.save_magic_tarot_log(
            user_id=int(user_id),
            spread_type=spread_type,
            question=None,
            image_used=False,
            result_text=text
        ))
        return jsonify({'success': True, 'text': text, 'cards': cards})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/tarot/question', methods=['POST'])
def magic_tarot_question():
    """Вопрос Таро"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        question = data.get('question', '').strip()
        if not user_id or not question:
            return jsonify({'success': False, 'error': 'user_id and question required'}), 400

        cards = draw_tarot_cards(3)
        card_names = ", ".join(c["name"] for c in cards)
        messages = [
            {"role": "system", "content": TAROT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Вопрос: {question}. Сделай расклад и дай толкование. Карты: {card_names}."}
        ]
        text, _ = run_async(ask(messages, model="anthropic/claude-sonnet-4.5"))
        ensure_pool_initialized()
        run_async(postgres_db.save_magic_tarot_log(
            user_id=int(user_id),
            spread_type="question",
            question=question,
            image_used=False,
            result_text=text
        ))
        return jsonify({'success': True, 'text': text, 'cards': cards})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/tarot/photo', methods=['POST'])
def magic_tarot_photo():
    """Анализ фото расклада"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        image = data.get('image')
        if not user_id or not image:
            return jsonify({'success': False, 'error': 'user_id and image required'}), 400

        text = run_async(analyze_image_with_prompt(image, TAROT_PHOTO_PROMPT))
        ensure_pool_initialized()
        run_async(postgres_db.save_magic_tarot_log(
            user_id=int(user_id),
            spread_type="photo",
            question=None,
            image_used=True,
            result_text=text
        ))
        return jsonify({'success': True, 'text': text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/divination/photo', methods=['POST'])
def magic_divination_photo():
    """Анализ фото для гаданий"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        image = data.get('image')
        dtype = data.get('type', 'palm')
        if not user_id or not image:
            return jsonify({'success': False, 'error': 'user_id and image required'}), 400

        prompt_map = {
            "palm": PALM_PROMPT,
            "face": FACE_PROMPT,
            "coffee": COFFEE_PROMPT
        }
        prompt = prompt_map.get(dtype, PALM_PROMPT)
        text = run_async(analyze_image_with_prompt(image, prompt))
        ensure_pool_initialized()
        run_async(postgres_db.save_magic_divination_log(
            user_id=int(user_id),
            divination_type=dtype,
            question=None,
            image_used=True,
            result_text=text
        ))
        return jsonify({'success': True, 'text': text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/divination/ask', methods=['POST'])
def magic_divination_ask():
    """Вопрос для гаданий"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        mode = data.get('mode', 'crystal')
        question = data.get('question', '').strip()
        if not user_id or not question:
            return jsonify({'success': False, 'error': 'user_id and question required'}), 400

        prompt_map = {
            "crystal": CRYSTAL_PROMPT,
            "candle": CANDLE_PROMPT
        }
        messages = [
            {"role": "system", "content": prompt_map.get(mode, CRYSTAL_PROMPT)},
            {"role": "user", "content": f"Вопрос: {question}"}
        ]
        text, _ = run_async(ask(messages, model="anthropic/claude-sonnet-4.5"))
        ensure_pool_initialized()
        run_async(postgres_db.save_magic_divination_log(
            user_id=int(user_id),
            divination_type=mode,
            question=question,
            image_used=False,
            result_text=text
        ))
        return jsonify({'success': True, 'text': text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/numerology/save', methods=['POST'])
def magic_numerology_save():
    """Сохранить профиль нумерологии"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400

        full_name = (data.get('full_name') or '').strip()
        # Конвертация даты если передана
        birth_date = data.get('birth_date')
        if not full_name and not birth_date:
            return jsonify({'success': False, 'error': 'full_name or birth_date required'}), 400
        if birth_date:
            if not isinstance(birth_date, str) or not birth_date.strip():
                return jsonify({'success': False, 'error': 'Неверный формат даты рождения'}), 400
            try:
                birth_date = datetime.strptime(birth_date.strip(), "%Y-%m-%d").date()
            except Exception:
                return jsonify({'success': False, 'error': 'Неверный формат даты рождения'}), 400

        ensure_pool_initialized()
        run_async(postgres_db.save_magic_numerology_profile(
            user_id=int(user_id),
            full_name=full_name or None,
            birth_date=birth_date
        ))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/numerology/load', methods=['GET'])
def magic_numerology_load():
    """Загрузить профиль нумерологии"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400

        ensure_pool_initialized()
        profile = run_async(postgres_db.get_magic_numerology_profile(int(user_id)))
        return jsonify({'success': True, 'profile': profile or {}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/numerology/calc', methods=['POST'])
def magic_numerology_calc():
    """Расчёты нумерологии"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        calc_type = data.get('type')
        partner_name = (data.get('partner_name') or '').strip()
        partner_date = data.get('partner_birth_date')
        if not user_id or not calc_type:
            return jsonify({'success': False, 'error': 'user_id and type required'}), 400

        ensure_pool_initialized()
        profile = run_async(postgres_db.get_magic_numerology_profile(int(user_id))) or {}
        full_name = profile.get('full_name') or ''
        birth_date = profile.get('birth_date')

        if calc_type in ("destiny", "name", "year", "karma") and (not full_name and not birth_date):
            return jsonify({'success': False, 'error': 'profile not found'}), 400

        meanings = {
            1: "Лидерство, инициатива, сила воли.",
            2: "Гармония, дипломатия, чувствительность.",
            3: "Творчество, общение, вдохновение.",
            4: "Стабильность, трудолюбие, порядок.",
            5: "Свобода, перемены, энергия.",
            6: "Забота, семья, ответственность.",
            7: "Интуиция, мудрость, анализ.",
            8: "Материальный успех, сила, власть.",
            9: "Гуманизм, завершение, сострадание.",
            11: "Мастер-число интуиции и вдохновения.",
            22: "Мастер-число строителя больших целей.",
            33: "Мастер-число служения и любви."
        }

        if calc_type == "destiny":
            num = destiny_number(birth_date)
            text = f"🔢 Число судьбы: {num}\n{meanings.get(num, '')}"
        elif calc_type == "name":
            num = name_number(full_name)
            text = f"🔢 Число имени: {num}\n{meanings.get(num, '')}"
        elif calc_type == "day":
            num = day_number()
            text = f"🔢 Число дня: {num}\n{meanings.get(num, '')}"
        elif calc_type == "compat":
            if not partner_name and not partner_date:
                return jsonify({'success': False, 'error': 'partner data required'}), 400
            num1 = destiny_number(birth_date)
            num2 = destiny_number(partner_date) if partner_date else name_number(partner_name)
            comp = reduce_number(num1 + num2) if num1 and num2 else 0
            text = f"💑 Совместимость: {comp}\n{meanings.get(comp, '')}"
        elif calc_type == "year":
            num = personal_year_number(birth_date)
            text = f"📅 Персональный год: {num}\n{meanings.get(num, '')}"
        elif calc_type == "karma":
            num = karma_number(birth_date, full_name)
            text = f"🔮 Кармическое число: {num}\n{meanings.get(num, '')}"
        else:
            return jsonify({'success': False, 'error': 'unknown type'}), 400

        ensure_pool_initialized()
        run_async(postgres_db.save_magic_numerology_log(int(user_id), calc_type, text))
        return jsonify({'success': True, 'text': text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/moon/today', methods=['GET'])
def magic_moon_today():
    """Лунный день"""
    try:
        info = moon_phase_info()
        advice = moon_day_advice(info["name"])
        text = (
            f"🌙 Фаза луны: {info['name']}\n"
            f"{advice['good']}\n"
            f"{advice['bad']}\n"
            "\n💇 Стрижка: аккуратно, без резких перемен.\n"
            "💅 Красота: мягкие уходовые процедуры.\n"
            "🌱 Дела: лучше планировать и завершать."
        )
        return jsonify({'success': True, 'text': text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/moon/month', methods=['GET'])
def magic_moon_month():
    """Календарь на месяц"""
    try:
        grid = moon_month_grid()
        text = "📅 Лунный календарь (ключевые фазы)\n\n" + moon_month_calendar()
        return jsonify({'success': True, 'text': text, 'grid': grid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/rituals/get', methods=['POST'])
def magic_rituals_get():
    """Получить ритуал"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        ritual_type = data.get('type')
        if not user_id or not ritual_type:
            return jsonify({'success': False, 'error': 'user_id and type required'}), 400

        ritual = RITUALS.get(ritual_type)
        if not ritual:
            return jsonify({'success': False, 'error': 'ritual not found'}), 404
        text = f"{ritual['title']}\n\n{ritual['text']}"
        ensure_pool_initialized()
        run_async(postgres_db.save_magic_ritual_log(int(user_id), ritual_type, text))
        return jsonify({'success': True, 'text': text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/magic/history/<string:kind>', methods=['GET'])
def magic_history(kind: str):
    """История запросов Магии"""
    try:
        user_id = request.args.get('user_id')
        kind_filter = request.args.get('type')
        date_from_raw = request.args.get('from')
        date_to_raw = request.args.get('to')
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        date_from = None
        date_to = None
        try:
            if date_from_raw:
                date_from = datetime.strptime(date_from_raw, "%Y-%m-%d").date()
            if date_to_raw:
                date_to = datetime.strptime(date_to_raw, "%Y-%m-%d").date()
        except Exception:
            date_from = None
            date_to = None
        ensure_pool_initialized()
        items = run_async(postgres_db.list_magic_history(
            int(user_id),
            kind,
            limit=30,
            kind_filter=kind_filter or None,
            date_from=date_from or None,
            date_to=date_to or None
        ))
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== SILAS PAIR SESSIONS ==========

@app.route('/silas/pair')
def silas_pair():
    """Telegram Mini App - Парная сессия Silas"""
    user_id = request.args.get('user_id', '')
    action = request.args.get('action', 'menu')  # menu, create, join
    return render_template('silas_pair.html', user_id=user_id, action=action)


@app.route('/silas/pair/join')
def silas_pair_join_page():
    """Telegram Mini App - Страница присоединения к парной сессии"""
    user_id = request.args.get('user_id', '')
    code = request.args.get('code', '').upper()
    return render_template('silas_pair_join.html', user_id=user_id, code=code)


@app.route('/silas/pair/session')
def silas_pair_session():
    """Telegram Mini App - Страница парной сессии (чат)"""
    user_id = request.args.get('user_id', '')
    code = request.args.get('code', '').upper()
    
    # Получаем данные сессии с именами участников
    try:
        ensure_pool_initialized()
        loop = get_or_create_loop()
        session_data = loop.run_until_complete(get_pair_session_with_names(code))
        
        # Передаём имена в шаблон
        user1_name = session_data.get('user1_name', 'Участник 1') if session_data else 'Участник 1'
        user2_name = session_data.get('user2_name', 'Участник 2') if session_data else 'Участник 2'
    except Exception as e:
        print(f"Error getting session names: {e}")
        # Fallback на дефолтные имена при ошибке
        user1_name = 'Участник 1'
        user2_name = 'Участник 2'
    
    return render_template('silas_pair_session.html', 
        user_id=user_id, 
        code=code,
        user1_name=user1_name,
        user2_name=user2_name
    )


@app.route('/silas/pair/create', methods=['POST'])
def silas_pair_create():
    """API для создания парной сессии"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        topic = data.get('topic')
        description = data.get('description', '')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        if not topic:
            return jsonify({'success': False, 'error': 'topic required'}), 400
        
        # Убеждаемся что пул инициализирован
        ensure_pool_initialized()
        
        # Используем глобальный loop
        loop = get_or_create_loop()
        
        existing = loop.run_until_complete(get_user_pair_session(int(user_id)))
        if existing:
            return jsonify({
                'success': False, 
                'error': 'У вас уже есть активная сессия',
                'code': existing.get('code')
            }), 400
        
        # Создаём новую сессию
        code = loop.run_until_complete(create_pair_session(
            uid=int(user_id),
            topic=topic,
            description=description
        ))
        
        # Кэшируем в Redis
        redis_db.set_pair_session_cache(code, {
            'topic': topic,
            'user1_id': int(user_id),
            'user1_description': description,
            'status': 'waiting'
        })
        redis_db.set_user_pair_session(int(user_id), code)
        
        return jsonify({'success': True, 'code': code})
        # НЕ закрываем loop - используется глобальный loop
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/silas/pair/join', methods=['POST'])
def silas_pair_join():
    """API для присоединения к парной сессии"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        code = data.get('code', '').upper()
        description = data.get('description', '')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        if not code:
            return jsonify({'success': False, 'error': 'code required'}), 400
        
        ensure_pool_initialized()
        loop = get_or_create_loop()
        
        # Проверяем/создаём пользователя перед присоединением
        # Используем get_user и create_user из postgres_db (импортированы выше)
        from database.postgres_db import get_user as pg_get_user, create_user as pg_create_user
        user = loop.run_until_complete(pg_get_user(int(user_id)))
        if not user:
            # Создаём пользователя с минимальными данными
            loop.run_until_complete(pg_create_user(
                uid=int(user_id),
                uname=f"user_{user_id}",
                fname="Участник"
            ))
            print(f"✅ Создан пользователь {user_id} для парной сессии")
        
        result = loop.run_until_complete(join_pair_session(
            uid=int(user_id),
            code=code,
            description=description
        ))
        
        if result['success']:
            # Обновляем кэш в Redis
            session = loop.run_until_complete(get_pair_session(code))
            if session:
                redis_db.set_pair_session_cache(code, session)
            redis_db.set_user_pair_session(int(user_id), code)
            
            return jsonify({'success': True, 'session_id': result['session_id']})
        else:
            return jsonify({'success': False, 'error': result['error']}), 400
        # НЕ закрываем loop - используется глобальный loop
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/silas/pair/status', methods=['GET'])
def silas_pair_status():
    """API для получения статуса парной сессии"""
    try:
        user_id = request.args.get('user_id')
        code = request.args.get('code', '').upper()
        
        if not user_id and not code:
            return jsonify({'success': False, 'error': 'user_id or code required'}), 400
        
        # Если есть код — ищем по коду
        if code:
            session = redis_db.get_pair_session_cache(code)
            if session:
                return jsonify({'success': True, 'session': session})
        
        # Если нет — ищем по user_id
        if user_id:
            code = redis_db.get_user_pair_session(int(user_id))
            if code:
                session = redis_db.get_pair_session_cache(code)
                if session:
                    session['code'] = code
                    return jsonify({'success': True, 'session': session})
        
        return jsonify({'success': True, 'session': None})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/silas/pair/cancel', methods=['POST'])
def silas_pair_cancel():
    """API для отмены парной сессии"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        code = data.get('code', '').upper()
        
        if not user_id or not code:
            return jsonify({'success': False, 'error': 'user_id and code required'}), 400
        
        ensure_pool_initialized()
        loop = get_or_create_loop()
        
        success = loop.run_until_complete(cancel_pair_session(code, int(user_id)))
        
        if success:
            redis_db.delete_pair_session_cache(code)
            redis_db.clear_user_pair_session(int(user_id))
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Не удалось отменить сессию'}), 400
        # НЕ закрываем loop - используется глобальный loop
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pair-sessions/<int:user_id>', methods=['GET'])
def get_user_pair_sessions(user_id):
    """Получить все парные сессии пользователя"""
    try:
        ensure_pool_initialized()
        loop = get_or_create_loop()
        
        sessions = loop.run_until_complete(get_all_user_pair_sessions(user_id))
        
        # Форматируем данные для фронтенда
        formatted_sessions = []
        for session in sessions:
            # Определяем статус для отображения
            status_display = {
                'waiting': 'Ожидает партнёра',
                'active': 'Активная',
                'ended': 'Завершённая'
            }.get(session.get('status', ''), 'Неизвестно')
            
            # Форматируем дату
            created_at = session.get('created_at')
            if created_at:
                if isinstance(created_at, str):
                    date_str = created_at[:10]  # YYYY-MM-DD
                else:
                    date_str = str(created_at)[:10]
            else:
                date_str = '—'
            
            formatted_sessions.append({
                'id': session.get('id'),
                'code': session.get('code'),
                'topic': session.get('topic'),
                'status': session.get('status'),
                'status_display': status_display,
                'created_at': date_str,
                'role': session.get('role', 'unknown')
            })
        
        return jsonify({'success': True, 'sessions': formatted_sessions})
        
    except Exception as e:
        print(f"Error in get_user_pair_sessions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pair-sessions/<int:session_id>', methods=['DELETE'])
def delete_pair_session(session_id):
    """Удалить парную сессию"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        ensure_pool_initialized()
        loop = get_or_create_loop()
        
        success = loop.run_until_complete(delete_pair_session_by_id(session_id, int(user_id)))
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Сессия не найдена или у вас нет прав на удаление'}), 404
            
    except Exception as e:
        print(f"Error in delete_pair_session: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pair-sessions/clear/<int:user_id>', methods=['DELETE'])
def clear_all_pair_sessions(user_id):
    """Удалить все парные сессии пользователя"""
    try:
        ensure_pool_initialized()
        loop = get_or_create_loop()
        
        deleted_count = loop.run_until_complete(delete_all_user_pair_sessions(user_id))
        
        return jsonify({'success': True, 'deleted_count': deleted_count})
        
    except Exception as e:
        print(f"Error in clear_all_pair_sessions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/images/settings')
def images_settings():
    """Telegram Mini App - Настройки генерации изображений"""
    try:
        return render_template('images_settings.html')
    except Exception as e:
        print(f"Error loading images settings: {e}")
        return f"Error: {e}", 500


@app.route('/creativity/video')
def creativity_video_settings():
    """Telegram Mini App - Настройки видео (отдельная страница)"""
    try:
        return render_template('video_settings.html')
    except Exception as e:
        print(f"Error loading video settings: {e}")
        return f"Error: {e}", 500


@app.route('/creativity/photo')
def creativity_photo_settings():
    """Telegram Mini App - Настройки фото (отдельная страница)"""
    try:
        return render_template('photo_settings.html')
    except Exception as e:
        print(f"Error loading photo settings: {e}")
        return f"Error: {e}", 500


@app.route('/creativity/blogger')
def creativity_blogger_settings():
    """Telegram Mini App - Настройки для блогеров (отдельная страница)"""
    try:
        return render_template('blogger_settings.html')
    except Exception as e:
        print(f"Error loading blogger settings: {e}")
        return f"Error: {e}", 500


@app.route('/creativity/creative')
def creativity_creative_settings():
    """Telegram Mini App - Настройки креатива (отдельная страница)"""
    try:
        return render_template('creative_settings.html')
    except Exception as e:
        print(f"Error loading creative settings: {e}")
        return f"Error: {e}", 500


@app.route('/creativity/video-notes')
def creativity_video_notes():
    """Telegram Mini App - Мои конспекты (видео-анализ)"""
    try:
        return render_template('video_notes.html')
    except Exception as e:
        print(f"Error loading video notes: {e}")
        return f"Error: {e}", 500


@app.route('/api/video-notes/list/<int:user_id>')
def api_video_notes_list(user_id: int):
    """Список конспектов пользователя"""
    try:
        ensure_pool_initialized()
        loop = get_or_create_loop()
        from database.postgres_db import list_video_notes
        notes = loop.run_until_complete(list_video_notes(user_id))
        return jsonify({"notes": notes})
    except Exception as e:
        print(f"Error in api_video_notes_list: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/video-notes/get/<int:user_id>/<int:note_id>')
def api_video_notes_get(user_id: int, note_id: int):
    """Получить один конспект"""
    try:
        ensure_pool_initialized()
        loop = get_or_create_loop()
        from database.postgres_db import get_video_note
        note = loop.run_until_complete(get_video_note(user_id, note_id))
        if not note:
            return jsonify({"error": "not found"}), 404
        return jsonify({"note": note})
    except Exception as e:
        print(f"Error in api_video_notes_get: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/video-notes/delete', methods=['POST'])
def api_video_notes_delete():
    """Удалить конспект"""
    try:
        ensure_pool_initialized()
        loop = get_or_create_loop()
        from database.postgres_db import delete_video_note
        data = request.get_json() or {}
        user_id = int(data.get("user_id"))
        note_id = int(data.get("note_id"))
        ok = loop.run_until_complete(delete_video_note(user_id, note_id))
        return jsonify({"success": bool(ok)})
    except Exception as e:
        print(f"Error in api_video_notes_delete: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/image-settings/<int:user_id>')
def get_image_settings_api(user_id: int):
    """Получить настройки изображений и баланс"""
    try:
        ensure_pool_initialized()
        loop = get_or_create_loop()
        from database.postgres_db import get_image_settings
        from database.postgres_db import get_available_stars
        
        settings = loop.run_until_complete(get_image_settings(user_id))
        balance = loop.run_until_complete(get_available_stars(user_id))
        
        return jsonify({
            "balance": balance,
            "create_model": settings.get("create_model", "gpt-image-1-mini"),
            "create_price": settings.get("create_price", 50),
            "upscale_model": settings.get("upscale_model", "auto_max"),
            "upscale_price": settings.get("upscale_price", 350),
            "edit_model": settings.get("edit_model", "gpt-image-1.5"),
            "edit_price": settings.get("edit_price", 120),
            # Расширяемая часть под новые функции (видео/обработка/стили/инструменты)
            "extra_settings": settings.get("extra_settings", {}) or {}
        })
    except Exception as e:
        print(f"❌ [Image Settings] Error in get_image_settings_api: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/image-settings/save', methods=['POST'])
def save_image_settings_api():
    """Сохранить настройки изображений"""
    try:
        ensure_pool_initialized()
        loop = get_or_create_loop()
        from database.postgres_db import get_image_settings, save_image_settings
        
        data = request.get_json()
        logger.info(f"🔵 [Image Settings] Received data: {data}")
        
        if not data:
            logger.error("❌ [Image Settings] No JSON data")
            return jsonify({"success": False, "error": "No JSON data"}), 400
            
        user_id = data.get("user_id")
        action = data.get("action")  # create, upscale, edit
        model = data.get("model")
        price = data.get("price")
        extra_patch = data.get("extra_settings")  # dict: merge into extra_settings
        
        logger.info(f"🔵 [Image Settings] Parsed: user_id={user_id} (type: {type(user_id).__name__}), action={action}, model={model}, price={price} (type: {type(price).__name__})")
        
        # Преобразуем user_id в int если это строка
        if isinstance(user_id, str):
            try:
                user_id = int(user_id)
            except ValueError:
                logger.error(f"❌ [Image Settings] Invalid user_id: {user_id}")
                return jsonify({"success": False, "error": "Invalid user_id"}), 400
        
        # Преобразуем price в int если это строка
        if isinstance(price, str):
            try:
                price = int(price)
            except ValueError:
                logger.error(f"❌ [Image Settings] Invalid price: {price}")
                return jsonify({"success": False, "error": "Invalid price"}), 400
        
        # Вариант A: сохранить стандартную секцию (create/upscale/edit)
        is_standard_section = action in ("create", "upscale", "edit")

        # Вариант B: сохранить расширенные настройки (extra_settings) без модели/цены
        if not is_standard_section and not isinstance(extra_patch, dict):
            logger.error(f"❌ [Image Settings] Missing fields: user_id={user_id}, action={action}, model={model}, price={price}, extra_settings={type(extra_patch).__name__}")
            return jsonify({"success": False, "error": "Missing fields"}), 400

        if is_standard_section and not all([user_id, action, model, price is not None]):
            logger.error(f"❌ [Image Settings] Missing fields: user_id={user_id}, action={action}, model={model}, price={price}")
            return jsonify({"success": False, "error": "Missing fields"}), 400
        
        # Получаем текущие настройки
        logger.info(f"🔵 [Image Settings] Getting current settings for user {user_id}")
        current = loop.run_until_complete(get_image_settings(user_id))
        logger.info(f"🔵 [Image Settings] Current settings: {current}")
        
        # Обновляем стандартную секцию
        if is_standard_section:
            current[f"{action}_model"] = model
            current[f"{action}_price"] = price

        def deep_merge(dst: dict, src: dict) -> dict:
            """Глубокое merge для nested extra_settings (чтобы не затирать photo.*)."""
            for k, v in (src or {}).items():
                if isinstance(v, dict) and isinstance(dst.get(k), dict):
                    dst[k] = deep_merge(dst.get(k, {}), v)
                else:
                    dst[k] = v
            return dst

        # Обновляем расширенные настройки (merge)
        if isinstance(extra_patch, dict) and extra_patch:
            existing_extra = current.get("extra_settings") or {}
            if not isinstance(existing_extra, dict):
                existing_extra = {}
            existing_extra = deep_merge(existing_extra, extra_patch)
            current["extra_settings"] = existing_extra
        
        logger.info(f"🔵 [Image Settings] Saving settings: {current}")
        # Сохраняем
        loop.run_until_complete(save_image_settings(user_id, current))
        
        logger.info(f"✅ [Image Settings] Settings saved successfully for user {user_id}")
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"❌ [Image Settings] Error in save_image_settings_api: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


def _build_user_response(user_id: int):
    """Собрать данные пользователя для WebApp"""
    ensure_pool_initialized()
    loop = get_or_create_loop()

    # Получаем пользователя или создаём, если отсутствует
    user = loop.run_until_complete(get_user(user_id))
    if not user:
        loop.run_until_complete(
            create_user(uid=user_id, uname=f"user_{user_id}", fname="Пользователь")
        )
        user = loop.run_until_complete(get_user(user_id))

    # Получаем подписку
    subscription = loop.run_until_complete(get_subscription(user_id))

    # Получаем доступные звёзды (из подписки или бонусные)
    stars = loop.run_until_complete(get_available_stars(user_id))

    # Формируем ответ
    response = {
        'user_id': user['user_id'],
        'username': user.get('username'),
        'first_name': user.get('first_name'),
        'stars': stars,        # основной ключ
        'balance': stars,      # совместимость со старыми клиентами
        'total_used': user.get('total_used', 0),
        'total_requests': user.get('total_requests', 0),
        'subscription': None
    }

    # Добавляем информацию о подписке если есть
    if subscription:
        response['subscription'] = {
            'type': subscription.get('type'),
            'is_active': bool(subscription.get('is_active')),
            'expires_at': subscription.get('expires_at'),
            'stars_limit': subscription.get('stars_limit', 0),
            'stars_used': subscription.get('stars_used', 0)
        }

    return response


@app.route('/api/user/<int:user_id>')
def api_user(user_id):
    """API для получения данных пользователя"""
    try:
        return jsonify(_build_user_response(user_id))
    except Exception as e:
        print(f"Error in api_user: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user', methods=['GET'])
def api_user_query():
    """API для получения данных пользователя (query-параметр)"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': 'user_id required'}), 400
        return jsonify(_build_user_response(int(user_id)))
    except Exception as e:
        print(f"Error in api_user_query: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/robokassa/result', methods=['POST', 'GET'])
def robokassa_result():
    """Webhook для обработки ResultURL от Robokassa"""
    try:
        from utils.robokassa import verify_result_signature
        from handlers.subscription import process_successful_payment
        
        # Получаем параметры
        out_sum = request.args.get('OutSum') or request.form.get('OutSum')
        inv_id = request.args.get('InvId') or request.form.get('InvId')
        signature = request.args.get('SignatureValue') or request.form.get('SignatureValue')
        shp_type = request.args.get('Shp_type') or request.form.get('Shp_type')
        shp_user = request.args.get('Shp_user') or request.form.get('Shp_user')
        
        if not all([out_sum, inv_id, signature, shp_type, shp_user]):
            return 'ERROR: Missing parameters', 400
        
        # Проверяем подпись
        if not verify_result_signature(out_sum, inv_id, shp_type, shp_user, signature):
            return 'ERROR: Invalid signature', 403
        
        # Обрабатываем оплату
        ensure_pool_initialized()
        loop = get_or_create_loop()
        try:
            loop.run_until_complete(process_successful_payment(int(inv_id), robokassa_id=int(inv_id)))
        except Exception as e:
            print(f"Error processing payment: {e}")
            import traceback
            traceback.print_exc()
        
        return f'OK{inv_id}'
        
    except Exception as e:
        print(f"Error in robokassa_result: {e}")
        import traceback
        traceback.print_exc()
        return f'ERROR: {str(e)}', 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
