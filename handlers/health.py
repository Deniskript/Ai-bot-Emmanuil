"""
Хендлеры для раздела Здоровье
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import reply, inline
from utils.openrouter import ask
from utils.calories import (
    parse_calories_response, calculate_bmr, calculate_tdee, 
    calculate_macros, format_date, get_meal_time, format_calories_summary
)
from utils.markdown import md_to_html
from config import OPENAI_API_KEY as PROXYAPI_KEY
import base64
import aiohttp
import os
import tempfile
from datetime import datetime, date, timedelta

router = Router()


class HealthStates(StatesGroup):
    """Состояния для раздела Здоровье"""
    menu = State()
    calories_menu = State()
    wait_photo = State()
    wait_manual_input = State()
    confirm_save = State()
    journal_menu = State()
    nutrition_menu = State()
    wait_goal_data = State()


# ========== ГЛАВНОЕ МЕНЮ ЗДОРОВЬЯ ==========

@router.message(F.text == "🍎 Здоровье")
async def health_menu(msg: Message, state: FSMContext):
    """Главное меню раздела Здоровье"""
    await state.set_state(HealthStates.menu)
    
    # Получаем статистику за сегодня
    today_stats = await db.get_today_calories(msg.from_user.id)
    goal = await db.get_nutrition_goal(msg.from_user.id)
    
    text = "🍎 <b>Здоровье</b>\n\n"
    text += "Следи за питанием и достигай целей!\n\n"
    
    if today_stats['calories'] > 0:
        text += "📊 <b>Сегодня:</b>\n"
        text += format_calories_summary(today_stats, goal)
    else:
        text += "<i>Сегодня ещё нет записей</i>"
    
    await msg.answer(text, parse_mode="HTML", reply_markup=reply.health_kb(msg.from_user.id))


# ========== ПОДСЧЁТ КАЛОРИЙ ==========

@router.message(HealthStates.menu, F.text == "🍽 Подсчёт калорий")
async def calories_menu(msg: Message, state: FSMContext):
    """Меню подсчёта калорий"""
    await state.set_state(HealthStates.calories_menu)
    await msg.answer(
        "🍽 <b>Подсчёт калорий</b>\n\n"
        "📸 <b>По фото</b> — сфоткай еду, я определю калории\n"
        "✏️ <b>Вручную</b> — напиши что съел\n\n"
        "Выбери способ:",
        parse_mode="HTML",
        reply_markup=reply.calories_menu_kb()
    )


@router.message(HealthStates.calories_menu, F.text == "📸 По фото")
async def wait_food_photo(msg: Message, state: FSMContext):
    """Ожидание фото еды"""
    await state.set_state(HealthStates.wait_photo)
    await msg.answer(
        "📸 <b>Отправь фото еды</b>\n\n"
        "Я определю:\n"
        "• Что это за блюдо\n"
        "• Примерный вес порции\n"
        "• Калории, белки, жиры, углеводы",
        parse_mode="HTML"
    )


@router.message(HealthStates.wait_photo, F.photo)
async def analyze_food_photo(msg: Message, state: FSMContext):
    """Анализ фото еды через ProxyAPI Vision"""
    processing = await msg.answer("🔍 Анализирую фото...")
    
    try:
        # Скачиваем фото
        photo = msg.photo[-1]
        file = await msg.bot.get_file(photo.file_id)
        
        # Создаём временный файл
        temp_dir = tempfile.mkdtemp(prefix="food_")
        photo_path = os.path.join(temp_dir, "food.jpg")
        
        await msg.bot.download_file(file.file_path, photo_path)
        
        # Читаем и конвертируем в base64
        with open(photo_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode()
        
        # Промпт для анализа
        prompt = """
Проанализируй фото еды и определи:
1. Название блюда/продукта
2. Примерный вес порции
3. Калории (ккал)
4. Белки (г)
5. Жиры (г)
6. Углеводы (г)

Ответь в формате:
🍽 Блюдо: [название]
⚖️ Порция: [вес]
🔥 Калории: [число] ккал
🥩 Белки: [число] г
🧈 Жиры: [число] г
🍞 Углеводы: [число] г
"""
        
        # Запрос к ProxyAPI Vision
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
        ]
        
        headers = {
            "Authorization": f"Bearer {PROXYAPI_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 500
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.proxyapi.ru/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise Exception(f"ProxyAPI Error: {error}")
                
                result = await resp.json()
                response = result["choices"][0]["message"]["content"]
        
        # Парсим ответ
        parsed = parse_calories_response(response)
        await state.update_data(food_data=parsed)
        
        # Списываем токены (Vision запрос ~ 300 токенов с маржой)
        await db.use_tokens_smart(msg.from_user.id, 300, bot_name='health')
        await db.increment_requests(msg.from_user.id)
        
        # Очищаем временные файлы
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        await processing.delete()
        await msg.answer(
            f"{response}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Записать в журнал?",
            parse_mode="HTML",
            reply_markup=inline.save_calories_kb()
        )
        
    except Exception as e:
        await processing.edit_text(f"❌ Ошибка анализа фото:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")


@router.message(HealthStates.calories_menu, F.text == "✏️ Записать вручную")
async def wait_manual_input(msg: Message, state: FSMContext):
    """Ожидание ручного ввода"""
    await state.set_state(HealthStates.wait_manual_input)
    await msg.answer(
        "✏️ <b>Напиши что съел</b>\n\n"
        "<b>Примеры:</b>\n"
        "• Картошка жареная 100г и сало 50г\n"
        "• Борщ тарелка и хлеб 2 куска\n"
        "• Кофе с молоком и круассан\n\n"
        "Пиши 👇",
        parse_mode="HTML"
    )


@router.message(HealthStates.wait_manual_input, F.text)
async def analyze_manual_input(msg: Message, state: FSMContext):
    """Анализ текстового описания еды"""
    if msg.text.startswith("◀️"):
        await state.set_state(HealthStates.calories_menu)
        await calories_menu(msg, state)
        return
    
    processing = await msg.answer("🔍 Считаю калории...")
    
    try:
        prompt = f"""
Пользователь съел: {msg.text}

Рассчитай калории и БЖУ для каждого продукта.

Ответь в формате:
🍽 Блюдо: [название всех продуктов]
⚖️ Порция: [общий вес]
🔥 Калории: [сумма] ккал
🥩 Белки: [сумма] г
🧈 Жиры: [сумма] г
🍞 Углеводы: [сумма] г

Если несколько продуктов — покажи каждый отдельно, потом сумму.
"""
        
        messages = [{"role": "user", "content": prompt}]
        response, tokens_used = await ask(messages, "anthropic/claude-sonnet-4.5", max_tokens=800)
        
        # Парсим ответ
        parsed = parse_calories_response(response)
        if not parsed['name']:
            parsed['name'] = msg.text[:50]

        await state.update_data(food_data=parsed)
        
        # Списываем токены с маржой 2.5x
        await db.use_tokens_smart(msg.from_user.id, tokens_used, bot_name='health')
        await db.increment_requests(msg.from_user.id)
        
        await processing.delete()
        await msg.answer(
            f"{md_to_html(response)}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Записать в журнал?",
            parse_mode="HTML",
            reply_markup=inline.save_calories_kb()
        )
        
    except Exception as e:
        await processing.edit_text(f"❌ Ошибка:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")


# ========== СОХРАНЕНИЕ В ЖУРНАЛ ==========

@router.callback_query(F.data == "save_calories")
async def save_to_journal(callback: CallbackQuery, state: FSMContext):
    """Сохранить калории в журнал"""
    try:
        data = await state.get_data()
        food_data = data.get("food_data")
        
        if not food_data:
            await callback.answer("❌ Нет данных для сохранения")
            print(f"[ERROR] No food_data in state for user {callback.from_user.id}")
            return
        
        # Логируем для отладки
        print(f"[DEBUG] Saving calories for user {callback.from_user.id}: {food_data}")
        
        # Сохраняем в БД
        await db.save_calories_log(
            user_id=callback.from_user.id,
            food_name=food_data.get("name", "Неизвестно"),
            portion=food_data.get("portion", ""),
            calories=int(food_data.get("calories", 0)),
            protein=float(food_data.get("protein", 0)),
            fat=float(food_data.get("fat", 0)),
            carbs=float(food_data.get("carbs", 0))
        )
        
        print(f"[DEBUG] Calories saved successfully for user {callback.from_user.id}")
        
        # Получаем статистику на сегодня
        today_stats = await db.get_today_calories(callback.from_user.id)
        goal = await db.get_nutrition_goal(callback.from_user.id)
        
        text = "✅ <b>Записано в журнал!</b>\n\n"
        text += "📊 <b>Сегодня:</b>\n"
        text += format_calories_summary(today_stats, goal)
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer("Сохранено!")
        
        await state.set_state(HealthStates.menu)
        
    except Exception as e:
        print(f"[ERROR] Error saving calories: {e}")
        import traceback
        traceback.print_exc()
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(F.data == "skip_calories")
async def skip_save(callback: CallbackQuery, state: FSMContext):
    """Не сохранять в журнал"""
    await callback.message.edit_text("👌 Не записываю")
    await callback.answer()
    await state.set_state(HealthStates.menu)


# ========== ЖУРНАЛ КАЛОРИЙ ==========

@router.message(HealthStates.menu, F.text == "📊 Журнал калорий")
async def journal_menu(msg: Message, state: FSMContext):
    """Меню журнала калорий"""
    await state.set_state(HealthStates.journal_menu)
    await msg.answer(
        "📊 <b>Журнал калорий</b>\n\n"
        "Выбери период:",
        parse_mode="HTML",
        reply_markup=reply.journal_menu_kb()
    )


@router.message(HealthStates.journal_menu, F.text == "📅 Сегодня")
async def show_today(msg: Message, state: FSMContext):
    """Показать записи за сегодня"""
    try:
        logs = await db.get_calories_logs(msg.from_user.id, days=0)
        
        print(f"[DEBUG] Found {len(logs)} logs for user {msg.from_user.id}")
        
        if not logs:
            await msg.answer(
                "📭 <b>Сегодня записей нет</b>\n\n"
                "Добавь первую запись через\n"
                "🍽 Подсчёт калорий",
                parse_mode="HTML"
            )
            return
        
        text = "📅 <b>Сегодня</b>\n\n"
        total_cal = 0
        total_protein = 0.0
        total_fat = 0.0
        total_carbs = 0.0
        
        for log in logs:
            # Обрабатываем время
            if isinstance(log['time'], str):
                time_str = log['time'][:5]  # Берём первые 5 символов (HH:MM)
            else:
                time_str = log['time'].strftime('%H:%M') if log['time'] else "00:00"
            
            text += f"🕐 {time_str} — <b>{log['food_name']}</b>\n"
            text += f"    {log['calories']} ккал | Б:{log['protein']}г Ж:{log['fat']}г У:{log['carbs']}г\n\n"
            
            total_cal += log['calories'] or 0
            total_protein += log['protein'] or 0
            total_fat += log['fat'] or 0
            total_carbs += log['carbs'] or 0
        
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += f"<b>ИТОГО:</b>\n"
        text += f"🔥 {total_cal} ккал\n"
        text += f"🥩 Белки: {total_protein:.1f}г\n"
        text += f"🧈 Жиры: {total_fat:.1f}г\n"
        text += f"🍞 Углеводы: {total_carbs:.1f}г"
        
        # Добавляем прогресс по цели
        goal = await db.get_nutrition_goal(msg.from_user.id)
        if goal:
            remaining = goal['daily_calories'] - total_cal
            if remaining > 0:
                text += f"\n\n📊 Осталось: {remaining:,} ккал"
            else:
                text += f"\n\n⚠️ Превышение: {abs(remaining):,} ккал"
        
        await msg.answer(text, parse_mode="HTML")
        
    except Exception as e:
        print(f"[ERROR] Error in show_today: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}", parse_mode="HTML")


@router.message(HealthStates.journal_menu, F.text == "📅 Вчера")
async def show_yesterday(msg: Message, state: FSMContext):
    """Показать записи за вчера"""
    logs = await db.get_calories_logs(msg.from_user.id, days=1)
    
    if not logs:
        await msg.answer("📭 Вчера записей нет")
        return
    
    text = "📅 <b>Вчера</b>\n\n"
    total_cal = 0
    total_protein = 0.0
    total_fat = 0.0
    total_carbs = 0.0
    
    for log in logs:
        time_str = log['time'] if isinstance(log['time'], str) else log['time'].strftime('%H:%M')
        text += f"🕐 {time_str} — {log['food_name']}\n"
        text += f"   {log['calories']} ккал | Б:{log['protein']}г Ж:{log['fat']}г У:{log['carbs']}г\n\n"
        total_cal += log['calories']
        total_protein += log['protein']
        total_fat += log['fat']
        total_carbs += log['carbs']
    
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += f"<b>ИТОГО:</b>\n"
    text += f"🔥 {total_cal} ккал\n"
    text += f"🥩 Белки: {total_protein:.1f}г\n"
    text += f"🧈 Жиры: {total_fat:.1f}г\n"
    text += f"🍞 Углеводы: {total_carbs:.1f}г"
    
    await msg.answer(text, parse_mode="HTML")


@router.message(HealthStates.journal_menu, F.text == "📅 Неделя")
async def show_week(msg: Message, state: FSMContext):
    """Показать статистику за неделю"""
    stats = await db.get_weekly_calories(msg.from_user.id)
    
    if not stats:
        await msg.answer("📭 За неделю записей нет")
        return
    
    text = "📅 <b>Статистика за 7 дней</b>\n\n"
    
    goal = await db.get_nutrition_goal(msg.from_user.id)
    goal_cal = goal['daily_calories'] if goal else 2000
    
    total_week = 0
    for day in stats:
        day_cal = day['calories']
        total_week += day_cal
        emoji = "✅" if day_cal <= goal_cal else "⚠️"
        date_str = day['date'] if isinstance(day['date'], str) else day['date'].strftime('%d.%m')
        text += f"{emoji} {date_str} — {day_cal:,} ккал\n"
    
    avg_cal = total_week // len(stats) if stats else 0
    
    text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 <b>Среднее в день:</b> {avg_cal:,} ккал\n"
    text += f"📈 <b>Всего за неделю:</b> {total_week:,} ккал"
    
    if goal:
        text += f"\n🎯 <b>Цель:</b> {goal_cal:,} ккал/день"
    
    await msg.answer(text, parse_mode="HTML")


@router.message(HealthStates.journal_menu, F.text == "📅 Месяц")
async def show_month(msg: Message, state: FSMContext):
    """Показать статистику за месяц"""
    stats = await db.get_monthly_calories(msg.from_user.id)
    
    if not stats:
        await msg.answer("📭 За месяц записей нет")
        return
    
    text = "📅 <b>Статистика за 30 дней</b>\n\n"
    
    total_month = sum(day['calories'] for day in stats)
    avg_cal = total_month // len(stats) if stats else 0
    
    text += f"📊 <b>Среднее в день:</b> {avg_cal:,} ккал\n"
    text += f"📈 <b>Всего за месяц:</b> {total_month:,} ккал\n"
    text += f"📅 <b>Дней с записями:</b> {len(stats)}"
    
    goal = await db.get_nutrition_goal(msg.from_user.id)
    if goal:
        text += f"\n🎯 <b>Цель:</b> {goal['daily_calories']:,} ккал/день"
    
    await msg.answer(text, parse_mode="HTML")


# ========== ПИТАНИЕ ==========

@router.message(HealthStates.menu, F.text == "🥗 Питание")
async def nutrition_menu(msg: Message, state: FSMContext):
    """Меню питания"""
    await state.set_state(HealthStates.nutrition_menu)
    
    goal = await db.get_nutrition_goal(msg.from_user.id)
    
    text = "🥗 <b>Питание</b>\n\n"
    if goal:
        text += "Персональные рекомендации на основе твоего журнала!"
    else:
        text += "Сначала установи цель, чтобы получать персональные советы!"
    
    await msg.answer(text, parse_mode="HTML", reply_markup=reply.nutrition_menu_kb())


@router.message(HealthStates.nutrition_menu, F.text == "📋 Что поесть сейчас?")
async def what_to_eat(msg: Message, state: FSMContext):
    """Рекомендации что поесть сейчас"""
    processing = await msg.answer("🔍 Анализирую твой журнал...")
    
    try:
        # Получаем данные
        goal = await db.get_nutrition_goal(msg.from_user.id)
        
        print(f"[DEBUG] what_to_eat: user {msg.from_user.id}, goal: {goal}")
        
        if not goal:
            await processing.edit_text(
                "⚠️ <b>Сначала установи цель!</b>\n\n"
                "Нажми 🎯 Моя цель и введи свои данные.\n"
                "Тогда я смогу давать персональные рекомендации.",
                parse_mode="HTML"
            )
            return
        
        today_stats = await db.get_today_calories(msg.from_user.id)
        current_hour = datetime.now().hour
        meal_time = get_meal_time()
        
        remaining_cal = goal['daily_calories'] - today_stats['calories']
        remaining_protein = goal['daily_protein'] - today_stats['protein']
        remaining_fat = goal['daily_fat'] - today_stats['fat']
        remaining_carbs = goal['daily_carbs'] - today_stats['carbs']
        
        goal_names = {"lose": "похудение", "maintain": "поддержание веса", "gain": "набор массы"}
        goal_name = goal_names.get(goal['goal'], "поддержание веса")
        
        prompt = f"""
Пользователь хочет узнать что поесть.

Данные:
- Цель: {goal_name}
- Дневная норма: {goal['daily_calories']} ккал
- Уже съедено: {today_stats['calories']} ккал
- Осталось: {remaining_cal} ккал
- Белков съедено: {today_stats['protein']:.1f}г из {goal['daily_protein']}г
- Жиров съедено: {today_stats['fat']:.1f}г из {goal['daily_fat']}г
- Углеводов съедено: {today_stats['carbs']:.1f}г из {goal['daily_carbs']}г
- Время: {current_hour}:00 ({meal_time})

Порекомендуй 2-3 варианта что поесть сейчас.
Учти сколько калорий осталось и время суток.

Формат ответа:
🍽 Осталось на сегодня: {remaining_cal} ккал

Рекомендую на {meal_time}:

1️⃣ [блюдо] — X ккал
   [почему подходит]

2️⃣ [блюдо] — X ккал
   [почему подходит]
"""
        
        print(f"[DEBUG] Sending prompt to OpenRouter")
        
        messages = [{"role": "user", "content": prompt}]
        response, tokens_used = await ask(messages, "anthropic/claude-sonnet-4.5", max_tokens=1000)
        
        print(f"[DEBUG] Got response from OpenRouter")
        
        # Списываем токены с маржой 2.5x
        await db.use_tokens_smart(msg.from_user.id, tokens_used, bot_name='health')
        await db.increment_requests(msg.from_user.id)
        
        await processing.delete()
        await msg.answer(md_to_html(response), parse_mode="HTML")
        
    except Exception as e:
        print(f"[ERROR] Error in what_to_eat: {e}")
        import traceback
        traceback.print_exc()
        await processing.delete()
        await msg.answer(f"❌ Ошибка:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")


@router.message(HealthStates.nutrition_menu, F.text == "📅 План на день")
async def day_plan(msg: Message, state: FSMContext):
    """Составить план питания на день"""
    processing = await msg.answer("📝 Составляю план...")
    
    try:
        goal = await db.get_nutrition_goal(msg.from_user.id)
        
        if not goal:
            await processing.edit_text(
                "⚠️ Сначала установи цель!\n\n"
                "Нажми <b>🎯 Моя цель</b> чтобы настроить",
                parse_mode="HTML"
            )
            return
        
        today_stats = await db.get_today_calories(msg.from_user.id)
        remaining_cal = goal['daily_calories'] - today_stats['calories']
        
        goal_names = {"lose": "похудение", "maintain": "поддержание веса", "gain": "набор массы"}
        goal_name = goal_names.get(goal['goal'], "поддержание веса")
        
        prompt = f"""
Составь план питания на остаток дня.

Данные:
- Цель: {goal_name}
- Дневная норма: {goal['daily_calories']} ккал
- Уже съедено: {today_stats['calories']} ккал
- Осталось: {remaining_cal} ккал
- Текущее время: {datetime.now().hour}:00

Распиши по приёмам пищи до конца дня.
Для каждого блюда укажи калории и БЖУ.
Учти цель пользователя ({goal_name}).

Формат:
🍽 [Приём пищи] (время)
• [Блюдо] — X ккал (Б:Xг Ж:Xг У:Xг)
• [Блюдо] — X ккал (Б:Xг Ж:Xг У:Xг)
"""
        
        messages = [{"role": "user", "content": prompt}]
        response, tokens_used = await ask(messages, "anthropic/claude-sonnet-4.5", max_tokens=1500)
        
        # Списываем токены с маржой 2.5x
        await db.use_tokens_smart(msg.from_user.id, tokens_used, bot_name='health')
        await db.increment_requests(msg.from_user.id)
        
        await processing.delete()
        await msg.answer(md_to_html(response), parse_mode="HTML")
        
    except Exception as e:
        await processing.edit_text(f"❌ Ошибка:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")


@router.message(HealthStates.nutrition_menu, F.text == "🎯 Моя цель")
async def my_goal(msg: Message, state: FSMContext):
    """Показать/установить цель"""
    goal = await db.get_nutrition_goal(msg.from_user.id)
    
    if goal:
        # Показываем текущую цель
        goal_names = {"lose": "🔻 Похудеть", "maintain": "⚖️ Поддержать вес", "gain": "🔺 Набрать массу"}
        goal_name = goal_names.get(goal['goal'], "⚖️ Поддержать вес")
        
        await msg.answer(
            f"🎯 <b>Твоя цель:</b> {goal_name}\n\n"
            f"📊 <b>Дневная норма:</b>\n"
            f"🔥 Калории: {goal['daily_calories']:,} ккал\n"
            f"🥩 Белки: {goal['daily_protein']}г\n"
            f"🧈 Жиры: {goal['daily_fat']}г\n"
            f"🍞 Углеводы: {goal['daily_carbs']}г\n\n"
            f"📏 Вес: {goal['weight']}кг | Рост: {goal['height']}см\n\n"
            "Хочешь изменить?",
            parse_mode="HTML",
            reply_markup=inline.goal_select_kb()
        )
    else:
        await msg.answer(
            "🎯 <b>Выбери цель</b>\n\n"
            "Это поможет рассчитать твою норму калорий:",
            parse_mode="HTML",
            reply_markup=inline.goal_select_kb()
        )


@router.callback_query(F.data.startswith("goal_"))
async def set_goal(callback: CallbackQuery, state: FSMContext):
    """Начать установку цели"""
    goal_type = callback.data.replace("goal_", "")  # lose/maintain/gain
    
    await state.update_data(goal_type=goal_type)
    await state.set_state(HealthStates.wait_goal_data)
    
    goal_names = {"lose": "Похудение", "maintain": "Поддержание веса", "gain": "Набор массы"}
    goal_name = goal_names.get(goal_type, "Поддержание веса")
    
    await callback.message.answer(
        f"🎯 Цель: <b>{goal_name}</b>\n\n"
        "📝 <b>Введи свои данные</b>\n\n"
        "Напиши в одну строку через пробел:\n\n"
        "<code>ВЕС РОСТ ВОЗРАСТ ПОЛ АКТИВНОСТЬ</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 <b>Пример:</b> <code>75 175 30 м средняя</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔹 <b>ВЕС</b> — твой вес в кг (например: 75)\n"
        "🔹 <b>РОСТ</b> — твой рост в см (например: 175)\n"
        "🔹 <b>ВОЗРАСТ</b> — полных лет (например: 30)\n"
        "🔹 <b>ПОЛ</b> — <code>м</code> или <code>ж</code>\n"
        "🔹 <b>АКТИВНОСТЬ</b>:\n"
        "    • <code>низкая</code> — сидячая работа, мало спорта\n"
        "    • <code>средняя</code> — тренировки 2-3 раза в неделю\n"
        "    • <code>высокая</code> — тренировки каждый день\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "✏️ Пиши свои данные 👇",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(HealthStates.wait_goal_data, F.text)
async def process_goal_data(msg: Message, state: FSMContext):
    """Обработка данных для расчёта цели"""
    try:
        data = await state.get_data()
        goal_type = data.get("goal_type")
        
        # Парсинг: "75 175 30 м средняя"
        parts = msg.text.split()
        if len(parts) < 5:
            await msg.answer(
                "❌ Неверный формат!\n\n"
                "Напиши: <b>Вес Рост Возраст Пол Активность</b>\n"
                "Пример: 75 175 30 м средняя",
                parse_mode="HTML"
            )
            return
        
        weight = float(parts[0])
        height = int(parts[1])
        age = int(parts[2])
        gender = parts[3].lower()
        activity = parts[4].lower()
        
        # Базовый метаболизм
        bmr = calculate_bmr(weight, height, age, gender)
        
        # Общий расход энергии
        tdee = calculate_tdee(bmr, activity)
        
        # Корректировка по цели
        if goal_type == "lose":
            daily_cal = tdee - 500  # Дефицит 500 ккал
        elif goal_type == "gain":
            daily_cal = tdee + 300  # Профицит 300 ккал
        else:
            daily_cal = tdee
        
        # Рассчитываем БЖУ
        macros = calculate_macros(daily_cal, weight, goal_type)
        
        # Сохраняем
        await db.save_nutrition_goal(
            user_id=msg.from_user.id,
            goal=goal_type,
            daily_calories=daily_cal,
            daily_protein=macros['protein'],
            daily_fat=macros['fat'],
            daily_carbs=macros['carbs'],
            weight=weight,
            height=height,
            age=age,
            gender=gender,
            activity=activity
        )
        
        goal_names = {"lose": "🔻 Похудеть", "maintain": "⚖️ Поддержать вес", "gain": "🔺 Набрать массу"}
        goal_name = goal_names.get(goal_type, "⚖️ Поддержать вес")
        
        await msg.answer(
            f"✅ <b>Цель установлена!</b>\n\n"
            f"🎯 Цель: {goal_name}\n\n"
            f"📊 <b>Твоя дневная норма:</b>\n"
            f"🔥 Калории: {daily_cal:,} ккал\n"
            f"🥩 Белки: {macros['protein']}г\n"
            f"🧈 Жиры: {macros['fat']}г\n"
            f"🍞 Углеводы: {macros['carbs']}г\n\n"
            f"Теперь раздел Питание будет давать персональные советы!",
            parse_mode="HTML",
            reply_markup=reply.health_kb(msg.from_user.id)
        )
        await state.set_state(HealthStates.menu)
        
    except Exception as e:
        await msg.answer(
            f"❌ Ошибка обработки данных:\n<code>{str(e)}</code>\n\n"
            "Попробуй ещё раз в формате:\n"
            "<b>Вес Рост Возраст Пол Активность</b>",
            parse_mode="HTML"
        )


@router.message(HealthStates.nutrition_menu, F.text == "💡 Советы")
async def nutrition_tips(msg: Message, state: FSMContext):
    """Советы по питанию на основе анализа"""
    processing = await msg.answer("🔍 Анализирую твоё питание...")
    
    try:
        # Получаем статистику за неделю
        week_stats = await db.get_weekly_calories(msg.from_user.id)
        goal = await db.get_nutrition_goal(msg.from_user.id)
        
        if not week_stats:
            await processing.edit_text("📭 Недостаточно данных для анализа. Начни вести журнал!")
            return
        
        # Формируем данные для анализа
        stats_text = ""
        for day in week_stats:
            date_str = day['date'] if isinstance(day['date'], str) else day['date'].strftime('%d.%m')
            stats_text += f"• {date_str}: {day['calories']} ккал (Б:{day['protein']}г Ж:{day['fat']}г У:{day['carbs']}г)\n"
        
        goal_text = "не установлена"
        if goal:
            goal_names = {"lose": "похудение", "maintain": "поддержание веса", "gain": "набор массы"}
            goal_text = f"{goal_names.get(goal['goal'], 'поддержание')} ({goal['daily_calories']} ккал/день)"
        
        prompt = f"""
Проанализируй питание пользователя за неделю и дай советы.

Цель: {goal_text}

Статистика за 7 дней:
{stats_text}

Найди:
1. Проблемы в питании (переедание, недоедание, дисбаланс БЖУ)
2. Что хорошо
3. Конкретные рекомендации

Формат:
📊 <b>Анализ питания за 7 дней</b>

❌ <b>Проблемы:</b>
• ...

✅ <b>Хорошо:</b>
• ...

💡 <b>Рекомендации:</b>
1. ...
2. ...
3. ...
"""
        
        messages = [{"role": "user", "content": prompt}]
        response, tokens_used = await ask(messages, "anthropic/claude-sonnet-4.5", max_tokens=1500)
        
        # Списываем токены с маржой 2.5x
        await db.use_tokens_smart(msg.from_user.id, tokens_used, bot_name='health')
        await db.increment_requests(msg.from_user.id)
        
        await processing.delete()
        await msg.answer(md_to_html(response), parse_mode="HTML")
        
    except Exception as e:
        await processing.edit_text(f"❌ Ошибка:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")


# ========== НАВИГАЦИЯ ==========

# Назад при ожидании фото → меню калорий
@router.message(HealthStates.wait_photo, F.text == "◀️ Назад")
async def back_from_photo(msg: Message, state: FSMContext):
    """Назад из ожидания фото в меню калорий"""
    await state.set_state(HealthStates.calories_menu)
    await msg.answer(
        "🍽 <b>Подсчёт калорий</b>\n\n"
        "📸 <b>По фото</b> — сфоткай еду, я определю калории\n"
        "✏️ <b>Вручную</b> — напиши что съел\n\n"
        "Выбери способ:",
        parse_mode="HTML",
        reply_markup=reply.calories_menu_kb()
    )


# Назад при вводе вручную → меню калорий
@router.message(HealthStates.wait_manual_input, F.text == "◀️ Назад")
async def back_from_manual(msg: Message, state: FSMContext):
    """Назад из ручного ввода в меню калорий"""
    await state.set_state(HealthStates.calories_menu)
    await msg.answer(
        "🍽 <b>Подсчёт калорий</b>\n\n"
        "📸 <b>По фото</b> — сфоткай еду, я определю калории\n"
        "✏️ <b>Вручную</b> — напиши что съел\n\n"
        "Выбери способ:",
        parse_mode="HTML",
        reply_markup=reply.calories_menu_kb()
    )


# Назад из подменю калорий → меню Здоровье
@router.message(HealthStates.calories_menu, F.text == "◀️ Назад")
async def back_to_health_from_calories(msg: Message, state: FSMContext):
    """Назад из меню калорий в главное меню Здоровье"""
    await state.set_state(HealthStates.menu)
    
    today_stats = await db.get_today_calories(msg.from_user.id)
    goal = await db.get_nutrition_goal(msg.from_user.id)
    
    text = "🍎 <b>Здоровье</b>\n\n"
    text += "Следи за питанием и достигай целей!\n\n"
    
    if today_stats['calories'] > 0:
        text += "📊 <b>Сегодня:</b>\n"
        text += format_calories_summary(today_stats, goal)
    else:
        text += "<i>Сегодня ещё нет записей</i>"
    
    await msg.answer(text, parse_mode="HTML", reply_markup=reply.health_kb(msg.from_user.id))


# Назад из журнала → меню Здоровье
@router.message(HealthStates.journal_menu, F.text == "◀️ Назад")
async def back_to_health_from_journal(msg: Message, state: FSMContext):
    """Назад из журнала в главное меню Здоровье"""
    await state.set_state(HealthStates.menu)
    
    today_stats = await db.get_today_calories(msg.from_user.id)
    goal = await db.get_nutrition_goal(msg.from_user.id)
    
    text = "🍎 <b>Здоровье</b>\n\n"
    text += "Следи за питанием и достигай целей!\n\n"
    
    if today_stats['calories'] > 0:
        text += "📊 <b>Сегодня:</b>\n"
        text += format_calories_summary(today_stats, goal)
    else:
        text += "<i>Сегодня ещё нет записей</i>"
    
    await msg.answer(text, parse_mode="HTML", reply_markup=reply.health_kb(msg.from_user.id))


# Назад из питания → меню Здоровье
@router.message(HealthStates.nutrition_menu, F.text == "◀️ Назад")
async def back_to_health_from_nutrition(msg: Message, state: FSMContext):
    """Назад из питания в главное меню Здоровье"""
    await state.set_state(HealthStates.menu)
    
    today_stats = await db.get_today_calories(msg.from_user.id)
    goal = await db.get_nutrition_goal(msg.from_user.id)
    
    text = "🍎 <b>Здоровье</b>\n\n"
    text += "Следи за питанием и достигай целей!\n\n"
    
    if today_stats['calories'] > 0:
        text += "📊 <b>Сегодня:</b>\n"
        text += format_calories_summary(today_stats, goal)
    else:
        text += "<i>Сегодня ещё нет записей</i>"
    
    await msg.answer(text, parse_mode="HTML", reply_markup=reply.health_kb(msg.from_user.id))


# Назад из меню Здоровье → Soul меню
@router.message(HealthStates.menu, F.text == "◀️ Назад")
async def back_to_soul_menu(msg: Message, state: FSMContext):
    """Назад из главного меню Здоровье в меню Soul AI"""
    await state.clear()
    from keyboards.reply import bots_menu_kb
    await msg.answer("🫧 Soul AI", reply_markup=bots_menu_kb())

