import logging
import os
import tempfile

import httpx

from config import VSEGPT_API_KEY, VSEGPT_BASE_URL

logger = logging.getLogger(__name__)


async def download_voice(bot, file_id: str) -> str | None:
    """Скачивает голосовое сообщение и возвращает путь к файлу"""
    try:
        file = await bot.get_file(file_id)
        file_path = tempfile.mktemp(suffix='.ogg')
        await bot.download_file(file.file_path, file_path)
        return file_path
    except Exception as e:
        logger.exception("Download voice error: %s", e)
        return None


async def transcribe_voice(file_path: str) -> str | None:
    """Преобразует голосовое сообщение в текст через Whisper"""
    try:
        if not VSEGPT_API_KEY:
            logger.error("VSEGPT_API_KEY не установлен (нужен для STT)")
            return None
        async with httpx.AsyncClient(timeout=60) as client:
            with open(file_path, 'rb') as f:
                files = {'file': ('audio.ogg', f, 'audio/ogg')}
                # VseGPT: OpenAI-compatible STT endpoint
                data = {'model': 'stt-openai/whisper-1'}
                
                response = await client.post(
                    f"{VSEGPT_BASE_URL}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {VSEGPT_API_KEY}"},
                    files=files,
                    data=data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get('text', '')
                else:
                    logger.error("STT error: %s - %s", response.status_code, response.text)
                    return None
    except Exception as e:
        logger.exception("Transcribe error: %s", e)
        return None
    finally:
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)


async def text_to_speech(text: str, voice: str = "shimmer") -> str | None:
    """
    Преобразует текст в речь через OpenAI TTS API
    
    Args:
        text: Текст для озвучки
        voice: Голос для озвучки
               Женские: nova, shimmer, alloy
               Мужские: onyx, echo, fable
    
    Returns:
        Путь к созданному аудио файлу или None
    """
    try:
        if not VSEGPT_API_KEY:
            logger.error("VSEGPT_API_KEY не установлен (нужен для TTS)")
            return None
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{VSEGPT_BASE_URL}/audio/speech",
                headers={
                    "Authorization": f"Bearer {VSEGPT_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "tts-1-hd",  # Высокое качество
                    "input": text[:4096],  # Ограничение по длине
                    "voice": voice,
                    "response_format": "opus"  # Формат для Telegram
                }
            )
            
            if response.status_code == 200:
                # Сохраняем в временный файл
                audio_path = tempfile.mktemp(suffix='.ogg')
                with open(audio_path, 'wb') as f:
                    f.write(response.content)
                return audio_path
            else:
                logger.error("TTS error: %s - %s", response.status_code, response.text)
                return None
                
    except Exception as e:
        logger.exception("TTS error: %s", e)
        return None
