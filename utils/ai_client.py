import httpx
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_CHAT_MODEL


async def ask(msgs, model=None):
    try:
        use_model = model or OPENAI_CHAT_MODEL
        
        # Собираем system prompt
        system = None
        clean_msgs = []
        for m in msgs:
            if m["role"] == "system":
                system = m["content"]
            else:
                clean_msgs.append({"role": m["role"], "content": m["content"]})
        
        # Если нет сообщений — добавляем заглушку
        if not clean_msgs:
            clean_msgs = [{"role": "user", "content": "Привет"}]
        
        async with httpx.AsyncClient(timeout=60) as client:
            payload = {
                "model": use_model,
                "max_tokens": 4000,
                "messages": clean_msgs
            }
            if system:
                payload["system"] = system
            
            response = await client.post(
                f"{OPENAI_BASE_URL}/messages",
                headers={
                    "x-api-key": OPENAI_API_KEY,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json=payload
            )
            
            if response.status_code != 200:
                print(f"❌ API Error {response.status_code}")
                print(f"❌ Response: {response.text}")
                print(f"❌ Model: {use_model}")
                print(f"❌ Messages: {len(clean_msgs)}")
                return f"❌ Ошибка API: {response.status_code}", 0
            
            data = response.json()
            text = data["content"][0]["text"]
            inp = data.get("usage", {}).get("input_tokens", 0)
            out = data.get("usage", {}).get("output_tokens", 0)
            return text, inp + out
    except Exception as e:
        print(f"❌ Exception: {e}")
        return f"❌ Ошибка: {e}", 0
