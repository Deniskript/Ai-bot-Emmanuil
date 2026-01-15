"""
Единый модуль стриминга для бота Soul
"""

import asyncio
import time
from aiogram import Bot
from aiogram.types import Message
from utils.status_manager import show_status
from utils.openrouter import ask_stream, ask
from utils.markdown import md_to_html


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
    """
    
    chat_id = message.chat.id
    
    # Добавляем системный промпт если есть
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt}] + messages
    
    # 1. Запускаем статус
    status = await show_status(bot, chat_id, status_type)
    stream_msg = None
    full_response = ""
    status_stopped = False
    
    try:
        # 2. Стриминг от OpenRouter
        last_update_time = time.time()
        last_paragraph_count = 0
        
        async for chunk in ask_stream(messages, model, max_tokens=max_tokens):
            if not chunk:
                continue
            
            full_response += chunk
            
            # Проверяем нужно ли обновить
            current_time = time.time()
            paragraph_count = full_response.count("\n\n")
            
            # Условия для обновления:
            # 1. Новые 2 абзаца появились
            # 2. ИЛИ прошло 2+ секунды и есть текст 100+ символов
            new_paragraphs = paragraph_count >= last_paragraph_count + 2
            time_passed = current_time - last_update_time >= 2.0 and len(full_response) >= 100
            
            if new_paragraphs or time_passed:
                # Останавливаем статус при первом обновлении
                if not status_stopped:
                    await status.stop()
                    status_stopped = True
                    await asyncio.sleep(0.05)
                    formatted = md_to_html(full_response)
                    stream_msg = await message.answer(formatted, parse_mode="HTML")
                else:
                    if stream_msg:
                        formatted = md_to_html(full_response)
                        try:
                            await stream_msg.edit_text(formatted, parse_mode="HTML")
                        except Exception:
                            pass
                
                last_update_time = current_time
                last_paragraph_count = paragraph_count
        
        # 3. Финальное обновление
        # Останавливаем статус если ещё не остановлен
        if not status_stopped:
            await status.stop()
            status_stopped = True
        
        # Отправляем/обновляем финальный текст
        if full_response.strip():
            formatted = md_to_html(full_response.strip())
            if stream_msg:
                try:
                    await stream_msg.edit_text(formatted, parse_mode="HTML")
                except Exception:
                    pass
            else:
                await message.answer(formatted, parse_mode="HTML")
        else:
            # Фолбэк: стриминг не дал текста — обычный запрос
            fallback_text, _ = await ask(messages, model, max_tokens=max_tokens)
            fallback_text = (fallback_text or "").strip()
            if fallback_text:
                formatted = md_to_html(fallback_text)
                await message.answer(formatted, parse_mode="HTML")
                return fallback_text
            else:
                await message.answer("Не удалось получить ответ. Попробуйте ещё раз.")
                return ""
        
        return full_response.strip()
        
    except Exception as e:
        if not status_stopped:
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
    Стриминг для магических функций.
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
