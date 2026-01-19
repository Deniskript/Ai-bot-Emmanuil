"""
Titus Memory - система долгосрочной памяти для курсов
Оптимизирован для 1000+ пользователей
"""
import json
import logging

from utils.openrouter import ask
from database import postgres_db as db
import config

logger = logging.getLogger(__name__)


async def save_step_progress(course_id: int, step: int, bot_message: str, user_response: str):
    """Сохраняет краткую суть пройденного шага"""
    logger.debug(f"save_step_progress: course_id={course_id}, step={step}")
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
        except Exception as e:
            logger.warning(f"save_step_progress parse error: {e}")
            return
        
        topic = data.get('topic', f'Шаг {step}')
        key_point = data.get('key_point', '')
        difficulty = data.get('difficulty', 'medium')
        
        if data.get('understood', True):
            await add_completed_topic(course_id, step, topic, [key_point], difficulty)
        else:
            await add_problem_zone(course_id, step, topic, key_point)
        logger.debug("save_step_progress: SUCCESS")
            
    except Exception as e:
        logger.error(f"save_step_progress error: {e}", exc_info=True)


async def add_completed_topic(course_id: int, step: int, topic: str, key_points: list, difficulty: str = "medium"):
    """Добавляет пройденную тему в память курса"""
    logger.debug(f"add_completed_topic: course_id={course_id}, step={step}, topic={topic}")
    try:
        await db.add_completed_topic(course_id, step, topic, key_points, difficulty)
        logger.debug("add_completed_topic: SUCCESS")
    except Exception as e:
        logger.error(f"add_completed_topic error: {e}", exc_info=True)


async def add_problem_zone(course_id: int, step: int, topic: str, question: str):
    """Добавляет проблемную зону в память курса"""
    logger.debug(f"add_problem_zone: course_id={course_id}, step={step}, topic={topic}")
    try:
        await db.add_problem_zone(course_id, step, topic, question)
        logger.debug("add_problem_zone: SUCCESS")
    except Exception as e:
        logger.error(f"add_problem_zone error: {e}", exc_info=True)


def build_smart_context(course_mem: dict, current_step: int, student_name: str = None) -> str:
    """
    Строит умный контекст с персонализацией и связями между шагами.
    
    Args:
        course_mem: Данные памяти курса из БД
        current_step: Текущий шаг курса
        student_name: Имя студента для персонализации
        
    Returns:
        Строка контекста для системного промпта
    """
    logger.debug(f"build_smart_context: step={current_step}, has_mem={bool(course_mem)}")
    
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
        logger.debug(f"build_smart_context: {len(problems)} problem zones")
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
        logger.debug(f"build_smart_context: {len(topics)} completed topics")
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
