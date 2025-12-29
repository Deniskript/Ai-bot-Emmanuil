from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Dict, Any, Awaitable

class ThrottleMiddleware(BaseMiddleware):
    def __init__(self):
        self.processing_users = set()
        
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)
            
        if event.text and event.text.startswith('/'):
            return await handler(event, data)
        
        user_id = event.from_user.id
        
        if user_id in self.processing_users:
            await event.answer("⏳ Подожди, обрабатываю предыдущий запрос...")
            return
        
        self.processing_users.add(user_id)
        
        try:
            return await handler(event, data)
        finally:
            self.processing_users.discard(user_id)
