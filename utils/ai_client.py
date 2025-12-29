import httpx
import json
import base64
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_CHAT_MODEL

async def get_ai_response(messages: list) -> tuple:
    """Получение ответа от Claude через ProxyAPI"""
    try:
        # Преобразуем формат сообщений для Claude
        system_prompt = ""
        claude_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                claude_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Запрос к Claude API
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{OPENAI_BASE_URL}/messages",
                headers={
                    "x-api-key": OPENAI_API_KEY,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": OPENAI_CHAT_MODEL,
                    "max_tokens": 4096,
                    "system": system_prompt,
                    "messages": claude_messages
                }
            )
            
            if response.status_code != 200:
                return f"❌ Ошибка API: {response.status_code} - {response.text}", 0
            
            data = response.json()
            
            # Извлекаем текст ответа
            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
            
            # Считаем токены
            input_tokens = data.get("usage", {}).get("input_tokens", 0)
            output_tokens = data.get("usage", {}).get("output_tokens", 0)
            total_tokens = input_tokens + output_tokens
            
            return text, total_tokens
            
    except Exception as e:
        return f"❌ Ошибка: {e}", 0


async def get_vision_response(b64: str, prompt: str) -> tuple:
    """Анализ изображения через Claude Vision"""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{OPENAI_BASE_URL}/messages",
                headers={
                    "x-api-key": OPENAI_API_KEY,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": OPENAI_CHAT_MODEL,
                    "max_tokens": 4096,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": b64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }]
                }
            )
            
            if response.status_code != 200:
                return f"❌ Ошибка Vision: {response.status_code} - {response.text}", 0
            
            data = response.json()
            
            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
            
            input_tokens = data.get("usage", {}).get("input_tokens", 0)
            output_tokens = data.get("usage", {}).get("output_tokens", 0)
            total_tokens = input_tokens + output_tokens
            
            return text, total_tokens
            
    except Exception as e:
        return f"❌ Ошибка Vision: {e}", 0
