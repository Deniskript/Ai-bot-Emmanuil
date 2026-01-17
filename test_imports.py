import asyncio
from database.postgres_db import PostgresDB
from utils.stars import calculate_stars
from utils.balance_guard import ensure_balance, get_no_stars_keyboard
from config import STAR_PACKAGES, MIN_STARS, NEW_USER_BONUS, SUBSCRIPTIONS

print("✅ Все импорты работают")
print(f"STAR_PACKAGES: {STAR_PACKAGES}")
print(f"MIN_STARS: {MIN_STARS}")
print(f"NEW_USER_BONUS: {NEW_USER_BONUS}")
