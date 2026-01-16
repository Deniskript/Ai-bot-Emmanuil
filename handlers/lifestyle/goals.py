"""
Хендлеры для раздела Трекер целей
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date, timedelta
import random
import re

from database import db  # Использует PostgreSQL через database/__init__.py
from keyboards import reply, inline

router = Router()


class GoalStates(StatesGroup):
    """Состояния для трекера целей"""
    menu = State()
    enter_title = State()
    enter_frequency = State()
    enter_custom_frequency = State()
    enter_reminder = State()


# ═══════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════

@router.message(F.text == "🎯 Трекер целей")
async def goals_menu(msg: Message, state: FSMContext):
    """Главное меню трекера целей"""
    await state.set_state(GoalStates.menu)
    
    active_goals = await db.get_active_goals(msg.from_user.id)
    streak = await db.get_total_streak(msg.from_user.id)
    
    await msg.answer(
        f"🎯 <b>Трекер целей</b>\n\n"
        f"📋 Активных целей: {len(active_goals)}\n"
        f"🔥 Общий streak: {streak} дней\n\n"
        f"Ставь цели — я буду напоминать и мотивировать!",
        parse_mode="HTML",
        reply_markup=reply.goals_menu_kb()
    )


# ═══════════════════════════════════════
# НОВАЯ ЦЕЛЬ
# ═══════════════════════════════════════

@router.message(GoalStates.menu, F.text == "➕ Новая цель")
async def new_goal_start(msg: Message, state: FSMContext):
    """Начать создание новой цели"""
    await state.set_state(GoalStates.enter_title)
    
    await msg.answer(
        "➕ <b>Новая цель</b>\n\n"
        "Напиши свою цель одним предложением:\n\n"
        "<i>Примеры:</i>\n"
        "• Бегать по утрам\n"
        "• Читать 30 минут\n"
        "• Пить 2 литра воды\n"
        "• Учить 10 английских слов\n"
        "• Медитировать\n\n"
        "✏️ Пиши цель 👇",
        parse_mode="HTML"
    )


@router.message(GoalStates.enter_title, F.text)
async def goal_title_entered(msg: Message, state: FSMContext):
    """Обработка названия цели"""
    if msg.text.startswith("◀️"):
        await state.set_state(GoalStates.menu)
        await msg.answer("🎯 Трекер целей", reply_markup=reply.goals_menu_kb())
        return
    
    await state.update_data(goal_title=msg.text)
    await state.set_state(GoalStates.enter_frequency)
    
    await msg.answer(
        f"✅ Цель: <b>{msg.text}</b>\n\n"
        f"Как часто выполнять?",
        parse_mode="HTML",
        reply_markup=inline.goal_frequency_kb()
    )


@router.callback_query(F.data == "freq_daily")
async def freq_daily(callback: CallbackQuery, state: FSMContext):
    """Частота: каждый день"""
    await state.update_data(frequency="daily", target_count=1, period_days=1)
    await ask_reminder(callback, state)


@router.callback_query(F.data == "freq_weekly")
async def freq_weekly(callback: CallbackQuery, state: FSMContext):
    """Частота: раз в неделю"""
    await state.update_data(frequency="weekly", target_count=1, period_days=7)
    await ask_reminder(callback, state)


@router.callback_query(F.data == "freq_custom")
async def freq_custom(callback: CallbackQuery, state: FSMContext):
    """Частота: своя"""
    await state.set_state(GoalStates.enter_custom_frequency)
    await callback.message.answer(
        "🔢 <b>Своя частота</b>\n\n"
        "Напиши в формате:\n"
        "<code>X раз за Y дней</code>\n\n"
        "Примеры:\n"
        "• <code>3 раз за 7 дней</code> — 3 раза в неделю\n"
        "• <code>5 раз за 7 дней</code> — 5 раз в неделю\n"
        "• <code>2 раз за 1 дней</code> — 2 раза в день",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(GoalStates.enter_custom_frequency, F.text)
async def custom_frequency_entered(msg: Message, state: FSMContext):
    """Обработка кастомной частоты"""
    match = re.search(r'(\d+)\s*раз.*?(\d+)\s*дн', msg.text.lower())
    
    if match:
        target = int(match.group(1))
        period = int(match.group(2))
        await state.update_data(frequency="custom", target_count=target, period_days=period)
        await ask_reminder_msg(msg, state)
    else:
        await msg.answer("❌ Не понял. Напиши например: 3 раз за 7 дней")


async def ask_reminder(callback: CallbackQuery, state: FSMContext):
    """Запросить время напоминания (через callback)"""
    await state.set_state(GoalStates.enter_reminder)
    await callback.message.answer(
        "⏰ <b>Напоминание</b>\n\n"
        "Во сколько напоминать о цели?\n\n"
        "Напиши время (например: <code>09:00</code>)\n"
        "Или напиши <code>нет</code> без напоминаний",
        parse_mode="HTML"
    )
    await callback.answer()


async def ask_reminder_msg(msg: Message, state: FSMContext):
    """Запросить время напоминания (через сообщение)"""
    await state.set_state(GoalStates.enter_reminder)
    await msg.answer(
        "⏰ <b>Напоминание</b>\n\n"
        "Во сколько напоминать?\n"
        "Напиши время: <code>09:00</code>\n"
        "Или <code>нет</code>",
        parse_mode="HTML"
    )


@router.message(GoalStates.enter_reminder, F.text)
async def reminder_entered(msg: Message, state: FSMContext):
    """Обработка времени напоминания и создание цели"""
    try:
        data = await state.get_data()
        
        reminder_time = None if msg.text.lower() == "нет" else msg.text.strip()
        
        # Создаём цель
        goal_id = await db.create_goal(
            user_id=msg.from_user.id,
            title=data["goal_title"],
            frequency=data["frequency"],
            target_count=data["target_count"],
            period_days=data["period_days"],
            reminder_time=reminder_time
        )
        
        # Создаём streak
        await db.create_streak(msg.from_user.id, goal_id)
        
        freq_text = {
            "daily": "каждый день",
            "weekly": "раз в неделю",
            "custom": f"{data['target_count']} раз за {data['period_days']} дней"
        }
        
        reminder_text = f"⏰ Напоминание: {reminder_time}" if reminder_time else "⏰ Без напоминаний"
        
        await msg.answer(
            f"🎉 <b>Цель создана!</b>\n\n"
            f"🎯 {data['goal_title']}\n"
            f"📅 {freq_text[data['frequency']]}\n"
            f"{reminder_text}\n\n"
            f"Удачи! Я буду следить за прогрессом 💪",
            parse_mode="HTML",
            reply_markup=reply.goals_menu_kb()
        )
        await state.set_state(GoalStates.menu)
        
    except Exception as e:
        print(f"[ERROR] Error creating goal: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка при создании цели: {str(e)[:200]}")


# ═══════════════════════════════════════
# МОИ ЦЕЛИ
# ═══════════════════════════════════════

@router.message(GoalStates.menu, F.text == "📋 Мои цели")
async def my_goals(msg: Message, state: FSMContext):
    """Показать список целей"""
    try:
        goals = await db.get_active_goals(msg.from_user.id)
        
        if not goals:
            await msg.answer(
                "📋 <b>У тебя пока нет целей</b>\n\n"
                "Нажми ➕ Новая цель чтобы начать!",
                parse_mode="HTML"
            )
            return
        
        for goal in goals:
            streak = await db.get_goal_streak(goal['id'], msg.from_user.id)
            progress = await db.get_goal_progress(goal['id'], goal['target_count'], goal['period_days'])
            
            await msg.answer(
                f"🎯 <b>{goal['title']}</b>\n\n"
                f"📊 Прогресс: {progress['done']}/{goal['target_count']} за период\n"
                f"🔥 Streak: {streak['current_streak']} дней\n"
                f"🏆 Лучший: {streak['best_streak']} дней",
                parse_mode="HTML",
                reply_markup=inline.goal_actions_kb(goal['id'])
            )
            
    except Exception as e:
        print(f"[ERROR] Error in my_goals: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# ОТМЕТКА ВЫПОЛНЕНИЯ
# ═══════════════════════════════════════

@router.callback_query(F.data.startswith("checkin_"))
async def checkin_goal(callback: CallbackQuery):
    """Начать отметку выполнения"""
    try:
        goal_id = int(callback.data.replace("checkin_", ""))
        goal = await db.get_goal_by_id(goal_id)
        
        if not goal:
            await callback.answer("❌ Цель не найдена")
            return
        
        await callback.message.answer(
            f"🎯 <b>{goal['title']}</b>\n\n"
            f"Выполнил сегодня?",
            parse_mode="HTML",
            reply_markup=inline.goal_confirm_kb(goal_id)
        )
        await callback.answer()
        
    except Exception as e:
        print(f"[ERROR] Error in checkin_goal: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(F.data.startswith("goal_done_"))
async def goal_done(callback: CallbackQuery):
    """Отметка: выполнено"""
    try:
        goal_id = int(callback.data.replace("goal_done_", ""))
        user_id = callback.from_user.id
        
        # Проверяем не отмечал ли уже сегодня
        existing = await db.get_checkin_today(goal_id, user_id)
        if existing:
            await callback.answer("Уже отмечено сегодня!", show_alert=True)
            return
        
        # Сохраняем отметку
        await db.save_checkin(goal_id, user_id, is_done=True)
        
        # Обновляем streak
        streak = await db.get_goal_streak(goal_id, user_id)
        
        # Логика streak
        last_checkin = streak.get('last_checkin')
        if last_checkin:
            if isinstance(last_checkin, str):
                last_checkin = date.fromisoformat(last_checkin)
            
            yesterday = date.today() - timedelta(days=1)
            
            if last_checkin == yesterday:
                # Продолжаем streak
                current_streak = streak['current_streak'] + 1
            elif last_checkin == date.today():
                # Уже отмечено сегодня
                current_streak = streak['current_streak']
            else:
                # Прервался streak
                current_streak = 1
        else:
            # Первая отметка
            current_streak = 1
        
        best_streak = max(current_streak, streak['best_streak'])
        
        # Сохраняем новый streak
        await db.update_streak(goal_id, user_id, current_streak, best_streak)
        
        # Мотивационное сообщение
        messages = [
            "🔥 Отлично! Так держать!",
            "💪 Молодец! Ещё один день в копилку!",
            "⭐ Супер! Ты на верном пути!",
            "🚀 Красавчик! Продолжай в том же духе!"
        ]
        
        motivation = random.choice(messages)
        
        await callback.message.edit_text(
            f"✅ <b>Выполнено!</b>\n\n"
            f"🔥 Streak: {current_streak} дней\n"
            f"🏆 Лучший: {best_streak} дней\n\n"
            f"{motivation}",
            parse_mode="HTML"
        )
        await callback.answer("✅ Записано!")
        
    except Exception as e:
        print(f"[ERROR] Error in goal_done: {e}")
        import traceback
        traceback.print_exc()
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(F.data.startswith("goal_skip_"))
async def goal_skip(callback: CallbackQuery):
    """Отметка: пропущено"""
    try:
        goal_id = int(callback.data.replace("goal_skip_", ""))
        user_id = callback.from_user.id
        
        # Сохраняем пропуск
        await db.save_checkin(goal_id, user_id, is_done=False)
        
        # Сбрасываем streak
        streak = await db.get_goal_streak(goal_id, user_id)
        await db.update_streak(goal_id, user_id, 0, streak['best_streak'])
        
        await callback.message.edit_text(
            f"😔 <b>Пропущено</b>\n\n"
            f"Ничего страшного! Завтра новый день.\n"
            f"Главное — не сдаваться! 💪",
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        print(f"[ERROR] Error in goal_skip: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(F.data.startswith("delete_goal_"))
async def delete_goal_handler(callback: CallbackQuery):
    """Удаление цели"""
    try:
        goal_id = int(callback.data.replace("delete_goal_", ""))
        
        await db.delete_goal(goal_id)
        
        await callback.message.edit_text(
            f"🗑 <b>Цель удалена</b>\n\n"
            f"Можешь создать новую в любой момент!",
            parse_mode="HTML"
        )
        await callback.answer("Удалено!")
        
    except Exception as e:
        print(f"[ERROR] Error in delete_goal: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(F.data.startswith("progress_"))
async def show_progress(callback: CallbackQuery):
    """Показать прогресс цели"""
    try:
        goal_id = int(callback.data.replace("progress_", ""))
        goal = await db.get_goal_by_id(goal_id)
        
        if not goal:
            await callback.answer("❌ Цель не найдена")
            return
        
        progress = await db.get_goal_progress(goal_id, goal['target_count'], goal['period_days'])
        streak = await db.get_goal_streak(goal_id, callback.from_user.id)
        
        # Генерируем прогресс-бар
        bar_length = 10
        filled = int(progress['percent'] / 10)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        await callback.message.answer(
            f"📊 <b>Прогресс: {goal['title']}</b>\n\n"
            f"{bar} {progress['percent']}%\n\n"
            f"✅ Выполнено: {progress['done']}/{goal['target_count']}\n"
            f"🔥 Текущий streak: {streak['current_streak']} дней\n"
            f"🏆 Лучший streak: {streak['best_streak']} дней",
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        print(f"[ERROR] Error in show_progress: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


# ═══════════════════════════════════════
# STREAK
# ═══════════════════════════════════════

@router.message(GoalStates.menu, F.text == "🔥 Мой streak")
async def my_streak(msg: Message):
    """Показать streak'и"""
    try:
        goals = await db.get_active_goals(msg.from_user.id)
        
        if not goals:
            await msg.answer("📋 Сначала создай цель!")
            return
        
        text = "🔥 <b>Твои streak'и</b>\n\n"
        
        total_current = 0
        total_best = 0
        
        for goal in goals:
            streak = await db.get_goal_streak(goal['id'], msg.from_user.id)
            fire = "🔥" * min(streak['current_streak'] // 7, 5)  # Огоньки за каждую неделю
            
            text += f"🎯 {goal['title']}\n"
            text += f"   Сейчас: {streak['current_streak']} дней {fire}\n"
            text += f"   Рекорд: {streak['best_streak']} дней\n\n"
            
            total_current += streak['current_streak']
            total_best += streak['best_streak']
        
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"📊 <b>Всего:</b> {total_current} дней streak\n"
        text += f"🏆 <b>Сумма рекордов:</b> {total_best} дней"
        
        await msg.answer(text, parse_mode="HTML")
        
    except Exception as e:
        print(f"[ERROR] Error in my_streak: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# СТАТИСТИКА
# ═══════════════════════════════════════

@router.message(GoalStates.menu, F.text == "📊 Статистика")
async def goals_stats(msg: Message):
    """Показать статистику за 30 дней"""
    try:
        goals = await db.get_active_goals(msg.from_user.id)
        
        if not goals:
            await msg.answer("📋 Сначала создай цель!")
            return
        
        # Статистика за 30 дней
        stats = await db.get_monthly_stats(msg.from_user.id)
        
        text = "📊 <b>Статистика за 30 дней</b>\n\n"
        
        text += f"✅ Выполнено: {stats['done']} раз\n"
        text += f"❌ Пропущено: {stats['skipped']} раз\n"
        text += f"📈 Процент выполнения: {stats['percent']}%\n\n"
        
        # График по неделям (текстовый)
        text += "<b>По неделям:</b>\n"
        for week in stats['weeks']:
            bar = "█" * (week['percent'] // 10) + "░" * (10 - week['percent'] // 10)
            text += f"{week['label']}: {bar} {week['percent']}%\n"
        
        await msg.answer(text, parse_mode="HTML")
        
    except Exception as e:
        print(f"[ERROR] Error in goals_stats: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# КНОПКА НАЗАД
# ═══════════════════════════════════════

@router.message(GoalStates.menu, F.text == "◀️ Назад")
async def back_from_goals(msg: Message, state: FSMContext):
    """Вернуться в меню Лайфстайл"""
    await state.clear()
    await msg.answer("🏃 <b>Лайфстайл</b>", parse_mode="HTML", reply_markup=reply.lifestyle_kb(msg.from_user.id))


@router.message(GoalStates.enter_title, F.text == "◀️ Назад")
async def back_from_title(msg: Message, state: FSMContext):
    """Назад из ввода названия"""
    await state.set_state(GoalStates.menu)
    await msg.answer("🎯 <b>Трекер целей</b>", parse_mode="HTML", reply_markup=reply.goals_menu_kb())
