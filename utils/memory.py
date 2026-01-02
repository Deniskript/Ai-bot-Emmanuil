from database import db
from utils.ai_client import ask
import json


EXTRACT_PROMPT = """Ты — ассистент психолога. Извлеки ВАЖНЫЕ факты о клиенте из диалога.

КАТЕГОРИИ:
- РАБОТА: профессия, коллеги, начальство, проблемы
- СЕМЬЯ: партнёр, дети, родители, отношения
- ЭМОЦИИ: страхи, тревоги, паттерны
- ЗДОРОВЬЕ: сон, энергия, состояние
- ЛИЧНОСТЬ: имя, возраст, характер
- ЦЕЛИ: желания, мечты

Диалог:
{dialog}

Уже известно (НЕ ПОВТОРЯЙ):
{existing}

Формат: "КАТЕГОРИЯ: факт"
Пример: "РАБОТА: конфликт с начальником"

JSON-список НОВЫХ фактов (макс 3):
["КАТЕГОРИЯ: факт"]

Если новых нет: []"""


async def extract_facts(user_id: int, bot_name: str, dialog: str, existing: list) -> list:
    try:
        existing_str = "\n".join(existing[-15:]) if existing else "нет"
        prompt = EXTRACT_PROMPT.format(dialog=dialog[-3000:], existing=existing_str)
        msgs = [{"role": "user", "content": prompt}]
        resp, _ = await ask(msgs, "gpt-4o-mini")
        
        start = resp.find('[')
        end = resp.rfind(']') + 1
        if start != -1 and end > start:
            return json.loads(resp[start:end])[:3]
        return []
    except Exception as e:
        print(f"Extract facts error: {e}")
        return []


async def update_memory(user_id: int, bot_name: str, user_msg: str, bot_resp: str):
    try:
        current = await db.get_memory(user_id, bot_name)
        dialog = f"Клиент: {user_msg}\nПсихолог: {bot_resp}"
        new_facts = await extract_facts(user_id, bot_name, dialog, current)
        
        if new_facts:
            all_facts = current + new_facts
            unique = list(dict.fromkeys(all_facts))[-20:]  # Макс 20
            await db.save_memory(user_id, bot_name, unique)
    except Exception as e:
        print(f"Update memory error: {e}")


def build_memory_context(facts: list, msg_count: int = 0) -> str:
    if not facts:
        return ""
    
    # Группируем по категориям
    cats = {}
    for f in facts:
        if ": " in f:
            c, v = f.split(": ", 1)
            cats.setdefault(c, []).append(v)
        else:
            cats.setdefault("ДРУГОЕ", []).append(f)
    
    text = "\n\n📋 ДОСЬЕ КЛИЕНТА:"
    for c, items in cats.items():
        text += f"\n• {c}: {'; '.join(items)}"
    
    # Триггер для упоминания памяти каждые 6-10 сообщений
    if msg_count > 0 and msg_count % 7 == 0:
        text += "\n\n⚡ СЕЙЧАС УМЕСТНО связать текущую тему с досье!"
    
    return text
