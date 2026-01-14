"""
Хендлеры для раздела Режим дня
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date

from database import db
from keyboards import reply, inline

router = Router()

# Дефолтные рутины
DEFAULT_MORNING = ["💧 Выпить воду", "🧘 Зарядка 10 мин", "🚿 Душ", "🍳 Завтрак", "📝 План на день"]
DEFAULT_EVENING = ["📱 Отложить телефон", "📖 Чтение 15 мин", "🧘 Растяжка", "📝 Записать 3 благодарности", "😴 Лечь до 23:00"]


class RoutineStates(StatesGroup):
    """Состояния для режима дня"""
    menu = State()
    morning_checklist = State()
    evening_reflection = State()
    enter_reflection = State()
    setup_routine = State()
    enter_custom_items = State()


# ═══════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════

@router.message(F.text == "🌅 Режим дня")
async def routine_menu(msg: Message, state: FSMContext):
    """Главное меню режима дня"""
    await state.set_state(RoutineStates.menu)
    
    try:
        today_morning = await db.get_today_routine_checkin(msg.from_user.id, "morning")
        today_evening = await db.get_today_routine_checkin(msg.from_user.id, "evening")
        
        morning_status = f"✅ {today_morning['completion_percent']}%" if today_morning else "⬜ Не выполнено"
        evening_status = f"✅ Заполнено" if today_evening else "⬜ Не заполнено"
        
        await msg.answer(
            f"🌅 <b>Режим дня</b>\n\n"
            f"<b>Сегодня:</b>\n"
            f"☀️ Утро: {morning_status}\n"
            f"🌙 Вечер: {evening_status}\n\n"
            f"Рутина — ключ к продуктивности!",
            parse_mode="HTML",
            reply_markup=reply.routine_menu_kb()
        )
        
    except Exception as e:
        print(f"[ERROR] Error in routine_menu: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# УТРЕННИЙ ЧЕКЛИСТ
# ═══════════════════════════════════════

@router.message(RoutineStates.menu, F.text == "☀️ Утренний чеклист")
async def morning_checklist(msg: Message, state: FSMContext):
    """Утренний чеклист"""
    try:
        # Получаем рутину пользователя или дефолтную
        routine = await db.get_user_routine(msg.from_user.id, "morning")
        items = routine['items'] if routine else DEFAULT_MORNING
        
        # Проверяем есть ли уже сегодняшний чекин
        today = await db.get_today_routine_checkin(msg.from_user.id, "morning")
        checked = today['completed_items'] if today else []
        
        await state.update_data(morning_items=items, morning_checked=checked)
        await state.set_state(RoutineStates.morning_checklist)
        
        await msg.answer(
            f"☀️ <b>Утренний чеклист</b>\n\n"
            f"Отмечай выполненное:",
            parse_mode="HTML",
            reply_markup=inline.checklist_kb(items, checked, "morning")
        )
        
    except Exception as e:
        print(f"[ERROR] Error in morning_checklist: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


@router.callback_query(F.data.startswith("check_morning_"))
async def check_morning_item(callback: CallbackQuery, state: FSMContext):
    """Переключить пункт утреннего чеклиста"""
    try:
        index = int(callback.data.replace("check_morning_", ""))
        data = await state.get_data()
        
        items = data.get("morning_items", DEFAULT_MORNING)
        checked = data.get("morning_checked", [])
        
        item = items[index]
        if item in checked:
            checked.remove(item)
        else:
            checked.append(item)
        
        await state.update_data(morning_checked=checked)
        
        # Обновляем сообщение
        await callback.message.edit_reply_markup(
            reply_markup=inline.checklist_kb(items, checked, "morning")
        )
        await callback.answer()
        
    except Exception as e:
        print(f"[ERROR] Error in check_morning_item: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(F.data == "save_morning")
async def save_morning(callback: CallbackQuery, state: FSMContext):
    """Сохранить утренний чеклист"""
    try:
        data = await state.get_data()
        
        items = data.get("morning_items", DEFAULT_MORNING)
        checked = data.get("morning_checked", [])
        percent = int(len(checked) / len(items) * 100) if items else 0
        
        # Сохраняем
        await db.save_routine_checkin(
            user_id=callback.from_user.id,
            routine_type="morning",
            completed_items=checked,
            total_items=len(items),
            completion_percent=percent
        )
        
        # Мотивация
        if percent == 100:
            text = "🎉 <b>Идеальное утро!</b>\n\nТы выполнил все пункты! Отличный старт дня! 🚀"
        elif percent >= 70:
            text = f"👍 <b>Хорошее утро!</b>\n\nВыполнено {percent}% рутины. Так держать!"
        else:
            text = f"☀️ <b>Утро сохранено</b>\n\nВыполнено {percent}%. Завтра будет лучше!"
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer("Сохранено!")
        await state.set_state(RoutineStates.menu)
        
    except Exception as e:
        print(f"[ERROR] Error in save_morning: {e}")
        import traceback
        traceback.print_exc()
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


# ═══════════════════════════════════════
# ВЕЧЕРНЯЯ РЕФЛЕКСИЯ
# ═══════════════════════════════════════

@router.message(RoutineStates.menu, F.text == "🌙 Вечерняя рефлексия")
async def evening_reflection(msg: Message, state: FSMContext):
    """Вечерняя рефлексия"""
    try:
        # Сначала чеклист
        routine = await db.get_user_routine(msg.from_user.id, "evening")
        items = routine['items'] if routine else DEFAULT_EVENING
        
        today = await db.get_today_routine_checkin(msg.from_user.id, "evening")
        checked = today['completed_items'] if today else []
        
        await state.update_data(evening_items=items, evening_checked=checked)
        await state.set_state(RoutineStates.evening_reflection)
        
        await msg.answer(
            f"🌙 <b>Вечерний чеклист</b>\n\n"
            f"Отмечай выполненное:",
            parse_mode="HTML",
            reply_markup=inline.checklist_kb(items, checked, "evening")
        )
        
    except Exception as e:
        print(f"[ERROR] Error in evening_reflection: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


@router.callback_query(F.data.startswith("check_evening_"))
async def check_evening_item(callback: CallbackQuery, state: FSMContext):
    """Переключить пункт вечернего чеклиста"""
    try:
        index = int(callback.data.replace("check_evening_", ""))
        data = await state.get_data()
        
        items = data.get("evening_items", DEFAULT_EVENING)
        checked = data.get("evening_checked", [])
        
        item = items[index]
        if item in checked:
            checked.remove(item)
        else:
            checked.append(item)
        
        await state.update_data(evening_checked=checked)
        
        await callback.message.edit_reply_markup(
            reply_markup=inline.checklist_kb(items, checked, "evening")
        )
        await callback.answer()
        
    except Exception as e:
        print(f"[ERROR] Error in check_evening_item: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(F.data == "save_evening")
async def save_evening(callback: CallbackQuery, state: FSMContext):
    """Сохранить вечерний чеклист и перейти к рефлексии"""
    try:
        await state.set_state(RoutineStates.enter_reflection)
        
        await callback.message.answer(
            "🌙 <b>Рефлексия</b>\n\n"
            "Как прошёл твой день?\n"
            "Напиши пару предложений:\n\n"
            "<i>Что получилось хорошо?\n"
            "Что можно улучшить?\n"
            "За что благодарен?</i>",
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        print(f"[ERROR] Error in save_evening: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.message(RoutineStates.enter_reflection, F.text)
async def reflection_entered(msg: Message, state: FSMContext):
    """Обработка рефлексии"""
    try:
        if msg.text.startswith("◀️"):
            await state.set_state(RoutineStates.menu)
            await msg.answer("🌅 Режим дня", reply_markup=reply.routine_menu_kb())
            return
        
        await state.update_data(reflection=msg.text)
        
        await msg.answer(
            "Оцени своё настроение сегодня:",
            reply_markup=inline.mood_kb()
        )
        
    except Exception as e:
        print(f"[ERROR] Error in reflection_entered: {e}")
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


@router.callback_query(F.data.startswith("mood_"))
async def mood_selected(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора настроения"""
    try:
        mood = int(callback.data.replace("mood_", ""))
        data = await state.get_data()
        
        items = data.get("evening_items", DEFAULT_EVENING)
        checked = data.get("evening_checked", [])
        reflection = data.get("reflection", "")
        percent = int(len(checked) / len(items) * 100) if items else 0
        
        # Сохраняем
        await db.save_routine_checkin(
            user_id=callback.from_user.id,
            routine_type="evening",
            completed_items=checked,
            total_items=len(items),
            completion_percent=percent,
            reflection=reflection,
            mood=mood
        )
        
        mood_emoji = ["", "😫", "😕", "😐", "🙂", "😄"][mood]
        
        await callback.message.edit_text(
            f"🌙 <b>День завершён!</b>\n\n"
            f"📊 Вечерняя рутина: {percent}%\n"
            f"💭 Настроение: {mood_emoji}\n\n"
            f"Спокойной ночи! 😴",
            parse_mode="HTML"
        )
        await state.set_state(RoutineStates.menu)
        await callback.answer("Сохранено!")
        
    except Exception as e:
        print(f"[ERROR] Error in mood_selected: {e}")
        import traceback
        traceback.print_exc()
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


# ═══════════════════════════════════════
# НАСТРОЙКА РУТИНЫ
# ═══════════════════════════════════════

@router.message(RoutineStates.menu, F.text == "⚙️ Настроить рутину")
async def setup_routine(msg: Message, state: FSMContext):
    """Настройка рутины"""
    await msg.answer(
        "⚙️ <b>Настройка рутины</b>\n\n"
        "Выбери что настроить:",
        parse_mode="HTML",
        reply_markup=inline.setup_routine_kb()
    )


@router.callback_query(F.data.startswith("setup_"))
async def setup_routine_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа рутины для настройки"""
    try:
        routine_type = callback.data.replace("setup_", "")  # morning/evening
        await state.update_data(setup_type=routine_type)
        await state.set_state(RoutineStates.enter_custom_items)
        
        type_name = "утренней" if routine_type == "morning" else "вечерней"
        default = DEFAULT_MORNING if routine_type == "morning" else DEFAULT_EVENING
        
        await callback.message.answer(
            f"✏️ <b>Настройка {type_name} рутины</b>\n\n"
            f"Напиши свои пункты, каждый с новой строки:\n\n"
            f"<i>Пример:\n"
            + "\n".join(default[:3]) + "</i>\n\n"
            f"Или напиши <code>дефолт</code> для стандартной рутины",
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        print(f"[ERROR] Error in setup_routine_type: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.message(RoutineStates.enter_custom_items, F.text)
async def custom_items_entered(msg: Message, state: FSMContext):
    """Обработка кастомных пунктов рутины"""
    try:
        data = await state.get_data()
        routine_type = data.get("setup_type")
        
        if msg.text.lower() == "дефолт":
            items = DEFAULT_MORNING if routine_type == "morning" else DEFAULT_EVENING
        else:
            items = [line.strip() for line in msg.text.split("\n") if line.strip()]
        
        # Сохраняем рутину
        await db.save_user_routine(msg.from_user.id, routine_type, items)
        
        type_name = "Утренняя" if routine_type == "morning" else "Вечерняя"
        
        await msg.answer(
            f"✅ <b>{type_name} рутина сохранена!</b>\n\n"
            f"Пункты:\n" + "\n".join(f"• {item}" for item in items),
            parse_mode="HTML",
            reply_markup=reply.routine_menu_kb()
        )
        await state.set_state(RoutineStates.menu)
        
    except Exception as e:
        print(f"[ERROR] Error in custom_items_entered: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# СТАТИСТИКА ПРОДУКТИВНОСТИ
# ═══════════════════════════════════════

@router.message(RoutineStates.menu, F.text == "📊 Продуктивность")
async def productivity_stats(msg: Message):
    """Статистика продуктивности за 7 дней"""
    try:
        # Статистика за 7 дней
        stats = await db.get_routine_stats(msg.from_user.id, days=7)
        
        text = "📊 <b>Продуктивность за 7 дней</b>\n\n"
        
        text += "<b>☀️ Утренняя рутина:</b>\n"
        for day in stats['morning']:
            bar = "█" * (day['percent'] // 20) + "░" * (5 - day['percent'] // 20)
            emoji = "✅" if day['percent'] >= 70 else "⬜" if day['percent'] > 0 else "❌"
            text += f"{emoji} {day['date']}: {bar} {day['percent']}%\n"
        
        text += f"\n<b>🌙 Вечерняя рефлексия:</b>\n"
        for day in stats['evening']:
            mood_emoji = ["❌", "😫", "😕", "😐", "🙂", "😄"][day.get('mood', 0)]
            emoji = "✅" if day['percent'] > 0 else "❌"
            text += f"{emoji} {day['date']}: {mood_emoji}\n"
        
        text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
        text += f"📈 Средняя продуктивность: {stats['avg_percent']}%\n"
        text += f"😊 Среднее настроение: {stats['avg_mood']:.1f}/5"
        
        await msg.answer(text, parse_mode="HTML")
        
    except Exception as e:
        print(f"[ERROR] Error in productivity_stats: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# КНОПКА НАЗАД
# ═══════════════════════════════════════

@router.message(RoutineStates.menu, F.text == "◀️ Назад")
async def back_from_routine(msg: Message, state: FSMContext):
    """Вернуться в меню Лайфстайл"""
    await state.clear()
    await msg.answer("🏃 <b>Лайфстайл</b>", parse_mode="HTML", reply_markup=reply.lifestyle_kb(msg.from_user.id))


@router.message(RoutineStates.morning_checklist, F.text == "◀️ Назад")
async def back_from_morning(msg: Message, state: FSMContext):
    """Назад из утреннего чеклиста"""
    await state.set_state(RoutineStates.menu)
    await msg.answer("🌅 <b>Режим дня</b>", parse_mode="HTML", reply_markup=reply.routine_menu_kb())


@router.message(RoutineStates.evening_reflection, F.text == "◀️ Назад")
async def back_from_evening(msg: Message, state: FSMContext):
    """Назад из вечерней рефлексии"""
    await state.set_state(RoutineStates.menu)
    await msg.answer("🌅 <b>Режим дня</b>", parse_mode="HTML", reply_markup=reply.routine_menu_kb())
