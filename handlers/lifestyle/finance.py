"""
Хендлеры для раздела Финансы
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date, timedelta
import re

from database import db  # Использует PostgreSQL через database/__init__.py
from database.postgres_db import EXPENSE_CATEGORIES
from keyboards import reply, inline
from utils.openrouter import ask
from utils.markdown import md_to_html
from utils.status_manager import show_status

router = Router()


class FinanceStates(StatesGroup):
    """Состояния для финансов"""
    menu = State()
    enter_amount = State()
    enter_description = State()
    select_category = State()
    enter_budget = State()


# ═══════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════

@router.message(F.text == "💰 Финансы")
async def finance_menu(msg: Message, state: FSMContext):
    """Главное меню финансов"""
    await state.set_state(FinanceStates.menu)
    
    try:
        # Статистика за месяц
        month_stats = await db.get_month_expenses(msg.from_user.id)
        budget = await db.get_user_budget(msg.from_user.id)
        
        budget_text = ""
        if budget:
            remaining = budget['monthly_limit'] - month_stats['total']
            percent = int(month_stats['total'] / budget['monthly_limit'] * 100) if budget['monthly_limit'] > 0 else 0
            emoji = "✅" if percent < 80 else "⚠️" if percent < 100 else "🔴"
            budget_text = f"\n{emoji} Бюджет: {month_stats['total']:,.0f} / {budget['monthly_limit']:,.0f} ₽ ({percent}%)"
        
        await msg.answer(
            f"💰 <b>Финансы</b>\n\n"
            f"📊 <b>Этот месяц:</b>\n"
            f"💸 Расходы: {month_stats['total']:,.0f} ₽"
            f"{budget_text}\n\n"
            f"Записывай траты — я покажу куда уходят деньги!",
            parse_mode="HTML",
            reply_markup=reply.finance_menu_kb()
        )
        
    except Exception as e:
        print(f"[ERROR] Error in finance_menu: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# ЗАПИСАТЬ ТРАТУ
# ═══════════════════════════════════════

@router.message(FinanceStates.menu, F.text == "➕ Записать трату")
async def add_expense_start(msg: Message, state: FSMContext):
    """Начать добавление траты"""
    await state.set_state(FinanceStates.enter_amount)
    
    await msg.answer(
        "➕ <b>Новая трата</b>\n\n"
        "Напиши сумму и на что потратил:\n\n"
        "<i>Примеры:</i>\n"
        "• <code>500 кофе</code>\n"
        "• <code>1500 такси до работы</code>\n"
        "• <code>3000 продукты в магазине</code>\n\n"
        "✏️ Пиши 👇",
        parse_mode="HTML"
    )


@router.message(FinanceStates.enter_amount, F.text)
async def expense_entered(msg: Message, state: FSMContext):
    """Обработка введенной траты"""
    try:
        if msg.text.startswith("◀️"):
            await state.set_state(FinanceStates.menu)
            await msg.answer("💰 Финансы", reply_markup=reply.finance_menu_kb())
            return
        
        # Парсим сумму и описание
        match = re.match(r'^(\d+(?:[.,]\d+)?)\s*(.*)$', msg.text.strip())
        
        if not match:
            await msg.answer(
                "❌ Не понял сумму.\n\n"
                "Напиши так: <code>500 кофе</code>",
                parse_mode="HTML"
            )
            return
        
        amount = float(match.group(1).replace(',', '.'))
        description = match.group(2).strip() or "Без описания"
        
        await state.update_data(amount=amount, description=description)
        
        # Определяем категорию
        category = detect_category(description)
        await state.update_data(auto_category=category)
        
        category_name = EXPENSE_CATEGORIES.get(category, "📦 Другое")
        
        await msg.answer(
            f"💸 <b>Трата:</b> {amount:,.0f} ₽\n"
            f"📝 <b>Описание:</b> {description}\n"
            f"📁 <b>Категория:</b> {category_name}\n\n"
            f"Категория верная?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"✅ Да, {category_name}", callback_data="confirm_category")],
                [InlineKeyboardButton(text="📁 Изменить категорию", callback_data="change_category")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_expense")]
            ])
        )
        
    except Exception as e:
        print(f"[ERROR] Error in expense_entered: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


def detect_category(description: str) -> str:
    """Определить категорию по описанию"""
    description_lower = description.lower()
    
    if any(word in description_lower for word in ['кофе', 'обед', 'ужин', 'еда', 'продукты', 'магазин', 'ресторан', 'кафе', 'пицца', 'бургер', 'завтрак']):
        return "food"
    elif any(word in description_lower for word in ['такси', 'метро', 'автобус', 'бензин', 'парковка', 'uber', 'яндекс']):
        return "transport"
    elif any(word in description_lower for word in ['кино', 'концерт', 'бар', 'клуб', 'игра', 'netflix', 'spotify', 'развлечение']):
        return "entertainment"
    elif any(word in description_lower for word in ['одежда', 'обувь', 'zara', 'hm', 'магазин', 'покупка']):
        return "shopping"
    elif any(word in description_lower for word in ['аптека', 'врач', 'клиника', 'лекарства', 'анализы']):
        return "health"
    elif any(word in description_lower for word in ['квартира', 'жкх', 'свет', 'вода', 'интернет', 'аренда', 'коммунал']):
        return "bills"
    elif any(word in description_lower for word in ['курс', 'книга', 'обучение', 'урок']):
        return "education"
    else:
        return "other"


@router.callback_query(F.data == "confirm_category")
async def confirm_category(callback: CallbackQuery, state: FSMContext):
    """Подтвердить категорию"""
    await save_expense(callback, state)


@router.callback_query(F.data == "change_category")
async def change_category(callback: CallbackQuery, state: FSMContext):
    """Изменить категорию"""
    await callback.message.edit_text(
        "📁 Выбери категорию:",
        reply_markup=inline.category_kb()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_"))
async def category_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрана категория"""
    try:
        category = callback.data.replace("cat_", "")
        await state.update_data(auto_category=category)
        await save_expense(callback, state)
        
    except Exception as e:
        print(f"[ERROR] Error in category_selected: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


async def save_expense(callback: CallbackQuery, state: FSMContext):
    """Сохранить трату"""
    try:
        data = await state.get_data()
        
        # Сохраняем транзакцию
        await db.save_transaction(
            user_id=callback.from_user.id,
            trans_type="expense",
            amount=data['amount'],
            category=data['auto_category'],
            description=data['description']
        )
        
        # Проверяем бюджет
        budget = await db.get_user_budget(callback.from_user.id)
        month_total = await db.get_month_total(callback.from_user.id)
        
        warning = ""
        if budget:
            if month_total > budget['monthly_limit']:
                warning = "\n\n🔴 <b>Внимание!</b> Бюджет превышен!"
            elif month_total > budget['monthly_limit'] * 0.9:
                warning = "\n\n⚠️ Осталось меньше 10% бюджета!"
        
        category_name = EXPENSE_CATEGORIES.get(data['auto_category'], "📦 Другое")
        
        await callback.message.edit_text(
            f"✅ <b>Записано!</b>\n\n"
            f"💸 {data['amount']:,.0f} ₽ — {data['description']}\n"
            f"📁 {category_name}\n\n"
            f"📊 Всего за месяц: {month_total:,.0f} ₽"
            f"{warning}",
            parse_mode="HTML"
        )
        await state.set_state(FinanceStates.menu)
        await callback.answer("Сохранено!")
        
    except Exception as e:
        print(f"[ERROR] Error in save_expense: {e}")
        import traceback
        traceback.print_exc()
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


@router.callback_query(F.data == "cancel_expense")
async def cancel_expense(callback: CallbackQuery, state: FSMContext):
    """Отменить трату"""
    await callback.message.edit_text("❌ Отменено")
    await state.set_state(FinanceStates.menu)
    await callback.answer()


# ═══════════════════════════════════════
# МОИ РАСХОДЫ
# ═══════════════════════════════════════

@router.message(FinanceStates.menu, F.text == "📊 Мои расходы")
async def my_expenses(msg: Message, state: FSMContext):
    """Показать расходы"""
    await msg.answer(
        "📊 <b>Мои расходы</b>\n\n"
        "За какой период показать?",
        parse_mode="HTML",
        reply_markup=inline.expenses_period_kb()
    )


@router.callback_query(F.data.startswith("exp_"))
async def show_expenses(callback: CallbackQuery, state: FSMContext):
    """Показать расходы за период"""
    try:
        period = callback.data.replace("exp_", "")
        
        if period == "today":
            start_date = date.today()
            period_name = "Сегодня"
        elif period == "week":
            start_date = date.today() - timedelta(days=7)
            period_name = "За неделю"
        else:  # month
            start_date = date.today().replace(day=1)
            period_name = "За месяц"
        
        expenses = await db.get_expenses_by_period(callback.from_user.id, start_date)
        
        if not expenses:
            await callback.message.edit_text(
                f"📊 <b>{period_name}</b>\n\n"
                f"Нет записей за этот период",
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        # Группируем по категориям
        by_category = {}
        total = 0
        
        for exp in expenses:
            cat = exp['category']
            if cat not in by_category:
                by_category[cat] = 0
            by_category[cat] += exp['amount']
            total += exp['amount']
        
        text = f"📊 <b>{period_name}</b>\n\n"
        
        # Сортируем по сумме
        sorted_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
        
        for cat, amount in sorted_cats:
            cat_name = EXPENSE_CATEGORIES.get(cat, "📦 Другое")
            percent = int(amount / total * 100) if total > 0 else 0
            bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
            text += f"{cat_name}\n{bar} {amount:,.0f} ₽ ({percent}%)\n\n"
        
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💰 <b>Итого:</b> {total:,.0f} ₽"
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        print(f"[ERROR] Error in show_expenses: {e}")
        import traceback
        traceback.print_exc()
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}")


# ═══════════════════════════════════════
# БЮДЖЕТ
# ═══════════════════════════════════════

@router.message(FinanceStates.menu, F.text == "🎯 Бюджет")
async def budget_menu(msg: Message, state: FSMContext):
    """Меню бюджета"""
    try:
        budget = await db.get_user_budget(msg.from_user.id)
        
        if budget:
            month_total = await db.get_month_total(msg.from_user.id)
            remaining = budget['monthly_limit'] - month_total
            percent = int(month_total / budget['monthly_limit'] * 100) if budget['monthly_limit'] > 0 else 0
            
            # Дни до конца месяца
            today = date.today()
            next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
            days_left = (next_month - today).days
            daily_budget = remaining / days_left if days_left > 0 and remaining > 0 else 0
            
            await msg.answer(
                f"🎯 <b>Бюджет на месяц</b>\n\n"
                f"💰 Лимит: {budget['monthly_limit']:,.0f} ₽\n"
                f"💸 Потрачено: {month_total:,.0f} ₽ ({percent}%)\n"
                f"💵 Осталось: {remaining:,.0f} ₽\n\n"
                f"📅 Дней до конца месяца: {days_left}\n"
                f"📊 Можно тратить: {daily_budget:,.0f} ₽/день",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✏️ Изменить бюджет", callback_data="edit_budget")],
                ])
            )
        else:
            await msg.answer(
                f"🎯 <b>Бюджет не установлен</b>\n\n"
                f"Установи месячный лимит расходов,\n"
                f"чтобы контролировать траты!",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Установить бюджет", callback_data="edit_budget")],
                ])
            )
            
    except Exception as e:
        print(f"[ERROR] Error in budget_menu: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


@router.callback_query(F.data == "edit_budget")
async def edit_budget(callback: CallbackQuery, state: FSMContext):
    """Изменить бюджет"""
    await state.set_state(FinanceStates.enter_budget)
    
    await callback.message.answer(
        "💰 <b>Установка бюджета</b>\n\n"
        "Напиши сумму, которую планируешь\n"
        "тратить в месяц:\n\n"
        "<i>Пример: <code>50000</code></i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(FinanceStates.enter_budget, F.text)
async def budget_entered(msg: Message, state: FSMContext):
    """Обработка введенного бюджета"""
    try:
        amount = float(msg.text.replace(' ', '').replace(',', '.'))
        
        await db.save_user_budget(msg.from_user.id, amount)
        
        await msg.answer(
            f"✅ <b>Бюджет установлен!</b>\n\n"
            f"💰 Лимит на месяц: {amount:,.0f} ₽\n\n"
            f"Я буду предупреждать когда приблизишься к лимиту!",
            parse_mode="HTML",
            reply_markup=reply.finance_menu_kb()
        )
        await state.set_state(FinanceStates.menu)
        
    except ValueError:
        await msg.answer("❌ Введи число, например: 50000")
    except Exception as e:
        print(f"[ERROR] Error in budget_entered: {e}")
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# СОВЕТЫ ПО ЭКОНОМИИ (AI)
# ═══════════════════════════════════════

@router.message(FinanceStates.menu, F.text == "💡 Советы")
async def finance_tips(msg: Message, state: FSMContext):
    """Советы по экономии"""
    status = None
    try:
        status = await show_status(msg.bot, msg.chat.id, "text")
        
        # Получаем статистику
        month_stats = await db.get_month_expenses_detailed(msg.from_user.id)
        budget = await db.get_user_budget(msg.from_user.id)
        
        budget_text = f"{budget['monthly_limit']:,.0f} ₽" if budget else "не установлен"
        
        stats_text = "\n".join([f"- {cat}: {data['total']:,.0f} ₽ ({data['count']} раз)" for cat, data in month_stats.items()])
        
        prompt = f"""
Проанализируй расходы пользователя за месяц и дай советы по экономии.

Расходы по категориям:
{stats_text if stats_text else "Нет данных"}

Бюджет: {budget_text}

Дай 3-5 конкретных советов:
1. Где можно сэкономить
2. Какие категории раздуты
3. Практические лайфхаки

Формат ответа:
💡 **Советы по экономии**

📊 **Анализ:**
[краткий анализ расходов]

💰 **Где сэкономить:**
1. ...
2. ...
3. ...

🎯 **Цель на следующий месяц:**
[конкретная цель]
"""
        
        messages = [{"role": "user", "content": prompt}]
        response, tokens_used = await ask(messages, "anthropic/claude-sonnet-4.5", max_tokens=1000)
        
        # Списываем токены с маржой 2.5x
        await db.use_tokens_smart(msg.from_user.id, tokens_used, bot_name='finance')
        await db.increment_requests(msg.from_user.id)
        
        await msg.answer(md_to_html(response), parse_mode="HTML")
        
    except Exception as e:
        print(f"[ERROR] Error in finance_tips: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")
    finally:
        if status:
            await status.stop()


# ═══════════════════════════════════════
# АНАЛИТИКА
# ═══════════════════════════════════════

@router.message(FinanceStates.menu, F.text == "📈 Аналитика")
async def analytics(msg: Message, state: FSMContext):
    """Аналитика расходов"""
    try:
        # Сравнение с прошлым месяцем
        current_month = await db.get_month_total(msg.from_user.id)
        last_month = await db.get_last_month_total(msg.from_user.id)
        
        if last_month > 0:
            change = ((current_month - last_month) / last_month) * 100
            change_text = f"📈 +{change:.0f}%" if change > 0 else f"📉 {change:.0f}%"
        else:
            change_text = "📊 Нет данных за прошлый месяц"
        
        # Топ категорий
        top_categories = await db.get_top_categories(msg.from_user.id)
        
        # Средний чек
        avg_expense = await db.get_average_expense(msg.from_user.id)
        
        # Самая большая трата
        max_expense = await db.get_max_expense(msg.from_user.id)
        
        text = f"📈 <b>Аналитика</b>\n\n"
        
        text += f"<b>Сравнение с прошлым месяцем:</b>\n"
        text += f"Сейчас: {current_month:,.0f} ₽\n"
        text += f"Прошлый: {last_month:,.0f} ₽\n"
        text += f"{change_text}\n\n"
        
        text += f"<b>Топ-3 категории:</b>\n"
        for i, (cat, amount) in enumerate(top_categories[:3], 1):
            cat_name = EXPENSE_CATEGORIES.get(cat, "📦 Другое")
            text += f"{i}. {cat_name}: {amount:,.0f} ₽\n"
        
        text += f"\n<b>Средний чек:</b> {avg_expense:,.0f} ₽\n"
        
        if max_expense:
            text += f"<b>Макс. трата:</b> {max_expense['amount']:,.0f} ₽ ({max_expense['description']})"
        
        await msg.answer(text, parse_mode="HTML")
        
    except Exception as e:
        print(f"[ERROR] Error in analytics: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:200]}")


# ═══════════════════════════════════════
# КНОПКА НАЗАД
# ═══════════════════════════════════════

@router.message(FinanceStates.menu, F.text == "◀️ Назад")
async def back_from_finance(msg: Message, state: FSMContext):
    """Вернуться в меню Лайфстайл"""
    await state.clear()
    await msg.answer("🏆 <b>Лайфстайл</b>", parse_mode="HTML", reply_markup=reply.lifestyle_kb(msg.from_user.id))
