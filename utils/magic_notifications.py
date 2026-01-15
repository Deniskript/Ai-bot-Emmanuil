"""
Ежедневные уведомления гороскопа
"""
import asyncio
from datetime import date, datetime, timedelta
from typing import Optional

from utils.openrouter import ask
from utils.magic_calculations import zodiac_sign
from prompts.magic_prompts import HOROSCOPE_SYSTEM_PROMPT
from database import postgres_db


def _should_send_today(last_sent: Optional[date]) -> bool:
    """Проверить, отправляли ли уже сегодня."""
    return last_sent != date.today()


async def build_daily_horoscope(profile: dict) -> str:
    """Сформировать дневной гороскоп по профилю."""
    zodiac = zodiac_sign(profile.get("birth_date", ""))
    base = (
        f"Пользователь: знак зодиака {zodiac}. "
        f"Дата рождения: {profile.get('birth_date')}. "
        f"Место рождения: {profile.get('birth_place', 'не указано')}. "
        "Сделай короткий персональный гороскоп на сегодня (6-8 предложений)."
    )
    messages = [
        {"role": "system", "content": HOROSCOPE_SYSTEM_PROMPT},
        {"role": "user", "content": base}
    ]
    text, _ = await ask(messages, model="anthropic/claude-sonnet-4.5")
    return text


async def run_magic_horoscope_notifier(bot):
    """Фоновая задача: отправка ежедневного гороскопа."""
    while True:
        try:
            profiles = await postgres_db.get_magic_horoscope_profiles()
            now_utc = datetime.utcnow()
            for profile in profiles:
                notify_time = profile.get("notify_time")
                if not notify_time:
                    continue
                tz_offset = int(profile.get("tz_offset", 0))
                local_time = now_utc - timedelta(minutes=tz_offset)
                hhmm = local_time.strftime("%H:%M")
                last_sent = profile.get("last_sent_date")
                if hhmm == notify_time and _should_send_today(last_sent):
                    text = await build_daily_horoscope(profile)
                    await bot.send_message(
                        profile["user_id"],
                        f"🔮 <b>Ваш гороскоп на сегодня</b>\n\n{text}",
                        parse_mode="HTML"
                    )
                    await postgres_db.update_magic_horoscope_last_sent(
                        profile["user_id"], date.today()
                    )
            await asyncio.sleep(60)
        except Exception:
            await asyncio.sleep(30)
