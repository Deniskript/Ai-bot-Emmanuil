"""
WebSocket сервер для парных сессий Silas
Запуск: python websocket_server.py
"""

import asyncio
import websockets
import json
from datetime import datetime
from database import db, redis_db
from utils.openrouter import ask
import config

# Активные подключения: {code: {user_id: websocket}}
rooms = {}

# Системный промпт для парной сессии
PAIR_SYSTEM_PROMPT = """Ты — Soul, AI-психолог для парной терапии.

КОНТЕКСТ СЕССИИ:
Тема: {topic}
Участник 1 описал ситуацию: {description1}
Участник 2 описал ситуацию: {description2}

ТВОЯ РОЛЬ:
- Ты нейтральный медиатор, не принимаешь ничью сторону
- Помогаешь участникам услышать друг друга
- Переформулируешь обвинения в потребности
- Задаёшь уточняющие вопросы
- Направляешь к конструктивному диалогу

ПРАВИЛА:
1. Обращайся к участникам как "Участник 1" и "Участник 2"
2. После каждого сообщения участника — краткий отклик и вопрос другому
3. Если видишь эскалацию — мягко останови и переформулируй
4. Фокусируйся на чувствах и потребностях, не на обвинениях
5. Каждые 5-7 сообщений подводи мини-итог

ФОРМАТ ОТВЕТА:
- Короткие абзацы (2-3 предложения)
- Эмодзи для тёплой атмосферы
- Прямые вопросы участникам

Начни сессию с приветствия обоих участников и краткого описания того, как ты понял ситуацию."""


async def get_ai_response(messages: list, session_data: dict) -> str:
    """Получить ответ от AI для парной сессии"""
    topic_names = {
        'partner': 'Отношения с партнёром',
        'family': 'Семейный конфликт',
        'friend': 'Конфликт с другом/коллегой',
        'work': 'Рабочий конфликт',
        'other': 'Другое'
    }
    
    system = PAIR_SYSTEM_PROMPT.format(
        topic=topic_names.get(session_data.get('topic', ''), 'Не указана'),
        description1=session_data.get('user1_description', 'Не указано'),
        description2=session_data.get('user2_description', 'Не указано')
    )
    
    full_messages = [{"role": "system", "content": system}] + messages
    
    try:
        response, tokens = await ask(full_messages, config.MODEL)
        return response
    except Exception as e:
        print(f"AI Error: {e}")
        import traceback
        traceback.print_exc()
        return "Произошла ошибка. Пожалуйста, повторите сообщение."


async def broadcast_to_room(code: str, message: dict, exclude_user: int = None):
    """Отправить сообщение всем в комнате"""
    if code not in rooms:
        return
    
    for user_id, ws in rooms[code].items():
        if exclude_user and user_id == exclude_user:
            continue
        try:
            await ws.send(json.dumps(message))
        except Exception as e:
            print(f"Broadcast error to {user_id}: {e}")


async def handle_connection(websocket):
    """Обработка WebSocket подключения"""
    # В websockets 16.0 path не нужен, так как мы получаем данные через сообщения
    # path больше не используется в новой версии
    user_id = None
    code = None
    participant_num = 0
    
    try:
        # Ждём первое сообщение с авторизацией
        auth_msg = await asyncio.wait_for(websocket.recv(), timeout=30)
        auth_data = json.loads(auth_msg)
        
        if auth_data.get('type') != 'auth':
            await websocket.close(1008, "Auth required")
            return
        
        user_id = auth_data.get('user_id')
        code = auth_data.get('code', '').upper()
        
        if not user_id or not code:
            await websocket.close(1008, "Invalid auth data")
            return
        
        user_id = int(user_id)
        
        # Проверяем сессию
        session = redis_db.get_pair_session_cache(code)
        if not session:
            session = await db.get_pair_session(code)
            if session:
                redis_db.set_pair_session_cache(code, session)
        
        if not session:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': 'Сессия не найдена'
            }))
            await websocket.close(1008, "Session not found")
            return
        
        # Проверяем что пользователь участник сессии
        if user_id != session.get('user1_id') and user_id != session.get('user2_id'):
            await websocket.send(json.dumps({
                'type': 'error',
                'message': 'Вы не участник этой сессии'
            }))
            await websocket.close(1008, "Not a participant")
            return
        
        # Добавляем в комнату
        if code not in rooms:
            rooms[code] = {}
        rooms[code][user_id] = websocket
        
        # Определяем номер участника
        participant_num = 1 if user_id == session.get('user1_id') else 2
        
        # Подтверждаем подключение
        await websocket.send(json.dumps({
            'type': 'connected',
            'participant': participant_num,
            'participants_online': len(rooms[code])
        }))
        
        # Уведомляем других о подключении
        await broadcast_to_room(code, {
            'type': 'participant_joined',
            'participant': participant_num,
            'participants_online': len(rooms[code])
        }, exclude_user=user_id)
        
        # Если оба подключены — запускаем сессию
        if len(rooms[code]) == 2:
            # Загружаем историю или начинаем новую сессию
            history = redis_db.get_pair_chat_history(code)
            
            if not history:
                # Первый запуск — AI приветствует
                ai_response = await get_ai_response([], session)
                
                # Сохраняем в историю
                redis_db.add_pair_chat_message(code, {
                    'role': 'assistant',
                    'content': ai_response,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Отправляем всем
                await broadcast_to_room(code, {
                    'type': 'message',
                    'from': 'soul',
                    'content': ai_response,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                # Отправляем историю подключившемуся
                await websocket.send(json.dumps({
                    'type': 'history',
                    'messages': history
                }))
        
        # Основной цикл обработки сообщений
        async for message in websocket:
            try:
                data = json.loads(message)
                
                if data.get('type') == 'message':
                    content = data.get('content', '').strip()
                    if not content:
                        continue
                    
                    # Сохраняем сообщение пользователя
                    user_message = {
                        'role': 'user',
                        'participant': participant_num,
                        'content': content,
                        'timestamp': datetime.now().isoformat()
                    }
                    redis_db.add_pair_chat_message(code, user_message)
                    
                    # Отправляем всем участникам
                    await broadcast_to_room(code, {
                        'type': 'message',
                        'from': f'participant_{participant_num}',
                        'participant': participant_num,
                        'content': content,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # Получаем ответ AI
                    history = redis_db.get_pair_chat_history(code)
                    
                    # Формируем сообщения для AI
                    ai_messages = []
                    for msg in history:
                        if msg['role'] == 'assistant':
                            ai_messages.append({
                                'role': 'assistant',
                                'content': msg['content']
                            })
                        else:
                            ai_messages.append({
                                'role': 'user',
                                'content': f"[Участник {msg.get('participant', '?')}]: {msg['content']}"
                            })
                    
                    # Показываем что Soul печатает
                    await broadcast_to_room(code, {
                        'type': 'typing',
                        'from': 'soul'
                    })
                    
                    ai_response = await get_ai_response(ai_messages, session)
                    
                    # Сохраняем ответ AI
                    redis_db.add_pair_chat_message(code, {
                        'role': 'assistant',
                        'content': ai_response,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # Отправляем всем
                    await broadcast_to_room(code, {
                        'type': 'message',
                        'from': 'soul',
                        'content': ai_response,
                        'timestamp': datetime.now().isoformat()
                    })
                
                elif data.get('type') == 'ping':
                    await websocket.send(json.dumps({'type': 'pong'}))
                    
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"Message handling error: {e}")
                continue
    
    except asyncio.TimeoutError:
        print(f"Connection timeout for user {user_id}")
    except websockets.exceptions.ConnectionClosed:
        print(f"Connection closed for user {user_id}")
    except Exception as e:
        print(f"Connection error: {e}")
    finally:
        # Удаляем из комнаты
        if code and user_id and code in rooms:
            rooms[code].pop(user_id, None)
            
            # Уведомляем оставшихся
            if rooms[code]:
                await broadcast_to_room(code, {
                    'type': 'participant_left',
                    'participant': participant_num,
                    'participants_online': len(rooms[code])
                })
            else:
                # Комната пуста — удаляем
                del rooms[code]


async def main():
    """Запуск WebSocket сервера"""
    print("🚀 Starting WebSocket server on ws://0.0.0.0:8765")
    
    async with websockets.serve(
        handle_connection,
        "0.0.0.0",
        8765,
        ping_interval=30,
        ping_timeout=10
    ):
        print("✅ WebSocket server running")
        await asyncio.Future()  # Работает вечно


if __name__ == "__main__":
    asyncio.run(main())
