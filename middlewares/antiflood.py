from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Dict, Any, Awaitable
import time
from collections import defaultdict

class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self):
        self.users_data = defaultdict(lambda: {
            'last_message': 0,
            'message_count': 0,
            'window_start': 0,
            'warnings': 0,
            'blocked_until': 0
        })
        self.min_interval = 2.0
        self.max_messages_per_minute = 8
        self.warning_threshold = 2
        self.block_duration = 60
        self.window_size = 60
        self.global_requests = []
        self.max_global_per_second = 20
        
    async def __call__(self, handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]], event: Message, data: Dict[str, Any]) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)
        
        current_time = time.time()
        self.global_requests = [t for t in self.global_requests if current_time - t < 1]
        if len(self.global_requests) >= self.max_global_per_second:
            await event.answer("⏳ Сервер загружен, попробуй позже...")
            return
        self.global_requests.append(current_time)
        
        user_id = event.from_user.id
        user_data = self.users_data[user_id]
        
        if current_time < user_data['blocked_until']:
            remaining = int(user_data['blocked_until'] - current_time)
            await event.answer(f"⏳ Подожди {remaining} сек")
            return
        
        if current_time - user_data['window_start'] > self.window_size:
            user_data['message_count'] = 0
            user_data['window_start'] = current_time
            user_data['warnings'] = 0
        
        time_since_last = current_time - user_data['last_message']
        
        if time_since_last < self.min_interval and user_data['last_message'] > 0:
            user_data['warnings'] += 1
            if user_data['warnings'] >= self.warning_threshold:
                user_data['blocked_until'] = current_time + self.block_duration
                await event.answer("🚫 Подожди минуту")
                return
            return
        
        user_data['message_count'] += 1
        if user_data['message_count'] > self.max_messages_per_minute:
            user_data['blocked_until'] = current_time + self.block_duration
            await event.answer("⏳ Лимит сообщений")
            return
        
        user_data['last_message'] = current_time
        return await handler(event, data)
