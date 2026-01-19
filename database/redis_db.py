"""
Redis модуль для real-time данных
- Настройки Luca (перенос из существующего кода)
- Настройки Silas (кэш)
- Парные сессии Silas (real-time)
"""

import redis
import json
import os
from typing import Optional, List

# Инициализация подключения
try:
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    redis_client = redis.from_url(redis_url, decode_responses=True)
    redis_client.ping()
    print("✅ Redis connected (redis_db module)")
except Exception as e:
    print(f"⚠️ Redis connection failed: {e}")
    redis_client = None


# ========== LUCA НАСТРОЙКИ ==========

def get_luca_settings(user_id: int) -> dict:
    """Получить настройки Luca из Redis"""
    try:
        if redis_client:
            data = redis_client.hgetall(f"luca:settings:{user_id}")
            if data:
                return {
                    'character': data.get('character', 'soul'),
                    'voice_enabled': data.get('voice_enabled', '0') == '1',
                    'voice_gender': 'male'
                }
    except Exception as e:
        print(f"Redis error in get_luca_settings: {e}")
    
    return {'character': 'soul', 'voice_enabled': False, 'voice_gender': 'male'}


def set_luca_settings(user_id: int, character: str = None, voice_enabled: bool = None):
    """Сохранить настройки Luca в Redis"""
    try:
        if redis_client:
            key = f"luca:settings:{user_id}"
            current = redis_client.hgetall(key) or {}
            
            mapping = {
                'character': character if character else current.get('character', 'soul'),
                'voice_enabled': '1' if voice_enabled else '0',
                'voice_gender': 'male'
            }
            redis_client.hset(key, mapping=mapping)
            return True
    except Exception as e:
        print(f"Redis error in set_luca_settings: {e}")
    return False


# ========== SILAS НАСТРОЙКИ (КЭШ) ==========

def get_silas_settings_cache(user_id: int) -> Optional[dict]:
    """Получить кэш настроек Silas из Redis"""
    try:
        if redis_client:
            data = redis_client.hgetall(f"silas:settings:{user_id}")
            if data:
                return {
                    'duration': int(data.get('duration', 30)),
                    'voice_enabled': data.get('voice_enabled', '0') == '1',
                    'mood': data.get('mood', ''),
                    'custom_mood': data.get('custom_mood', '')
                }
    except Exception as e:
        print(f"Redis error in get_silas_settings_cache: {e}")
    return None


def set_silas_settings_cache(user_id: int, duration: int = None, voice_enabled: bool = None, 
                              mood: str = None, custom_mood: str = None):
    """Сохранить настройки Silas в Redis кэш (TTL 1 час)"""
    try:
        if redis_client:
            key = f"silas:settings:{user_id}"
            current = redis_client.hgetall(key) or {}
            
            mapping = {}
            if duration is not None:
                mapping['duration'] = str(duration)
            elif current.get('duration'):
                mapping['duration'] = current['duration']
            else:
                mapping['duration'] = '30'
                
            if voice_enabled is not None:
                mapping['voice_enabled'] = '1' if voice_enabled else '0'
            elif current.get('voice_enabled'):
                mapping['voice_enabled'] = current['voice_enabled']
            else:
                mapping['voice_enabled'] = '0'
                
            if mood is not None:
                mapping['mood'] = mood
            elif current.get('mood'):
                mapping['mood'] = current['mood']
            else:
                mapping['mood'] = ''
                
            if custom_mood is not None:
                mapping['custom_mood'] = custom_mood
            elif current.get('custom_mood'):
                mapping['custom_mood'] = current['custom_mood']
            else:
                mapping['custom_mood'] = ''
            
            redis_client.hset(key, mapping=mapping)
            redis_client.expire(key, 3600)  # TTL 1 час
            return True
    except Exception as e:
        print(f"Redis error in set_silas_settings_cache: {e}")
    return False


def clear_silas_settings_cache(user_id: int):
    """Очистить кэш настроек Silas"""
    try:
        if redis_client:
            redis_client.delete(f"silas:settings:{user_id}")
    except Exception as e:
        print(f"Redis error in clear_silas_settings_cache: {e}")


# ========== TITUS НАСТРОЙКИ (УДАЛЕНО) ==========
# Функции настроек голоса Titus больше не нужны


# ========== ПАРНЫЕ СЕССИИ SILAS (REAL-TIME) ==========

def set_pair_session_cache(code: str, data: dict, ttl: int = 86400):
    """Сохранить данные парной сессии в Redis (TTL 24 часа)"""
    try:
        if redis_client:
            key = f"silas:pair:{code.upper()}"
            redis_client.hset(key, mapping={
                'topic': data.get('topic', ''),
                'user1_id': str(data.get('user1_id', '')),
                'user2_id': str(data.get('user2_id', '')),
                'status': data.get('status', 'waiting'),
                'user1_description': data.get('user1_description', ''),
                'user2_description': data.get('user2_description', '')
            })
            redis_client.expire(key, ttl)
            return True
    except Exception as e:
        print(f"Redis error in set_pair_session_cache: {e}")
    return False


def get_pair_session_cache(code: str) -> Optional[dict]:
    """Получить данные парной сессии из Redis"""
    try:
        if redis_client:
            data = redis_client.hgetall(f"silas:pair:{code.upper()}")
            if data:
                return {
                    'topic': data.get('topic', ''),
                    'user1_id': int(data['user1_id']) if data.get('user1_id') else None,
                    'user2_id': int(data['user2_id']) if data.get('user2_id') else None,
                    'status': data.get('status', 'waiting'),
                    'user1_description': data.get('user1_description', ''),
                    'user2_description': data.get('user2_description', '')
                }
    except Exception as e:
        print(f"Redis error in get_pair_session_cache: {e}")
    return None


def delete_pair_session_cache(code: str):
    """Удалить данные парной сессии из Redis"""
    try:
        if redis_client:
            redis_client.delete(f"silas:pair:{code.upper()}")
            redis_client.delete(f"silas:pair:{code.upper()}:typing")
            redis_client.delete(f"silas:pair:{code.upper()}:online")
    except Exception as e:
        print(f"Redis error in delete_pair_session_cache: {e}")


def set_user_pair_session(user_id: int, code: str):
    """Привязать пользователя к парной сессии"""
    try:
        if redis_client:
            redis_client.set(f"silas:pair:user:{user_id}", code.upper(), ex=86400)
    except Exception as e:
        print(f"Redis error in set_user_pair_session: {e}")


def get_user_pair_session(user_id: int) -> Optional[str]:
    """Получить код парной сессии пользователя"""
    try:
        if redis_client:
            return redis_client.get(f"silas:pair:user:{user_id}")
    except Exception as e:
        print(f"Redis error in get_user_pair_session: {e}")
    return None


def clear_user_pair_session(user_id: int):
    """Отвязать пользователя от парной сессии"""
    try:
        if redis_client:
            redis_client.delete(f"silas:pair:user:{user_id}")
    except Exception as e:
        print(f"Redis error in clear_user_pair_session: {e}")


# ========== TYPING / ONLINE СТАТУСЫ ==========

def set_typing(code: str, user_id: int):
    """Установить статус "печатает" (TTL 5 сек)"""
    try:
        if redis_client:
            key = f"silas:pair:{code.upper()}:typing"
            redis_client.set(key, str(user_id), ex=5)
    except Exception as e:
        print(f"Redis error in set_typing: {e}")


def get_typing(code: str) -> Optional[int]:
    """Получить ID пользователя который печатает"""
    try:
        if redis_client:
            uid = redis_client.get(f"silas:pair:{code.upper()}:typing")
            return int(uid) if uid else None
    except Exception as e:
        print(f"Redis error in get_typing: {e}")
    return None


def set_online(code: str, user_id: int):
    """Установить статус "онлайн" (TTL 30 сек)"""
    try:
        if redis_client:
            key = f"silas:pair:{code.upper()}:online:{user_id}"
            redis_client.set(key, "1", ex=30)
    except Exception as e:
        print(f"Redis error in set_online: {e}")


def is_online(code: str, user_id: int) -> bool:
    """Проверить онлайн ли пользователь"""
    try:
        if redis_client:
            return redis_client.exists(f"silas:pair:{code.upper()}:online:{user_id}") > 0
    except Exception as e:
        print(f"Redis error in is_online: {e}")
    return False


# ========== ИСТОРИЯ ЧАТА ПАРНЫХ СЕССИЙ ==========

def add_pair_chat_message(code: str, message: dict):
    """Добавить сообщение в историю чата парной сессии"""
    try:
        if redis_client:
            key = f"silas:pair:{code.upper()}:chat"
            # Используем список для хранения сообщений
            messages_json = redis_client.get(key)
            messages = json.loads(messages_json) if messages_json else []
            messages.append(message)
            # Ограничиваем историю последними 100 сообщениями
            if len(messages) > 100:
                messages = messages[-100:]
            redis_client.set(key, json.dumps(messages), ex=86400)  # TTL 24 часа
    except Exception as e:
        print(f"Redis error in add_pair_chat_message: {e}")


def get_pair_chat_history(code: str) -> list:
    """Получить историю чата парной сессии"""
    try:
        if redis_client:
            key = f"silas:pair:{code.upper()}:chat"
            messages_json = redis_client.get(key)
            if messages_json:
                return json.loads(messages_json)
    except Exception as e:
        print(f"Redis error in get_pair_chat_history: {e}")
    return []


def clear_pair_chat_history(code: str):
    """Очистить историю чата парной сессии"""
    try:
        if redis_client:
            redis_client.delete(f"silas:pair:{code.upper()}:chat")
    except Exception as e:
        print(f"Redis error in clear_pair_chat_history: {e}")


# ========== УНИВЕРСАЛЬНЫЙ КЭШ ==========

def get_cache(key: str) -> Optional[dict]:
    """Получить данные из кэша по ключу"""
    try:
        if redis_client:
            data = redis_client.get(f"cache:{key}")
            if data:
                return json.loads(data)
    except Exception as e:
        print(f"Redis error in get_cache: {e}")
    return None


def set_cache(key: str, data: dict, ttl: int = 3600):
    """Сохранить данные в кэш"""
    try:
        if redis_client:
            redis_client.setex(f"cache:{key}", ttl, json.dumps(data, ensure_ascii=False))
    except Exception as e:
        print(f"Redis error in set_cache: {e}")
