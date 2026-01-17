import httpx
import json
import config
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_SITE_URL, OPENROUTER_APP_NAME
from utils.stars import calculate_stars, STAR_MARGIN

_client = None


async def get_client():
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            http2=True
        )
    return _client


async def close_client():
    """Закрыть httpx client при shutdown"""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def ask(msgs: list, model: str = None, image_base64: str = None, max_tokens: int = 2000) -> tuple:
    """Обычный (не стрим) запрос к OpenRouter"""
    try:
        use_model = model or config.MODEL
        
        clean_msgs = []
        for m in msgs:
            clean_msgs.append({"role": m["role"], "content": m["content"]})
        
        if image_base64 and clean_msgs:
            last_msg = clean_msgs[-1]
            clean_msgs[-1] = {
                "role": last_msg["role"],
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": last_msg["content"] or "Что на этом изображении?"
                    }
                ]
            }
        
        if not clean_msgs:
            clean_msgs = [{"role": "user", "content": "Привет"}]
        
        payload = {
            "model": use_model,
            "messages": clean_msgs,
            "max_tokens": max_tokens,
            "provider": {
                "order": ["Google", "Anthropic", "AWS Bedrock"],
                "allow_fallbacks": True
            }
        }
        
        client = await get_client()
        response = await client.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": OPENROUTER_SITE_URL or "https://t.me/lukabotai",
                "X-Title": OPENROUTER_APP_NAME or "Luka AI Bot",
                "Content-Type": "application/json"
            },
            json=payload
        )
        
        if response.status_code != 200:
            error_text = response.text
            print(f"OpenRouter Error {response.status_code}: {error_text}")
            return f"Ошибка API: {response.status_code}", 0
        
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        
        # Используем новый точный подсчёт
        stars_to_charge = calculate_stars(clean_msgs, text)
        
        # Логируем для отладки
        print(f"[STARS] charging={stars_to_charge}, margin={STAR_MARGIN}")
        
        return text, stars_to_charge
        
    except httpx.TimeoutException:
        print("OpenRouter Timeout")
        return "Превышено время ожидания. Попробуйте ещё раз.", 0
    except Exception as e:
        print(f"OpenRouter Exception: {e}")
        import traceback
        traceback.print_exc()
        return f"Ошибка: {e}", 0


async def ask_stream(msgs: list, model: str = None, max_tokens: int = 2000):
    """Стрим запрос к OpenRouter (звёзды считаются в хендлере)"""
    try:
        use_model = model or config.MODEL
        
        clean_msgs = []
        for m in msgs:
            clean_msgs.append({"role": m["role"], "content": m["content"]})
        
        if not clean_msgs:
            clean_msgs = [{"role": "user", "content": "Привет"}]
        
        payload = {
            "model": use_model,
            "messages": clean_msgs,
            "max_tokens": max_tokens,
            "stream": True,
            "provider": {
                "order": ["Google", "Anthropic", "AWS Bedrock"],
                "allow_fallbacks": True
            }
        }
        
        client = await get_client()
        
        async with client.stream(
            "POST",
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": OPENROUTER_SITE_URL or "https://t.me/lukabotai",
                "X-Title": OPENROUTER_APP_NAME or "Luka AI Bot",
                "Content-Type": "application/json"
            },
            json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta:
                            text = delta["content"]
                            print(f"[STREAM CHUNK] {len(text)} chars")
                            yield text
                    except Exception as e:
                        print(f"[STREAM ERROR] {e}")
                        pass
                        
    except Exception as e:
        print(f"Stream error: {e}")
        yield f"Ошибка: {e}"


async def check_api_status() -> dict:
    """Проверка статуса API"""
    try:
        client = await get_client()
        response = await client.get(
            f"{OPENROUTER_BASE_URL}/models",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
        )
        if response.status_code == 200:
            return {"status": "ok", "models": len(response.json().get("data", []))}
        return {"status": "error", "code": response.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_available_models() -> dict:
    """Доступные модели"""
    return {
        "sonnet": [config.MODEL],
        "opus": ["anthropic/claude-opus-4"]
    }
