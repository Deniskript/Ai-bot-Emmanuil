"""
WebSocket сервер для парных сессий Silas
Оптимизирован для 1000+ одновременных пользователей
Запуск: python websocket_server.py
"""

import asyncio
import json
import logging
import time
from collections import OrderedDict
from datetime import datetime
from typing import Any, Optional

import websockets

import config
from database import postgres_db as db, redis_db
from database.postgres_db import get_pair_session_with_names, init_db, init_pool
from utils.openrouter import ask

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════
# КОНФИГУРАЦИЯ ДЛЯ ВЫСОКОЙ НАГРУЗКИ
# ═══════════════════════════════════════

MAX_ROOMS = 200                    # Максимум активных комнат
MAX_ROOM_AGE_MINUTES = 120         # Максимальный возраст комнаты без активности
API_TIMEOUT = 60.0                 # Таймаут на API запросы
API_SEMAPHORE = asyncio.Semaphore(30)  # Лимит одновременных API запросов
CLEANUP_INTERVAL = 300             # Интервал очистки (секунды)


# ═══════════════════════════════════════
# МЕНЕДЖЕР КОМНАТ С ЛИМИТАМИ
# ═══════════════════════════════════════

class Room:
    """Класс комнаты парной сессии"""
    
    def __init__(self, code: str, session_data: dict):
        self.code = code
        self.session_data = session_data
        self.connections: dict[int, Any] = {}  # user_id -> websocket
        self.user1_name: str = session_data.get('user1_name', 'Участник 1')
        self.user2_name: str = session_data.get('user2_name', 'Участник 2')
        self.created_at: float = time.time()
        self.last_activity: float = time.time()
    
    def update_activity(self) -> None:
        self.last_activity = time.time()
    
    def get_websocket_count(self) -> int:
        return len(self.connections)
    
    def is_expired(self, max_age_minutes: int = MAX_ROOM_AGE_MINUTES) -> bool:
        return (time.time() - self.last_activity) > (max_age_minutes * 60)


class RoomManager:
    """Менеджер комнат с лимитами и автоочисткой"""
    
    def __init__(self, max_rooms: int = MAX_ROOMS):
        self.rooms: OrderedDict[str, Room] = OrderedDict()
        self.max_rooms = max_rooms
        self._lock = asyncio.Lock()
    
    async def get_or_create(self, code: str, session_data: dict) -> Optional[Room]:
        """Получить или создать комнату"""
        async with self._lock:
            code = code.upper()
            
            if code in self.rooms:
                self.rooms.move_to_end(code)
                return self.rooms[code]
            
            if len(self.rooms) >= self.max_rooms:
                await self._cleanup_inactive()
            
            if len(self.rooms) >= self.max_rooms:
                logger.warning(f"[RoomManager] Max rooms limit reached ({self.max_rooms})")
                return None
            
            room = Room(code, session_data)
            self.rooms[code] = room
            logger.info(f"[RoomManager] Room created: {code}, total rooms: {len(self.rooms)}")
            return room
    
    async def get(self, code: str) -> Optional[Room]:
        """Получить комнату по коду"""
        async with self._lock:
            code = code.upper()
            if code in self.rooms:
                self.rooms.move_to_end(code)
                return self.rooms[code]
            return None
    
    async def remove(self, code: str) -> None:
        """Удалить комнату"""
        async with self._lock:
            code = code.upper()
            if code in self.rooms:
                del self.rooms[code]
                logger.info(f"[RoomManager] Room removed: {code}, total rooms: {len(self.rooms)}")
    
    async def add_connection(self, code: str, user_id: int, websocket) -> bool:
        """Добавить подключение в комнату"""
        async with self._lock:
            code = code.upper()
            if code not in self.rooms:
                return False
            self.rooms[code].connections[user_id] = websocket
            self.rooms[code].update_activity()
            return True
    
    async def remove_connection(self, code: str, user_id: int) -> int:
        """Удалить подключение из комнаты, вернуть количество оставшихся"""
        async with self._lock:
            code = code.upper()
            if code not in self.rooms:
                return 0
            
            self.rooms[code].connections.pop(user_id, None)
            remaining = self.rooms[code].get_websocket_count()
            
            if remaining == 0:
                del self.rooms[code]
                logger.info(f"[RoomManager] Empty room removed: {code}")
            
            return remaining
    
    async def _cleanup_inactive(self) -> int:
        """Очистить неактивные комнаты (внутренний метод, без лока)"""
        now = time.time()
        to_delete = [
            code for code, room in self.rooms.items()
            if room.is_expired()
        ]
        for code in to_delete:
            del self.rooms[code]
        
        if to_delete:
            logger.info(f"[RoomManager] Cleaned up {len(to_delete)} inactive rooms")
        
        return len(to_delete)
    
    async def cleanup_inactive_rooms(self) -> int:
        """Публичный метод очистки неактивных комнат"""
        async with self._lock:
            return await self._cleanup_inactive()
    
    def get_stats(self) -> dict:
        """Получить статистику комнат"""
        return {
            'total_rooms': len(self.rooms),
            'max_rooms': self.max_rooms,
            'total_connections': sum(room.get_websocket_count() for room in self.rooms.values())
        }


# Глобальный менеджер комнат
room_manager = RoomManager()


# ═══════════════════════════════════════
# СИСТЕМНЫЙ ПРОМПТ ДЛЯ ПАРНОЙ СЕССИИ
# ═══════════════════════════════════════

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


# ═══════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════

async def call_api_with_limit_and_timeout(coro, timeout: float = API_TIMEOUT):
    """Вызов API с лимитом и таймаутом"""
    async with API_SEMAPHORE:
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"[API] Timeout after {timeout}s")
            return None


async def get_ai_response(messages: list, session_data: dict) -> str:
    """Получить ответ от AI для парной сессии"""
    topic_names = {
        'partner': 'Отношения с партнёром',
        'family': 'Семейный конфликт',
        'friend': 'Конфликт с другом/коллегой',
        'work': 'Рабочий конфликт',
        'other': 'Другое'
    }
    
    name1 = session_data.get('user1_name') or 'Участник 1'
    name2 = session_data.get('user2_name') or 'Участник 2'
    
    system = PAIR_SYSTEM_PROMPT.format(
        topic=topic_names.get(session_data.get('topic', ''), 'Не указана'),
        name1=name1,
        name2=name2
    )
    
    full_messages = [{"role": "system", "content": system}] + messages
    
    try:
        result = await call_api_with_limit_and_timeout(
            ask(full_messages, config.MODEL)
        )
        
        if result is None:
            return "Произошла ошибка таймаута. Пожалуйста, повторите сообщение."
        
        response, stars_used = result
        return response
    except Exception as e:
        logger.exception(f"[AI] Error: {e}")
        return "Произошла ошибка. Пожалуйста, повторите сообщение."


async def broadcast_to_room(room: Room, message: dict, exclude_user: int = None) -> None:
    """Отправить сообщение всем в комнате"""
    for user_id, ws in room.connections.items():
        if exclude_user and user_id == exclude_user:
            continue
        try:
            await ws.send(json.dumps(message))
        except Exception as e:
            logger.debug(f"[Broadcast] Error to {user_id}: {e}")


async def periodic_cleanup() -> None:
    """Периодическая очистка неактивных комнат"""
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL)
            cleaned = await room_manager.cleanup_inactive_rooms()
            stats = room_manager.get_stats()
            logger.info(f"[Cleanup] Cleaned {cleaned} rooms. Stats: {stats}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[Cleanup] Error: {e}")


# ═══════════════════════════════════════
# ОБРАБОТКА WEBSOCKET ПОДКЛЮЧЕНИЙ
# ═══════════════════════════════════════

async def handle_connection(websocket) -> None:
    """Обработка WebSocket подключения"""
    user_id = None
    code = None
    room = None
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
            logger.warning(f"[WS] Error getting session with names: {type(e).__name__}: {e}")
            session = None
        
        # Fallback на старый метод
        if not session:
            session = redis_db.get_pair_session_cache(code)
            if not session:
                try:
                    session = await db.get_pair_session(code)
                    if session:
                        redis_db.set_pair_session_cache(code, session)
                        session['user1_name'] = 'Участник 1'
                        session['user2_name'] = 'Участник 2' if session.get('user2_id') else None
                except Exception as e2:
                    logger.warning(f"[WS] Fallback error: {e2}")
                    session = None
        
        if not session:
            session = redis_db.get_pair_session_cache(code)
            if session:
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
        
        # Получаем или создаём комнату
        room = await room_manager.get_or_create(code, session)
        if not room:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': 'Сервер перегружен. Попробуйте позже.'
            }))
            await websocket.close(1013, "Server overloaded")
            return
        
        # Добавляем подключение
        await room_manager.add_connection(code, user_id, websocket)
        
        # Определяем номер участника
        participant_num = 1 if user_id == session.get('user1_id') else 2
        
        # Подтверждаем подключение
        websocket_count = room.get_websocket_count()
        await websocket.send(json.dumps({
            'type': 'connected',
            'participant': participant_num,
            'participants_online': websocket_count
        }))
        
        # Уведомляем других о подключении
        await broadcast_to_room(room, {
            'type': 'participant_joined',
            'participant': participant_num,
            'participants_online': websocket_count
        }, exclude_user=user_id)
        
        # Если оба подключены — запускаем сессию
        if websocket_count == 2:
            history = redis_db.get_pair_chat_history(code)
            
            if not history:
                # Первый запуск — AI приветствует
                ai_response = await get_ai_response([], session)
                
                redis_db.add_pair_chat_message(code, {
                    'role': 'assistant',
                    'content': ai_response,
                    'timestamp': datetime.now().isoformat()
                })
                
                await broadcast_to_room(room, {
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
                room.update_activity()
                
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
                    await broadcast_to_room(room, {
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
                            p_num = msg.get('participant')
                            if p_num == 1:
                                sender_name = room.user1_name
                            elif p_num == 2:
                                sender_name = room.user2_name
                            else:
                                sender_name = f'Участник {p_num}'
                            
                            ai_messages.append({
                                'role': 'user',
                                'content': f"[{sender_name}]: {msg['content']}"
                            })
                    
                    # Показываем что Soul печатает
                    await broadcast_to_room(room, {
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
                    await broadcast_to_room(room, {
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
                logger.error(f"[WS] Message handling error: {e}")
                continue
    
    except asyncio.TimeoutError:
        logger.info(f"[WS] Connection timeout for user {user_id}")
    except websockets.exceptions.ConnectionClosed:
        logger.debug(f"[WS] Connection closed for user {user_id}")
    except Exception as e:
        logger.exception(f"[WS] Connection error: {type(e).__name__}: {e}")
    finally:
        # Удаляем из комнаты
        if code and user_id:
            remaining = await room_manager.remove_connection(code, user_id)
            
            # Уведомляем оставшихся
            if remaining > 0 and participant_num > 0:
                room = await room_manager.get(code)
                if room:
                    try:
                        await broadcast_to_room(room, {
                            'type': 'participant_left',
                            'participant': participant_num,
                            'participants_online': remaining
                        })
                    except Exception as e:
                        logger.debug(f"[WS] Error broadcasting participant_left: {e}")


# ═══════════════════════════════════════
# ТОЧКА ВХОДА
# ═══════════════════════════════════════

async def main() -> None:
    """Запуск WebSocket сервера"""
    # Инициализация PostgreSQL pool
    try:
        await init_pool()
        await init_db()
        logger.info("✅ PostgreSQL initialized in WebSocket server")
    except Exception as e:
        logger.exception(f"⚠️ PostgreSQL initialization error: {e}")
    
    # Запускаем периодическую очистку
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    logger.info("🚀 Starting WebSocket server on ws://0.0.0.0:8765")
    
    try:
        async with websockets.serve(
            handle_connection,
            "0.0.0.0",
            8765,
            ping_interval=30,
            ping_timeout=10,
            max_size=1024 * 1024  # 1MB max message size
        ):
            logger.info("✅ WebSocket server running")
            await asyncio.Future()
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
