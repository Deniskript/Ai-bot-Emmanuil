"""
GPT Vision для модуля Магия
"""
import aiohttp
from config import VSEGPT_API_KEY, VSEGPT_BASE_URL
from utils.openrouter import ask as openrouter_ask


def _strip_data_url(image_base64: str) -> str:
    """Убрать префикс data:image/... из base64"""
    if image_base64.startswith("data:image"):
        return image_base64.split(",", 1)[-1]
    return image_base64


def _ensure_data_url(image_base64: str) -> str:
    """Добавить префикс data:image если его нет"""
    if not image_base64.startswith("data:image"):
        return f"data:image/jpeg;base64,{image_base64}"
    return image_base64


async def _openrouter_vision(image_base64: str, prompt: str) -> str:
    """OpenRouter Vision API"""
    image_clean = _strip_data_url(image_base64)
    
    print(f"[OPENROUTER VISION] Image size: {len(image_clean)} chars")
    print(f"[OPENROUTER VISION] Prompt: {prompt[:80]}...")
    
    text, tokens = await openrouter_ask(
        msgs=[{"role": "user", "content": prompt}],
        model="openai/gpt-4o-mini",
        image_base64=image_clean,
        max_tokens=1200
    )
    
    print(f"[OPENROUTER VISION] Result tokens: {tokens}")
    print(f"[OPENROUTER VISION] Result text: {text[:100] if text else 'None'}...")
    
    if tokens == 0 and isinstance(text, str) and text.startswith("Ошибка"):
        raise Exception(text)
    
    return text


async def _vsegpt_vision(image_base64: str, prompt: str) -> str:
    """VseGPT Vision API (fallback)"""
    if not VSEGPT_API_KEY:
        raise Exception("VSEGPT_API_KEY not set")
    
    image_url = _ensure_data_url(image_base64)
    
    print(f"[VSEGPT VISION] Image URL starts: {image_url[:50]}...")
    
    content = [
        {"type": "text", "text": prompt},
        {
            "type": "image_url",
            "image_url": {
                "url": image_url,
                "detail": "high"
            }
        }
    ]
    
    headers = {
        "Authorization": f"Bearer {VSEGPT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 1200,
        "temperature": 0.8
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{VSEGPT_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=180)
        ) as resp:
            response_text = await resp.text()
            print(f"[VSEGPT VISION] Status: {resp.status}")
            
            if resp.status != 200:
                print(f"[VSEGPT VISION] Error: {response_text[:200]}")
                raise Exception(f"VseGPT Error {resp.status}: {response_text}")
            
            result = await resp.json()
            text = result["choices"][0]["message"]["content"].strip()
            print(f"[VSEGPT VISION] Success! Text: {text[:100]}...")
            return text


async def analyze_image_with_prompt(image_base64: str, prompt: str) -> str:
    """
    Анализ изображения через Vision API
    Попытка 1: OpenRouter
    Попытка 2: VseGPT (fallback)
    """
    if not image_base64:
        raise ValueError("image_base64 is required")
    
    print(f"[VISION] === Starting image analysis ===")
    print(f"[VISION] Input image size: {len(image_base64)} chars")
    
    try:
        print("[VISION] Trying OpenRouter...")
        result = await _openrouter_vision(image_base64, prompt)
        print("[VISION] OpenRouter SUCCESS")
        return result
    except Exception as e:
        print(f"[VISION] OpenRouter FAILED: {e}")
    
    try:
        print("[VISION] Trying VseGPT fallback...")
        result = await _vsegpt_vision(image_base64, prompt)
        print("[VISION] VseGPT SUCCESS")
        return result
    except Exception as e:
        print(f"[VISION] VseGPT FAILED: {e}")
        raise Exception(f"Все Vision API недоступны: {e}")
