import httpx
import os
import tempfile
from config import OPENAI_API_KEY


async def download_voice(bot, file_id: str) -> str:
    """Скачивает голосовое сообщение и возвращает путь к файлу"""
    try:
        file = await bot.get_file(file_id)
        file_path = tempfile.mktemp(suffix='.ogg')
        await bot.download_file(file.file_path, file_path)
        return file_path
    except Exception as e:
        print(f"Download voice error: {e}")
        return None


async def transcribe_voice(file_path: str) -> str:
    """Преобразует голосовое сообщение в текст через Whisper"""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            with open(file_path, 'rb') as f:
                files = {'file': ('audio.ogg', f, 'audio/ogg')}
                data = {'model': 'whisper-1'}
                
                response = await client.post(
                    "https://api.proxyapi.ru/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    files=files,
                    data=data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get('text', '')
                else:
                    print(f"Whisper error: {response.status_code} - {response.text}")
                    return None
    except Exception as e:
        print(f"Transcribe error: {e}")
        return None
    finally:
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)


async def text_to_speech(text: str, voice: str = "nova") -> str:
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
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                "https://api.proxyapi.ru/openai/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
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
                print(f"TTS error: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        print(f"TTS error: {e}")
        return None
