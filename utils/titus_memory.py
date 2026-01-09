"""Titus Memory - система долгосрочной памяти для курсов"""
import json
from utils.openrouter import ask
from database import db
import config


async def save_step_progress(course_id: int, step: int, bot_message: str, user_response: str):
    """Сохраняет краткую суть пройденного шага"""
    try:
        prompt = f"""Извлеки ключевую информацию из этого шага обучения.

Объяснение преподавателя:
{bot_message[:500]}

Ответ студента:
{user_response[:300]}

Верни JSON:
{{"topic": "название темы кратко", "key_point": "главная мысль в 1 предложение", "understood": true/false, "difficulty": "easy/medium/hard"}}"""

        resp, _ = await ask([{"role": "user", "content": prompt}], config.MODEL)
        
        try:
            clean = resp.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(clean)
        except:
            return
        
        topic = data.get('topic', f'Шаг {step}')
        key_point = data.get('key_point', '')
        difficulty = data.get('difficulty', 'medium')
        
        if data.get('understood', True):
            await db.add_completed_topic(course_id, step, topic, [key_point], difficulty)
        else:
            await db.add_problem_zone(course_id, step, topic, key_point)
            
    except Exception as e:
        print(f"Save step progress error: {e}")


def build_smart_context(course_mem: dict, current_step: int, student_name: str = None) -> str:
    """Строит умный контекст с персонализацией и связями между шагами"""
    if not course_mem:
        parts = []
        if student_name:
            parts.append(f"👤 СТУДЕНТ: {student_name}")
        return "\n".join(parts)
    
    parts = []
    
    # Имя студента с инструкцией КОГДА использовать
    if student_name:
        parts.append(f"👤 СТУДЕНТ: {student_name}")
        parts.append(f"   📌 Называй по имени:")
        parts.append(f"      - После правильного ответа: '{student_name}, отлично!'")
        parts.append(f"      - Каждые 2-4 шага для закрепления связи")
        parts.append(f"      - При похвале за сложную тему")
        parts.append(f"      - НЕ в каждом сообщении (это навязчиво)")
    
    # Проблемные зоны
    problems = course_mem.get('problem_zones', [])
    if isinstance(problems, str):
        try:
            problems = json.loads(problems)
        except:
            problems = []
    
    if problems:
        parts.append("")
        parts.append("⚠️ ПРОБЛЕМНЫЕ ТЕМЫ (где были трудности):")
        for p in problems[-7:]:
            step = p.get('step', '?')
            topic = p.get('topic', '?')
            question = p.get('question', '')[:100]
            parts.append(f"   • Шаг {step} [{topic}]: {question}")
        parts.append("")
        parts.append("   🔗 ОБЯЗАТЕЛЬНО при связи с проблемной темой:")
        parts.append("      'Помнишь на шаге X было сложно с Y? Сейчас разберём похожее, но проще'")
    
    # Усвоенные темы
    topics = course_mem.get('completed_topics', [])
    if isinstance(topics, str):
        try:
            topics = json.loads(topics)
        except:
            topics = []
    
    if topics:
        parts.append("")
        parts.append("✅ ПРОЙДЕННЫЕ ТЕМЫ (ссылайся на них!):")
        
        for t in topics[-12:]:
            if isinstance(t, dict):
                step = t.get('step', '?')
                name = t.get('topic', str(t))
                key = t.get('key_points', [''])[0] if t.get('key_points') else ''
                diff = t.get('difficulty', '')
                
                marker = "🟢" if diff == "easy" else "🟡" if diff == "medium" else "🔴"
                entry = f"   {marker} Шаг {step}: {name}"
                if key:
                    entry += f" — {key[:60]}"
                parts.append(entry)
            else:
                parts.append(f"   • {t}")
    
    # Инструкции по связям
    if topics or problems:
        parts.append("")
        parts.append("🧠 СВЯЗЫВАЙ УРОКИ (это важно!):")
        parts.append("   • 'Это похоже на шаг X, но здесь мы углубимся...'")
        parts.append("   • 'Ты уже знаешь X, поэтому Y будет легко понять'")
        parts.append("   • 'Помнишь принцип из шага X? Он работает и тут'")
        if current_step > 5:
            parts.append(f"   • Мы на шаге {current_step} — покажи прогресс!")
    
    return "\n".join(parts)
