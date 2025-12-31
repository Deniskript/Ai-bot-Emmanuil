import asyncio
import psutil
from database import db

async def collect_metrics():
    """Собирает метрики каждые 30 сек"""
    while True:
        try:
            cpu = psutil.cpu_percent(interval=1)
            
            stats = await db.get_stats()
            active = stats.get('users', 0)
            reqs = stats.get('reqs', 0)
            
            rpm = reqs // max(1, (active or 1))
            avg_time = 2.5
            
            await db.save_metrics(
                load_pct=int(cpu),
                active_users=active,
                rpm=rpm,
                avg_time=avg_time
            )
        except Exception as e:
            print(f"Metrics error: {e}")
        
        await asyncio.sleep(30)
