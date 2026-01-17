import config
import json
from utils.openrouter import ask
from database import postgres_db as db


async def update_memory(user_id: int, bot_type: str, user_text: str, bot_response: str):
    """Анализирует сообщение и обновляет память о пользователе"""
    
    try:
        current_memory = await db.get_memory(user_id, bot_type)
        if current_memory is None:
            current_memory = []
        
        prompt = f"""Проанализируй диалог и обнови память о пользователе.

═══════════════════════════════════════
ТЕКУЩАЯ ПАМЯТЬ:
{json.dumps(current_memory, ensure_ascii=False) if current_memory else 'пусто'}
═══════════════════════════════════════

НОВЫЙ ДИАЛОГ:
Пользователь: {user_text[:500]}
Бот: {bot_response[:500]}

═══════════════════════════════════════
ТВОЯ ЗАДАЧА:
═══════════════════════════════════════

1. ДОБАВЬ новые важные факты:
   • Имя, возраст, город
   • Работа, учёба, интересы
   • Текущие проблемы и переживания
   • Цели, мечты, планы
   • Важные люди (семья, друзья, партнёр)

2. УДАЛИ из памяти:
   • Решённые проблемы (человек сказал "всё наладилось", "уже норм", "решил", "справился")
   • Устаревшую информацию (если появилась новая)
   • Дубликаты (оставь один вариант)

3. ОБНОВИ если изменилось:
   • Было "ищет работу" → стало "нашёл работу" → замени на новое

═══════════════════════════════════════
ФОРМАТ ОТВЕТА:
═══════════════════════════════════════

Верни ПОЛНЫЙ актуальный список фактов (не только новые, а ВСЕ что нужно помнить).
Каждый факт — короткая фраза.

JSON массив строк:
["Зовут Алексей", "Работает программистом", "Есть девушка Маша"]

Если ничего важного нет и память пуста — верни: []
Если ничего не изменилось — верни текущую память как есть."""

        resp, _ = await ask([{"role": "user", "content": prompt}], config.MODEL)
        
        if not resp or resp.startswith("❌"):
            return
        
        clean = resp.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
        
        new_facts = json.loads(clean)
        
        if isinstance(new_facts, list):
            # Удаляем дубликаты (сохраняем порядок, оставляем последние)
            seen = set()
            unique_facts = []
            for fact in reversed(new_facts):
                # Нормализуем для сравнения (lowercase, strip)
                normalized = fact.lower().strip()
                if normalized not in seen:
                    seen.add(normalized)
                    unique_facts.append(fact)
            unique_facts.reverse()
            
            # Сохраняем последние 15 уникальных фактов
            all_facts = unique_facts[-15:] if unique_facts else current_memory
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
