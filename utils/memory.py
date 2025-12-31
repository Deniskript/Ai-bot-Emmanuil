from database import db
from utils.ai_client import ask
import json


EXTRACT_PROMPT = """Извлеки ВАЖНЫЕ факты о пользователе из диалога.
Только конкретные факты: имя, возраст, работа, хобби, семья, проблемы, цели.

Диалог:
{dialog}

Ответь JSON-списком фактов (максимум 5 новых):
["факт1", "факт2"]

Если фактов нет — ответь: []"""


async def extract_facts(user_id: int, bot_name: str, dialog: str) -> list:
    """Извлекает факты из диалога"""
    try:
        msgs = [{"role": "user", "content": EXTRACT_PROMPT.format(dialog=dialog[-2000:])}]
        resp, _ = await ask(msgs, "claude-sonnet-4-5-20250929")
        
        # Парсим JSON из ответа
        start = resp.find('[')
        end = resp.rfind(']') + 1
        if start != -1 and end > start:
            facts = json.loads(resp[start:end])
            return facts[:5]
        return []
    except Exception as e:
        print(f"Extract facts error: {e}")
        return []


async def update_memory(user_id: int, bot_name: str, user_msg: str, bot_resp: str):
    """Обновляет долгую память после диалога"""
    try:
        # Получаем текущую память
        current_facts = await db.get_memory(user_id, bot_name)
        
        # Извлекаем новые факты
        dialog = f"Пользователь: {user_msg}\nБот: {bot_resp}"
        new_facts = await extract_facts(user_id, bot_name, dialog)
        
        if new_facts:
            # Объединяем, убираем дубли, оставляем последние 15
            all_facts = current_facts + new_facts
            unique_facts = list(dict.fromkeys(all_facts))[-15:]
            await db.save_memory(user_id, bot_name, unique_facts)
            
    except Exception as e:
        print(f"Update memory error: {e}")


def build_memory_context(facts: list) -> str:
    """Формирует контекст памяти для промпта"""
    if not facts:
        return ""
    return "\n\n🧠 ДОЛГАЯ ПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ:\n• " + "\n• ".join(facts[-10:])
