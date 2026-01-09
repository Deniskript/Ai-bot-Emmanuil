import config
import json
from utils.openrouter import ask
from database import db


async def update_memory(user_id: int, bot_type: str, user_text: str, bot_response: str):
    """Анализирует сообщение и обновляет память о пользователе"""
    
    try:
        current_memory = await db.get_memory(user_id, bot_type)
        if current_memory is None:
            current_memory = []
        
        prompt = f"""Проанализируй сообщение пользователя и извлеки важную информацию.

Текущая память: {json.dumps(current_memory, ensure_ascii=False) if current_memory else 'пусто'}

Пользователь: {user_text[:500]}
Бот: {bot_response[:500]}

Если есть важные факты о пользователе (имя, возраст, интересы, проблемы, цели), 
верни их списком. Каждый факт - короткая фраза.

Если ничего важного нет, верни пустой список.

Формат ответа - только JSON массив строк, например:
["Зовут Алексей", "Интересуется программированием"]
или
[]"""

        resp, _ = await ask([{"role": "user", "content": prompt}], config.MODEL)
        
        if not resp or resp.startswith("❌"):
            return
        
        clean = resp.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
        
        new_facts = json.loads(clean)
        
        if new_facts and isinstance(new_facts, list):
            all_facts = list(set(current_memory + new_facts))[-15:]
            await db.save_memory(user_id, bot_type, all_facts)
            
    except json.JSONDecodeError as e:
        print(f"Memory JSON error: {e}")
    except Exception as e:
        print(f"Memory update error: {e}")


def build_memory_context(memory_data) -> str:
    """Строит контекст из памяти для системного промпта"""
    if not memory_data:
        return ""
    
    try:
        if isinstance(memory_data, list):
            if memory_data:
                return "\n\n📝 Что я помню о тебе:\n• " + "\n• ".join(memory_data[:10])
            return ""
        
        if isinstance(memory_data, str):
            data = json.loads(memory_data)
            if isinstance(data, list) and data:
                return "\n\n📝 Что я помню о тебе:\n• " + "\n• ".join(data[:10])
        
        return ""
    except:
        return ""
