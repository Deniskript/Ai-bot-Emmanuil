#!/usr/bin/env python3
"""
Веб-приложение для отображения диалогов
"""
from flask import Flask, render_template_string, render_template, abort, jsonify
import asyncio
from database.db import get_conversation, get_conversation_messages, get_user, get_subscription, DATABASE_PATH
import aiosqlite
import html
import re

app = Flask(__name__)

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
        # Получаем диалог и сообщения
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
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


@app.route('/api/user/<int:user_id>')
def api_user(user_id):
    """API для получения данных пользователя"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Получаем данные пользователя
        user = loop.run_until_complete(get_user(user_id))
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Получаем подписку
        subscription = loop.run_until_complete(get_subscription(user_id))
        
        # Формируем ответ
        response = {
            'user_id': user['user_id'],
            'username': user.get('username'),
            'first_name': user.get('first_name'),
            'tokens': user.get('tokens', 0),
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
