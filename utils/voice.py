import tempfile
import os
import httpx
from config import OPENAI_API_KEY

async def transcribe_voice(data: bytes) -> str:
    """Транскрибация голоса через ProxyAPI Whisper"""
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(data)
            path = f.name
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(path, "rb") as audio_file:
                response = await client.post(
                    "https://api.proxyapi.ru/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    files={"file": ("voice.ogg", audio_file, "audio/ogg")},
                    data={"model": "whisper-1", "language": "ru"}
                )
        
        os.unlink(path)
        
        if response.status_code == 200:
            return response.json().get("text", "")
        else:
            return None
    except Exception as e:
        return None
