"""
Единый модуль стриминга для бота Soul
Автоматически: статус → переключение → стриминг
"""

import asyncio
from aiogram import Bot
from aiogram.types import Message
from utils.status_manager import show_status
from utils.openrouter import ask_stream
from utils.markdown import md_to_html
from utils.conversations import clean_response


async def stream_response(
    bot: Bot,
    message: Message,
    messages: list,
    model: str = "anthropic/claude-sonnet-4.5",
    status_type: str = "text",
    system_prompt: str = None,
    max_tokens: int = 4000
) -> str:
    """
    Единая функция стриминга с автоматическим статусом.
    
    Логика:
    1. Показывает анимированный статус
    2. Отправляет запрос к OpenRouter API
    3. При первом chunk — выключает статус
    4. Стримит ответ пользователю
    
    Args:
        bot: Экземпляр бота
        message: Сообщение пользователя (для получения chat_id)
        messages: История сообщений для API
        model: Модель (OpenRouter)
        status_type: Тип статуса ("text", "photo", "voice", "magic", "generate")
        system_prompt: Системный промпт (опционально)
        max_tokens: Макс токенов в ответе
    
    Returns:
        Полный текст ответа
    """
    
    chat_id = message.chat.id
    
    # Добавляем системный промпт если есть
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages
    
    # 1. Запускаем статус
    status = await show_status(bot, chat_id, status_type)
    first_chunk = True
    stream_msg = None
    full_response = ""
    buffer = ""
    last_update = asyncio.get_event_loop().time()
    
    try:
        # 2. Стриминг от OpenRouter
        async for chunk in ask_stream(messages, model, max_tokens=max_tokens):
            if not chunk:
                continue
            
            full_response += chunk
            buffer += chunk
            now = asyncio.get_event_loop().time()
            
            # При первом chunk - выключаем статус и создаем сообщение
            if first_chunk:
                first_chunk = False
                await status.stop()
                await asyncio.sleep(0.05)
                stream_msg = await message.answer(chunk, parse_mode=None)
                last_update = now
                continue
            
            # Обновляем экран каждые 30 символов или 0.5 секунды
            if stream_msg and buffer:
                should_update = (
                    len(buffer) >= 30 or 
                    now - last_update >= 0.5 or
                    '\n' in buffer[-5:]
                )
                
                if should_update:
                    formatted = md_to_html(full_response)
                    try:
                        await stream_msg.edit_text(formatted + " ▌", parse_mode="HTML")
                        buffer = ""
                        last_update = now
                        await asyncio.sleep(0.05)
                    except Exception as e:
                        # Игнорируем ошибки "message not modified"
                        if "message is not modified" not in str(e).lower():
                            pass
        
        # Финальное обновление без курсора
        if stream_msg and full_response:
            formatted = md_to_html(full_response.strip())
            try:
                await stream_msg.edit_text(formatted, parse_mode="HTML")
            except:
                pass
        
        # Если не было ни одного chunk
        if first_chunk:
            await status.stop()
            return ""
        
        return full_response.strip()
        
    except Exception as e:
        # При ошибке — выключаем статус
        if first_chunk:
            await status.stop()
        raise e


async def stream_magic_response(
    bot: Bot,
    message: Message,
    prompt: str,
    magic_type: str = "tarot",
    model: str = "anthropic/claude-sonnet-4.5"
) -> str:
    """
    Стриминг для магических функций (таро, гороскоп, гадания).
    """
    
    MAGIC_PROMPTS = {
        "tarot": "Ты мистический таролог. Отвечай загадочно и глубокомысленно.",
        "horoscope": "Ты астролог. Составляй гороскопы красиво и детально.",
        "numerology": "Ты нумеролог. Анализируй числа мистически.",
        "fortune": "Ты гадалка. Предсказывай будущее таинственно."
    }
    
    system_prompt = MAGIC_PROMPTS.get(magic_type, MAGIC_PROMPTS["fortune"])
    messages = [{"role": "user", "content": prompt}]
    
    return await stream_response(
        bot=bot,
        message=message,
        messages=messages,
        model=model,
        status_type="magic",
        system_prompt=system_prompt
    )
