import httpx
from config import OPENAI_API_KEY


# Конфигурация провайдеров
PROVIDERS = {
    "anthropic": {
        "base_url": "https://api.proxyapi.ru/anthropic/v1",
        "models": [
            "claude-sonnet-4-5-20250929",
            "claude-opus-4-5-20251101",
            "claude-opus-4-1-20250805",
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-20250219",
            "claude-haiku-4-5-20251001",
            "claude-3-5-haiku-20241022"
        ]
    },
    "openai": {
        "base_url": "https://api.proxyapi.ru/openai/v1",
        "models": [
            "o4-mini-2025-04-16",
            "o3-pro-2025-06-10",
            "o3-2025-04-16",
            "o3-mini-2025-01-31",
            "o1-pro-2025-03-19",
            "o1-2024-12-17",
            "gpt-5.2-chat-latest",
            "gpt-5.1-2025-11-13",
            "gpt-5.1-chat-latest",
            "gpt-5-2025-08-07",
            "gpt-5-chat-latest",
            "gpt-5-mini-2025-08-07",
            "gpt-5-nano-2025-08-07",
            "gpt-4.1-2025-04-14",
            "gpt-4.1-mini-2025-04-14",
            "gpt-4.1-nano-2025-04-14",
            "gpt-4o",
            "gpt-4o-mini"
        ]
    }
}


def get_provider(model: str) -> str:
    """Определяет провайдера по модели"""
    if model.startswith("claude"):
        return "anthropic"
    return "openai"


async def ask(msgs: list, model: str = None, image_base64: str = None) -> tuple:
    """Универсальный запрос к AI"""
    try:
        use_model = model or "claude-sonnet-4-5-20250929"
        provider = get_provider(use_model)
        
        if provider == "anthropic":
            return await _ask_anthropic(msgs, use_model, image_base64)
        else:
            return await _ask_openai(msgs, use_model, image_base64)
            
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return f"❌ Ошибка: {e}", 0


async def _ask_anthropic(msgs: list, model: str, image_base64: str = None) -> tuple:
    """Запрос к Anthropic Claude"""
    try:
        system = None
        clean_msgs = []
        
        for m in msgs:
            if m["role"] == "system":
                system = m["content"]
            else:
                clean_msgs.append({"role": m["role"], "content": m["content"]})
        
        if image_base64 and clean_msgs:
            last_msg = clean_msgs[-1]
            clean_msgs[-1] = {
                "role": last_msg["role"],
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_base64
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
        
        async with httpx.AsyncClient(timeout=120) as client:
            payload = {
                "model": model,
                "max_tokens": 4000,
                "messages": clean_msgs
            }
            if system:
                payload["system"] = system
            
            response = await client.post(
                f"{PROVIDERS['anthropic']['base_url']}/messages",
                headers={
                    "x-api-key": OPENAI_API_KEY,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json=payload
            )
            
            if response.status_code != 200:
                print(f"❌ Anthropic Error {response.status_code}: {response.text}")
                return f"❌ Ошибка API: {response.status_code}", 0
            
            data = response.json()
            text = data["content"][0]["text"]
            inp = data.get("usage", {}).get("input_tokens", 0)
            out = data.get("usage", {}).get("output_tokens", 0)
            return text, inp + out
            
    except Exception as e:
        print(f"❌ Anthropic Exception: {e}")
        return f"❌ Ошибка: {e}", 0


async def _ask_openai(msgs: list, model: str, image_base64: str = None) -> tuple:
    """Запрос к OpenAI GPT"""
    try:
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
        
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{PROVIDERS['openai']['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "max_tokens": 4000,
                    "messages": clean_msgs
                }
            )
            
            if response.status_code != 200:
                print(f"❌ OpenAI Error {response.status_code}: {response.text}")
                return f"❌ Ошибка API: {response.status_code}", 0
            
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            return text, tokens
            
    except Exception as e:
        print(f"❌ OpenAI Exception: {e}")
        return f"❌ Ошибка: {e}", 0


def get_available_models() -> dict:
    """Возвращает список доступных моделей по провайдерам"""
    return PROVIDERS


def get_all_models() -> list:
    """Возвращает плоский список всех моделей"""
    models = []
    for p in PROVIDERS.values():
        models.extend(p["models"])
    return models
