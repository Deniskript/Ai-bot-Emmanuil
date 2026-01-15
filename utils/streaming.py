"""
Единый модуль стриминга для бота Soul
Автоматически: статус → переключение → стриминг
"""

import asyncio
from aiogram import Bot
from aiogram.types import Message
from utils.status_manager import show_status
import openai
from config import OPENAI_API_KEY

# Инициализация клиента
client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)


async def stream_response(
    bot: Bot,
    message: Message,
    messages: list,
    model: str = "gpt-4o-mini",
    status_type: str = "text",
    system_prompt: str = None
) -> str:
    """
    Единая функция стриминга с автоматическим статусом.
    
    Логика:
    1. Показывает анимированный статус
    2. Отправляет запрос к API
    3. При первом chunk — выключает статус
    4. Стримит ответ пользователю
    
    Args:
        bot: Экземпляр бота
        message: Сообщение пользователя (для получения chat_id)
        messages: История сообщений для API
        model: Модель OpenAI
        status_type: Тип статуса ("text", "photo", "voice", "magic", "generate")
        system_prompt: Системный промпт (опционально)
    
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
    full_text = ""
    
    try:
        # 2. Стриминг от OpenAI
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True
        )
        
        buffer = ""
        last_update = 0
        
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                buffer += content
                full_text += content
                
                # Обновляем каждые 20 символов или при переносе строки
                if len(buffer) - last_update >= 20 or "\n" in content:
                    if first_chunk:
                        # 3. Первый chunk — выключаем статус
                        await status.stop()
                        first_chunk = False
                        stream_msg = await message.answer(buffer)
                    else:
                        # 4. Обновляем сообщение
                        try:
                            await stream_msg.edit_text(buffer)
                        except Exception:
                            pass  # Игнорируем ошибки редактирования
                    last_update = len(buffer)
        
        # Финальное обновление
        if stream_msg and buffer != stream_msg.text:
            try:
                await stream_msg.edit_text(buffer)
            except Exception:
                pass
        
        # Если не было ни одного chunk
        if first_chunk:
            await status.stop()
            await message.answer("Не удалось получить ответ. Попробуйте ещё раз.")
            return ""
        
        return full_text
        
    except Exception as e:
        # При ошибке — выключаем статус
        if first_chunk:
            await status.stop()
        await message.answer(f"❌ Ошибка: {str(e)}")
        raise e


async def stream_response_with_photo(
    bot: Bot,
    message: Message,
    prompt: str,
    image_url: str = None,
    image_base64: str = None,
    model: str = "gpt-4o",
    system_prompt: str = None
) -> str:
    """
    Стриминг для анализа фото.
    """
    
    # Формируем сообщение с изображением
    content = [{"type": "text", "text": prompt}]
    
    if image_url:
        content.append({
            "type": "image_url",
            "image_url": {"url": image_url}
        })
    elif image_base64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
        })
    
    messages = [{"role": "user", "content": content}]
    
    return await stream_response(
        bot=bot,
        message=message,
        messages=messages,
        model=model,
        status_type="photo",
        system_prompt=system_prompt
    )


async def stream_magic_response(
    bot: Bot,
    message: Message,
    prompt: str,
    magic_type: str = "tarot",
    model: str = "gpt-4o-mini"
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
