from database import db
from utils.ai_client import ask
import json


ANALYZE_PROMPT = """Проанализируй ответ ученика.

Шаг: {step}
Учитель: {bot_msg}
Ученик: {user_msg}

Ответь ТОЛЬКО JSON:
{{"asks_clarification": true/false, "answer_correct": true/false/null, "ready_next": true/false, "problem_topic": "тема" или null, "understood_topic": "тема" или null}}"""


async def analyze_student_response(course_id: int, step: int, bot_msg: str, user_msg: str) -> dict:
    try:
        prompt = ANALYZE_PROMPT.format(step=step, bot_msg=bot_msg[:400], user_msg=user_msg[:300])
        msgs = [{"role": "user", "content": prompt}]
        resp, _ = await ask(msgs, "gpt-4o-mini")
        
        start = resp.find('{')
        end = resp.rfind('}') + 1
        if start == -1 or end <= start:
            return {}
        
        data = json.loads(resp[start:end])
        
        if data.get('asks_clarification') or data.get('answer_correct') == False:
            topic = data.get('problem_topic') or f"Шаг {step}"
            await db.add_problem_zone(course_id, step, topic, user_msg[:150])
        
        if data.get('answer_correct') == True and data.get('understood_topic'):
            await remove_problem_zone(course_id, data['understood_topic'])
            await db.add_completed_topic(course_id, step, data['understood_topic'], [])
        
        return data
    except Exception as e:
        print(f"Analyze error: {e}")
        return {}


async def remove_problem_zone(course_id: int, topic: str):
    try:
        mem = await db.get_course_memory(course_id)
        zones = mem.get('problem_zones', [])
        zones = [z for z in zones if topic.lower() not in z.get('topic', '').lower()]
        await db.save_course_memory(course_id, problem_zones=zones)
    except:
        pass


async def should_review_problems(course_id: int, msg_count: int) -> dict:
    if msg_count % 8 != 0:
        return None
    mem = await db.get_course_memory(course_id)
    problems = mem.get('problem_zones', [])
    if not problems:
        return None
    return problems[0]


def build_course_context(course_mem: dict) -> str:
    parts = []
    
    if course_mem.get('summary'):
        parts.append(f"ПРОГРЕСС: {course_mem['summary']}")
    
    topics = course_mem.get('completed_topics', [])[-8:]
    if topics:
        parts.append(f"УСВОЕНО: {', '.join([t['topic'] for t in topics])}")
    
    problems = course_mem.get('problem_zones', [])
    if problems:
        parts.append(f"ПРОБЛЕМНЫЕ ЗОНЫ: {', '.join([p['topic'] for p in problems[-5:]])}")
        parts.append("→ Периодически проверяй понимание проблемных тем!")
    
    return "\n".join(parts) if parts else ""
