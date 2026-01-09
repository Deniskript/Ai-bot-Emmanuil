import time
from collections import defaultdict
from database import db


class AIAntiFlood:
    def __init__(self):
        self.users_data = defaultdict(lambda: {
            'last_request': 0,
            'request_count': 0,
            'window_start': 0,
            'blocked_until': 0
        })
        self.window_size = 60
        self.block_duration = 60
    
    async def check(self, user_id: int) -> tuple[bool, str]:
        """Возвращает (можно ли делать запрос, сообщение об ошибке)"""
        min_interval = int(await db.get_setting('spam_interval') or '2')
        max_rpm = int(await db.get_setting('spam_max_rpm') or '8')
        
        current_time = time.time()
        user_data = self.users_data[user_id]
        
        # Проверка блокировки
        if current_time < user_data['blocked_until']:
            remaining = int(user_data['blocked_until'] - current_time)
            return False, f"⏳ Подожди {remaining} сек"
        
        # Сброс окна
        if current_time - user_data['window_start'] > self.window_size:
            user_data['request_count'] = 0
            user_data['window_start'] = current_time
        
        # Проверка интервала
        time_since_last = current_time - user_data['last_request']
        if time_since_last < min_interval and user_data['last_request'] > 0:
            return False, f"⏳ Подожди {int(min_interval - time_since_last)} сек"
        
        # Проверка лимита в минуту
        if user_data['request_count'] >= max_rpm:
            user_data['blocked_until'] = current_time + self.block_duration
            return False, "🚫 Лимит запросов. Подожди минуту"
        
        # Всё ок — обновляем
        user_data['last_request'] = current_time
        user_data['request_count'] += 1
        return True, ""


# Глобальный экземпляр
ai_flood = AIAntiFlood()
