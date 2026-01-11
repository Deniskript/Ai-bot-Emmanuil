"""
Хендлеры для раздела Ментальное здоровье
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import random

from database import db
from keyboards import reply, inline
from utils.openrouter import ask
from utils.markdown import md_to_html

router = Router()

# Теги настроения
MOOD_TAGS = ["😴 Сон", "💼 Работа", "🏃 Спорт", "👥 Общение", "🍔 Еда", "📱 Соцсети", "😰 Стресс"]


class MentalStates(StatesGroup):
    """Состояния для ментального здоровья"""
    menu = State()
    meditation_type = State()
    meditation_duration = State()
    mood_score = State()
    mood_energy = State()
    mood_tags = State()


# ═══════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════

@router.message(F.text == "🧘 Ментальное")
async def mental_menu(msg: Message, state: FSMContext):
    """Главное меню ментального здоровья"""
    await state.set_state(MentalStates.menu)
    
    try:
        today_mood = await db.get_today_mood(msg.from_user.id)
        meditation_streak = await db.get_meditation_streak(msg.from_user.id)
        
        mood_text = f"😊 Сегодня: {'😫😕😐🙂😄'[today_mood['mood']-1]}" if today_mood else "😊 Сегодня: не отмечено"
        
        await msg.answer(
            f"🧘 <b>Ментальное здоровье</b>\n\n"
            f"{mood_text}\n"
            f"🔥 Медитации подряд: {meditation_streak} дней\n\n"
            f"Забота о себе — это важно! 💜",
            parse_mode="HTML",
            reply_markup=reply.mental_menu_kb()
        )
        
    except Exception as e:
        print(f"[ERROR] Error in mental_menu: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# МЕДИТАЦИЯ
# ═══════════════════════════════════════

@router.message(MentalStates.menu, F.text == "🧘‍♀️ Медитация")
async def meditation_start(msg: Message, state: FSMContext):
    """Начать медитацию"""
    await state.set_state(MentalStates.meditation_type)
    
    await msg.answer(
        "🧘‍♀️ <b>Медитация</b>\n\n"
        "Выбери тип медитации:",
        parse_mode="HTML",
        reply_markup=inline.meditation_type_kb()
    )


@router.callback_query(F.data.startswith("type_"))
async def meditation_type_selected(callback: CallbackQuery, state: FSMContext):
    """Выбор типа медитации"""
    try:
        med_type = callback.data.replace("type_", "")
        await state.update_data(med_type=med_type)
        await state.set_state(MentalStates.meditation_duration)
        
        await callback.message.edit_text(
            "⏱ Сколько минут?",
            reply_markup=inline.meditation_duration_kb()
        )
        await callback.answer()
        
    except Exception as e:
        print(f"[ERROR] Error in meditation_type_selected: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(F.data.startswith("med_"))
async def meditation_duration_selected(callback: CallbackQuery, state: FSMContext):
    """Выбор длительности медитации"""
    try:
        duration = int(callback.data.replace("med_", ""))
        data = await state.get_data()
        med_type = data.get("med_type", "calm")
        
        await state.update_data(duration=duration)
        
        # Генерируем медитацию через AI
        processing = await callback.message.edit_text("🧘 Создаю медитацию для тебя...")
        
        type_prompts = {
            "calm": "Создай успокаивающую медитацию для снятия стресса",
            "focus": "Создай медитацию для концентрации и фокуса",
            "sleep": "Создай расслабляющую медитацию для подготовки ко сну"
        }
        
        prompt = f"""
{type_prompts[med_type]} на {duration} минут.

Формат:
- Начни с приветствия
- Пошаговые инструкции для дыхания
- Визуализация
- Плавное завершение

Пиши мягко, спокойно. Используй эмодзи для настроения.
Разбей на абзацы для удобства чтения.
"""
        
        messages = [{"role": "user", "content": prompt}]
        response, _ = await ask(messages, "anthropic/claude-sonnet-4.5", max_tokens=1000)
        
        # Сохраняем медитацию
        await db.save_meditation_log(callback.from_user.id, duration, med_type)
        
        await processing.edit_text(
            f"🧘‍♀️ <b>Медитация {duration} мин</b>\n\n"
            f"{md_to_html(response)}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Медитация записана! +1 к streak 🔥",
            parse_mode="HTML"
        )
        await state.set_state(MentalStates.menu)
        
    except Exception as e:
        print(f"[ERROR] Error in meditation_duration_selected: {e}")
        import traceback
        traceback.print_exc()
        await callback.message.edit_text(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# ДНЕВНИК НАСТРОЕНИЯ
# ═══════════════════════════════════════

@router.message(MentalStates.menu, F.text == "😊 Настроение")
async def mood_start(msg: Message, state: FSMContext):
    """Начать отметку настроения"""
    await state.set_state(MentalStates.mood_score)
    
    await msg.answer(
        "😊 <b>Как ты себя чувствуешь?</b>\n\n"
        "Оцени своё настроение:",
        parse_mode="HTML",
        reply_markup=inline.mood_scale_kb()
    )


@router.callback_query(MentalStates.mood_score, F.data.startswith("mood_m_"))
async def mood_selected(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора настроения"""
    try:
        mood = int(callback.data.replace("mood_m_", ""))
        await state.update_data(mood=mood)
        await state.set_state(MentalStates.mood_energy)
        
        await callback.message.edit_text(
            "⚡ <b>Уровень энергии?</b>",
            parse_mode="HTML",
            reply_markup=inline.energy_scale_kb()
        )
        await callback.answer()
        
    except Exception as e:
        print(f"[ERROR] Error in mood_selected: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(MentalStates.mood_energy, F.data.startswith("energy_"))
async def energy_selected(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора энергии"""
    try:
        energy = int(callback.data.replace("energy_", ""))
        await state.update_data(energy=energy, tags=[])
        await state.set_state(MentalStates.mood_tags)
        
        await callback.message.edit_text(
            "🏷 <b>Что повлияло на настроение?</b>\n\n"
            "Выбери теги (можно несколько):",
            parse_mode="HTML",
            reply_markup=inline.mood_tags_kb()
        )
        await callback.answer()
        
    except Exception as e:
        print(f"[ERROR] Error in energy_selected: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(MentalStates.mood_tags, F.data.startswith("mtag_"))
async def tag_toggled(callback: CallbackQuery, state: FSMContext):
    """Переключение тега"""
    try:
        tag_index = int(callback.data.replace("mtag_", ""))
        tag = MOOD_TAGS[tag_index]
        
        data = await state.get_data()
        selected = data.get("tags", [])
        
        if tag in selected:
            selected.remove(tag)
        else:
            selected.append(tag)
        
        await state.update_data(tags=selected)
        
        await callback.message.edit_reply_markup(
            reply_markup=inline.mood_tags_kb(selected)
        )
        await callback.answer()
        
    except Exception as e:
        print(f"[ERROR] Error in tag_toggled: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(F.data == "save_mood")
async def save_mood(callback: CallbackQuery, state: FSMContext):
    """Сохранить настроение"""
    try:
        data = await state.get_data()
        
        mood = data.get("mood", 3)
        energy = data.get("energy", 3)
        tags = data.get("tags", [])
        
        # Сохраняем
        await db.save_mood_log(callback.from_user.id, mood, energy, tags)
        
        mood_emoji = "😫😕😐🙂😄"[mood - 1]
        energy_emoji = "🔋" * energy
        
        # AI совет на основе настроения
        if mood <= 2:
            tip = await get_mood_tip(mood, tags)
        else:
            tip = "Отличный настрой! Так держать! 💪"
        
        await callback.message.edit_text(
            f"✅ <b>Настроение записано!</b>\n\n"
            f"😊 Настроение: {mood_emoji}\n"
            f"⚡ Энергия: {energy_emoji}\n"
            f"🏷 Теги: {', '.join(tags) if tags else '-'}\n\n"
            f"💡 {tip}",
            parse_mode="HTML"
        )
        await state.set_state(MentalStates.menu)
        await callback.answer("Сохранено!")
        
    except Exception as e:
        print(f"[ERROR] Error in save_mood: {e}")
        import traceback
        traceback.print_exc()
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


async def get_mood_tip(mood: int, tags: list) -> str:
    """AI совет при плохом настроении"""
    try:
        prompt = f"""
Пользователь отметил плохое настроение ({mood}/5).
Факторы: {', '.join(tags) if tags else 'не указаны'}

Дай короткий (1-2 предложения) тёплый совет или поддержку.
Без банальностей. Конкретно и с эмпатией.
"""
        
        messages = [{"role": "user", "content": prompt}]
        response, _ = await ask(messages, "anthropic/claude-sonnet-4.5", max_tokens=200)
        return response.strip()
    except Exception as e:
        print(f"[ERROR] Error in get_mood_tip: {e}")
        return "Это пройдёт. Ты не один 💜"


# ═══════════════════════════════════════
# УБРАТЬ ТРЕВОГУ
# ═══════════════════════════════════════

@router.message(MentalStates.menu, F.text == "💆 Убрать тревогу")
async def anxiety_help(msg: Message, state: FSMContext):
    """Помощь при тревоге"""
    try:
        processing = await msg.answer("💆 Готовлю технику для тебя...")
        
        techniques = [
            ("5-4-3-2-1", "grounding"),
            ("Дыхание 4-7-8", "breathing"),
            ("Сканирование тела", "bodyscan"),
            ("Техника бабочки", "butterfly")
        ]
        
        name, technique = random.choice(techniques)
        
        prompts = {
            "grounding": """
Опиши технику заземления 5-4-3-2-1:
- 5 вещей которые видишь
- 4 которые можешь потрогать
- 3 звука
- 2 запаха
- 1 вкус

Пошагово, мягко, с примерами.
""",
            "breathing": """
Опиши дыхательную технику 4-7-8:
- Вдох 4 секунды
- Задержка 7 секунд
- Выдох 8 секунд

Пошагово, с визуализацией.
""",
            "bodyscan": """
Опиши технику сканирования тела для расслабления:
- От макушки до пяток
- Замечать напряжение
- Отпускать его

Мягко, пошагово.
""",
            "butterfly": """
Опиши технику бабочки (butterfly hug):
- Скрестить руки на груди
- Поочерёдно похлопывать
- Глубокое дыхание

Простые шаги, с поддержкой.
"""
        }
        
        messages = [{"role": "user", "content": prompts[technique]}]
        response, _ = await ask(messages, "anthropic/claude-sonnet-4.5", max_tokens=800)
        
        await processing.edit_text(
            f"💆 <b>{name}</b>\n\n"
            f"{md_to_html(response)}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💜 Ты справишься. Это пройдёт.",
            parse_mode="HTML"
        )
        
    except Exception as e:
        print(f"[ERROR] Error in anxiety_help: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# АФФИРМАЦИЯ ДНЯ
# ═══════════════════════════════════════

@router.message(MentalStates.menu, F.text == "✨ Аффирмация")
async def daily_affirmation(msg: Message, state: FSMContext):
    """Аффирмация дня"""
    try:
        processing = await msg.answer("✨ Генерирую аффирмацию...")
        
        prompt = """
Сгенерируй одну мощную аффирмацию на сегодня.

Требования:
- От первого лица ("Я...")
- Позитивная, в настоящем времени
- Конкретная, не абстрактная
- Вдохновляющая

Формат:
✨ [аффирмация]

💫 [короткое пояснение почему это важно]
"""
        
        messages = [{"role": "user", "content": prompt}]
        response, _ = await ask(messages, "anthropic/claude-sonnet-4.5", max_tokens=300)
        
        await processing.edit_text(
            f"<b>Аффирмация дня</b>\n\n"
            f"{md_to_html(response)}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔁 Повтори 3 раза вслух!",
            parse_mode="HTML"
        )
        
    except Exception as e:
        print(f"[ERROR] Error in daily_affirmation: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# ГРАФИК НАСТРОЕНИЯ
# ═══════════════════════════════════════

@router.message(MentalStates.menu, F.text == "📊 График настроения")
async def mood_chart(msg: Message, state: FSMContext):
    """График настроения за 14 дней"""
    try:
        # Статистика за 14 дней
        stats = await db.get_mood_stats(msg.from_user.id, days=14)
        
        if not stats['logs']:
            await msg.answer(
                "📊 <b>Нет данных</b>\n\n"
                "Начни отмечать настроение каждый день!",
                parse_mode="HTML"
            )
            return
        
        text = "📊 <b>Настроение за 14 дней</b>\n\n"
        
        # Текстовый график
        emojis = "😫😕😐🙂😄"
        for log in stats['logs']:
            mood_bar = "▓" * log['mood'] + "░" * (5 - log['mood'])
            text += f"{log['date']}: {emojis[log['mood']-1]} {mood_bar}\n"
        
        text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
        text += f"📈 Среднее настроение: {stats['avg_mood']:.1f}/5\n"
        text += f"⚡ Средняя энергия: {stats['avg_energy']:.1f}/5\n"
        
        # Самый частый тег
        if stats['top_tag']:
            text += f"🏷 Частый фактор: {stats['top_tag']}"
        
        await msg.answer(text, parse_mode="HTML")
        
    except Exception as e:
        print(f"[ERROR] Error in mood_chart: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# КНОПКА НАЗАД
# ═══════════════════════════════════════

@router.message(MentalStates.menu, F.text == "◀️ Назад")
async def back_from_mental(msg: Message, state: FSMContext):
    """Вернуться в меню Лайфстайл"""
    await state.clear()
    await msg.answer("🏃 <b>Лайфстайл</b>", parse_mode="HTML", reply_markup=reply.lifestyle_kb(msg.from_user.id))
