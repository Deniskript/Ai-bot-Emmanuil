"""
Единая система статусов ожидания для бота Soul
"""
import asyncio
from aiogram import Bot
from aiogram.enums import ChatAction

STATUS_CONFIG = {
    "text": {
        "emoji_animation": ["✨", "💭", "✍️", "💬"],
        "text": "✍️ Печатаю вам сообщение",
        "action": ChatAction.TYPING
    },
    "photo": {
        "emoji_animation": ["📸", "👁️", "🔍", "🎯"],
        "text": "🔍 Смотрю ваше фото",
        "action": ChatAction.UPLOAD_PHOTO
    },
    "voice": {
        "emoji_animation": ["🎤", "🎧", "🎵", "🔊"],
        "text": "🎧 Слушаю ваше сообщение",
        "action": ChatAction.RECORD_VOICE
    },
    "magic": {
        "emoji_animation": ["✨", "🔮", "🌙", "⭐"],
        "text": "✨ Заглядываю в будущее",
        "action": ChatAction.TYPING
    },
    "generate": {
        "emoji_animation": ["💡", "🎨", "🖼️", "✨"],
        "text": "🎨 Создаю для вас",
        "action": ChatAction.UPLOAD_PHOTO
    }
}

SEPARATOR = "· · · · · · · · · · · · · ·"


class StatusManager:
    def __init__(self, bot: Bot, chat_id: int, status_type: str = "text"):
        self.bot = bot
        self.chat_id = chat_id
        self.config = STATUS_CONFIG.get(status_type, STATUS_CONFIG["text"])
        self.message = None
        self.running = False
        self.task = None
        self.seconds = 0
    
    def _build_message(self) -> str:
        emoji_index = self.seconds % len(self.config["emoji_animation"])
        header_emoji = self.config["emoji_animation"][emoji_index]
        return f"{header_emoji} Soul\n{SEPARATOR}\n{self.config['text']}... ({self.seconds} сек)"
    
    async def start(self):
        """Запустить анимацию статуса"""
        self.running = True
        self.seconds = 0
        
        try:
            self.message = await self.bot.send_message(
                self.chat_id,
                self._build_message()
            )
            self.task = asyncio.create_task(self._animate())
        except Exception as e:
            print(f"[STATUS] Error starting: {e}")
    
    async def _animate(self):
        """Анимация статуса каждую секунду"""
        while self.running:
            try:
                await asyncio.sleep(1)
                self.seconds += 1
                
                if self.running and self.message:
                    await self.message.edit_text(self._build_message())
                    await self.bot.send_chat_action(
                        self.chat_id,
                        self.config["action"]
                    )
            except Exception:
                pass
    
    async def stop(self):
        """Остановить и удалить статус"""
        self.running = False
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        if self.message:
            try:
                await self.message.delete()
            except Exception:
                pass
            self.message = None


async def show_status(bot: Bot, chat_id: int, status_type: str = "text"):
    """Создать и запустить статус. Возвращает StatusManager для остановки."""
    manager = StatusManager(bot, chat_id, status_type)
    await manager.start()
    return manager
