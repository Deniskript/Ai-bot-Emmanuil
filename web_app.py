#!/usr/bin/env python3
"""
Веб-приложение для отображения диалогов
"""
from flask import Flask, render_template_string, render_template, abort, jsonify, request
import asyncio
from database.db import get_conversation, get_conversation_messages, get_user, get_subscription, get_available_tokens, DATABASE_PATH
from database.postgres_db import init_pool, init_db, get_user_pair_session, create_pair_session, join_pair_session, get_pair_session, cancel_pair_session, get_user, create_user, get_all_user_pair_sessions, delete_pair_session_by_id, delete_all_user_pair_sessions, get_pair_session_with_names
from database import redis_db
import aiosqlite
import html
import re

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


@app.route('/api/user/<int:user_id>')
def api_user(user_id):
    """API для получения данных пользователя"""
    try:
        ensure_pool_initialized()
        loop = get_or_create_loop()
        
        # Получаем данные пользователя
        user = loop.run_until_complete(get_user(user_id))
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Получаем подписку
        subscription = loop.run_until_complete(get_subscription(user_id))
        
        # Получаем доступные токены (из подписки или бонусные)
        tokens = loop.run_until_complete(get_available_tokens(user_id))
        
        # Формируем ответ
        response = {
            'user_id': user['user_id'],
            'username': user.get('username'),
            'first_name': user.get('first_name'),
            'tokens': tokens,  # ✅ Правильный баланс с учетом подписки
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
                'tokens_limit': subscription.get('tokens_limit', 0),
                'tokens_used': subscription.get('tokens_used', 0)
            }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error in api_user: {e}")
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
