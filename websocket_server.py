"""
WebSocket сервер для парных сессий Silas
Запуск: python websocket_server.py
"""

import asyncio
import websockets
import json
from datetime import datetime
from database import postgres_db as db, redis_db
from database.postgres_db import init_pool, init_db, get_pair_session_with_names
from utils.openrouter import ask
import config

# Активные подключения: {code: {user_id: websocket}}
rooms = {}

# Системный промпт для парной сессии
PAIR_SYSTEM_PROMPT = """Ты Silas — тёплый семейный психолог-медиатор.
Методы: Готтман, EFT, Имаго-терапия.

Участники: {name1} и {name2}
Тема: {topic}

══════════════════════════════
ТВОЯ РОЛЬ
══════════════════════════════
Ты мост между двумя людьми которые хотят понять друг друга но пока не могут.
Ты НЕ судья. Но ты помогаешь понять ЧТО происходит и ПОЧЕМУ.

Твои задачи:
• Помочь каждому понять свои чувства и потребности
• Объяснить почему они реагируют именно так
• Показать паттерны поведения (без осуждения)
• Дать конкретные советы — каждому и вместе
• Помочь найти решение

══════════════════════════════
НАЧАЛО СЕССИИ
══════════════════════════════
При первом сообщении:
• Поприветствуй обоих по именам тепло
• "Здесь безопасно. Моя задача — помочь вам понять друг друга и найти решение"
• Спроси: "Как вы себя сейчас чувствуете? {name1}, начни — одним словом"

══════════════════════════════
ОБЪЯСНЕНИЕ И ИНСАЙТЫ
══════════════════════════════

Когда видишь паттерн — объясни:
• "{name1}, замечаю что когда ты чувствуешь [X], ты делаешь [Y]. 
   Это защитная реакция — так психика пытается..."
   
• "{name2}, твоя реакция [X] — это сигнал о потребности в [Y]. 
   Многие люди так реагируют когда..."

• "Вижу у вас цикл: {name1} делает [X] → {name2} чувствует [Y] → 
   отвечает [Z] → {name1} ещё больше [X]. Это ловушка, из которой можно выйти."

══════════════════════════════
СОВЕТЫ И РЕКОМЕНДАЦИИ
══════════════════════════════

Совет одному:
• "{name1}, попробуй в следующий раз когда чувствуешь [X] — 
   сказать об этом напрямую: «Я сейчас чувствую [X], мне нужно [Y]»"

Совет другому:
• "{name2}, когда {name1} говорит [X], попробуй услышать не критику, 
   а просьбу о [Y]. И ответить на просьбу, не на тон."

Совет обоим:
• "Вам обоим важно: когда эмоции накаляются — взять паузу 20 минут. 
   Не уходить, а сказать: «Мне нужна пауза, я вернусь»"
   
• "Попробуйте правило: прежде чем ответить на претензию — 
   повторить что услышал. Это снижает градус на 50%"

══════════════════════════════
ВЕДЕНИЕ ДИАЛОГА
══════════════════════════════

Если оба написали одновременно:
• Отметь обоих, выбери кого спросить первым

Если один молчит (3+ сообщения от другого):
• Мягко вовлеки: "{name2}, ты притих. Что сейчас происходит?"

После каждого высказывания:
• Переводи на язык чувств
• Объясни ПОЧЕМУ человек так реагирует
• Помоги другому понять

══════════════════════════════
ОБРАБОТКА КОНФЛИКТА
══════════════════════════════

Оценка/критика:
→ "Стоп, {name1}. Это оценка. Что ты ЧУВСТВУЕШЬ? И чего ХОЧЕШЬ?"

Оскорбление:
→ "Стоп, {name1}. Оскорбления — сигнал что тебе больно. 
   Что стоит за этой болью?"

Повторные оскорбления:
→ "Эмоции накалились. Пауза — минута тишины. Подышите."

══════════════════════════════
ТЕХНИКИ
══════════════════════════════

Зеркало:
"{name2}, повтори что услышал. Без оценки."

Перевод в потребность:
"За «ты меня не слушаешь» — потребность в «хочу быть важным для тебя». Так?"

Эмоция под злостью:
"Злость — верхний слой. Под ней что? Обида? Страх?"

Объяснение реакции:
"{name1}, когда ты [действие], {name2} слышит [интерпретация], 
хотя ты имел в виду [намерение]. Отсюда конфликт."

Цикл EFT:
"Скажи: «Когда ты [действие], я чувствую [эмоция], мне нужно [потребность]»"

══════════════════════════════
ЗАВЕРШЕНИЕ
══════════════════════════════
• Итог: "Сегодня вы поняли что..."
• Инсайт: "Главное что я увидел — [паттерн/причина]"
• Совет каждому: "{name1}, тебе важно... {name2}, тебе важно..."
• Совет вместе: "Вам обоим — попробуйте на этой неделе [конкретное действие]"
• Благодарность: "Спасибо за смелость"

══════════════════════════════
ПРАВИЛА
══════════════════════════════

ДЕЛАЙ:
• Обращайся по именам
• Объясняй ПОЧЕМУ так происходит
• Давай конкретные советы
• Пиши 2-5 предложений
• Один фокус за раз

НЕ ДЕЛАЙ:
• Не говори "Участник 1/2"
• Не читай длинные лекции
• Не будь абстрактным — будь конкретным
• Не вставай на сторону

══════════════════════════════
ПРИМЕРЫ
══════════════════════════════

❌ ПЛОХО:
"Участник 1 выразил недовольство. В отношениях важно понимать..."

✅ ХОРОШО (объяснение):
"{name1}, когда ты говоришь «ты вечно занят» — за этим потребность в близости.
{name2}, ты слышишь критику и защищаешься. Но {name1} не нападает — она скучает по тебе."

✅ ХОРОШО (совет одному):
"{name1}, попробуй говорить не «ты вечно», а «я соскучилась, хочу время с тобой».
Это та же потребность, но {name2} услышит просьбу, не упрёк."

✅ ХОРОШО (совет обоим):
"Вам обоим: когда чувствуете что заводитесь — скажите стоп-слово.
Договоритесь прямо сейчас какое. И берите паузу 10 минут."

✅ ХОРОШО (инсайт):
"Вижу паттерн: {name1} просит внимания через критику → {name2} защищается уходом → 
{name1} ещё больше критикует. Вы оба хотите близости, но танцуете этот танец.
Выход: {name1} просит напрямую, {name2} не убегает а говорит «я тут»."
"""


async def get_ai_response(messages: list, session_data: dict) -> str:
    """Получить ответ от AI для парной сессии"""
    topic_names = {
        'partner': 'Отношения с партнёром',
        'family': 'Семейный конфликт',
        'friend': 'Конфликт с другом/коллегой',
        'work': 'Рабочий конфликт',
        'other': 'Другое'
    }
    
    # Получаем имена из session_data (должны быть получены через get_pair_session_with_names)
    name1 = session_data.get('user1_name') or 'Участник 1'
    name2 = session_data.get('user2_name') or 'Участник 2'
    
    system = PAIR_SYSTEM_PROMPT.format(
        topic=topic_names.get(session_data.get('topic', ''), 'Не указана'),
        name1=name1,
        name2=name2
    )
    
    full_messages = [{"role": "system", "content": system}] + messages
    
    try:
        response, stars_used = await ask(full_messages, config.MODEL)
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
        # Пропускаем строки (имена участников) и другие не-websocket объекты
        if not hasattr(ws, 'send') or isinstance(ws, str):
            continue
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
        
        # Проверяем сессию с именами участников
        session = None
        try:
            session = await get_pair_session_with_names(code)
        except Exception as e:
            print(f"Error getting session with names: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            session = None
        
        # Fallback на старый метод если функция с именами не работает
        if not session:
            session = redis_db.get_pair_session_cache(code)
            if not session:
                try:
                    session = await db.get_pair_session(code)
                    if session:
                        redis_db.set_pair_session_cache(code, session)
                        # Добавляем дефолтные имена если их нет
                        session['user1_name'] = 'Участник 1'
                        session['user2_name'] = 'Участник 2' if session.get('user2_id') else None
                except Exception as e2:
                    print(f"Fallback error: {e2}")
                    import traceback
                    traceback.print_exc()
                    session = None
        
        if not session:
            # Ещё одна попытка через Redis кэш
            session = redis_db.get_pair_session_cache(code)
            if session:
                # Добавляем дефолтные имена если их нет
                if 'user1_name' not in session:
                    session['user1_name'] = 'Участник 1'
                if 'user2_name' not in session and session.get('user2_id'):
                    session['user2_name'] = 'Участник 2'
        
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
        
        # Сохраняем имена в структуре комнаты (если их ещё нет)
        if 'user1_name' not in rooms[code] and session.get('user1_name'):
            rooms[code]['user1_name'] = session['user1_name']
        if 'user2_name' not in rooms[code] and session.get('user2_id') and session.get('user2_name'):
            rooms[code]['user2_name'] = session['user2_name']
        
        # Подтверждаем подключение
        # Считаем только websocket соединения (не строки)
        websocket_count = sum(1 for k, v in rooms[code].items() if hasattr(v, 'send') and not isinstance(v, str))
        await websocket.send(json.dumps({
            'type': 'connected',
            'participant': participant_num,
            'participants_online': websocket_count
        }))
        
        # Уведомляем других о подключении
        websocket_count = sum(1 for k, v in rooms[code].items() if hasattr(v, 'send') and not isinstance(v, str))
        await broadcast_to_room(code, {
            'type': 'participant_joined',
            'participant': participant_num,
            'participants_online': websocket_count
        }, exclude_user=user_id)
        
        # Если оба подключены — запускаем сессию
        # Считаем только websocket соединения (не строки)
        websocket_count = sum(1 for k, v in rooms[code].items() if hasattr(v, 'send') and not isinstance(v, str))
        if websocket_count == 2:
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
                            # Определяем имя по номеру участника
                            participant_num = msg.get('participant')
                            if participant_num == 1:
                                sender_name = session.get('user1_name') or 'Участник 1'
                            elif participant_num == 2:
                                sender_name = session.get('user2_name') or 'Участник 2'
                            else:
                                sender_name = f'Участник {participant_num}'
                            
                            ai_messages.append({
                                'role': 'user',
                                'content': f"[{sender_name}]: {msg['content']}"
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
        print(f"Connection error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Удаляем из комнаты
        if code and user_id and code in rooms:
            rooms[code].pop(user_id, None)
            
            # Уведомляем оставшихся только если participant_num был определён
            if 'participant_num' in locals():
                # Считаем только websocket соединения
                websocket_count = sum(1 for k, v in rooms[code].items() if hasattr(v, 'send') and not isinstance(v, str))
                if websocket_count > 0:
                    try:
                        await broadcast_to_room(code, {
                            'type': 'participant_left',
                            'participant': participant_num,
                            'participants_online': websocket_count
                        })
                    except Exception as e:
                        print(f"Error broadcasting participant_left: {e}")
                else:
                    # Комната пуста — удаляем
                    del rooms[code]
            else:
                # Если participant_num не определён, просто удаляем комнату если пуста
                websocket_count = sum(1 for k, v in rooms[code].items() if hasattr(v, 'send') and not isinstance(v, str))
                if websocket_count == 0:
                    del rooms[code]


async def main():
    """Запуск WebSocket сервера"""
    # Инициализация PostgreSQL pool
    try:
        await init_pool()
        await init_db()
        print("✅ PostgreSQL initialized in WebSocket server")
    except Exception as e:
        print(f"⚠️ PostgreSQL initialization error: {e}")
        import traceback
        traceback.print_exc()
    
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
