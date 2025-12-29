import json
from database import db
from utils.ai_client import get_ai_response
from config import MEMORY_REFRESH_INTERVAL, MAX_HISTORY_WITH_MEMORY

def safe_json_load(data, default):
    if data is None:
        return default
    if isinstance(data, list):
        return data
    if isinstance(data, str):
        try:
            return json.loads(data)
        except:
            return default
    return default

async def get_messages_with_memory(user_id: int):
    memory = await db.get_user_memory(user_id)
    messages = await db.get_messages(user_id, limit=MAX_HISTORY_WITH_MEMORY)
    result = []
    
    if memory and memory.get('memory_enabled'):
        memory_parts = []
        facts = safe_json_load(memory.get('important_facts'), [])
        problems = safe_json_load(memory.get('problems'), [])
        interests = safe_json_load(memory.get('interests'), [])
        
        if facts:
            memory_parts.append("Znayu: " + "; ".join(str(f) for f in facts[:5]))
        if problems:
            memory_parts.append("Problemy: " + "; ".join(str(p) for p in problems[:3]))
        if interests:
            memory_parts.append("Interesy: " + "; ".join(str(i) for i in interests[:3]))
        
        if memory_parts:
            memory_text = "\n".join(memory_parts)
            result.append({"role": "system", "content": "[MEMORY]\n" + memory_text[:600]})
    
    for msg in reversed(messages):
        result.append({"role": msg['role'], "content": msg['content']})
    return result

async def update_memory(user_id: int, user_message: str, assistant_response: str):
    memory = await db.get_user_memory(user_id)
    if not memory or not memory.get('memory_enabled'):
        return
    
    counter = memory.get('request_counter', 0) + 1
    if counter < MEMORY_REFRESH_INTERVAL:
        await db.update_memory_counter(user_id, counter)
        return
    
    await db.update_memory_counter(user_id, 0)
    facts = safe_json_load(memory.get('important_facts'), [])
    problems = safe_json_load(memory.get('problems'), [])
    interests = safe_json_load(memory.get('interests'), [])
    
    try:
        prompt = 'Extract: {"name":"","problem":"","fact":""} or {}'
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"U:{user_message}\nA:{assistant_response}"}
        ]
        response, _ = await get_ai_response(messages)
        response = response.strip()
        if response.startswith('{'):
            data = json.loads(response)
            if data.get('name') and data['name'] not in str(facts):
                facts.insert(0, f"Name: {data['name']}")
            if data.get('problem') and data['problem'] not in str(problems):
                problems.insert(0, data['problem'])
            if data.get('fact') and data['fact'] not in str(facts):
                facts.insert(0, data['fact'])
            
            new_data = {
                'important_facts': facts[:5],
                'problems': problems[:3],
                'interests': interests[:3],
                'personal_prompt': memory.get('personal_prompt', ''),
                'lessons_completed': memory.get('lessons_completed', [])
            }
            await db.update_user_memory(user_id, new_data)
    except:
        pass
