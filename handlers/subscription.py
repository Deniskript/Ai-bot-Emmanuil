from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from database import postgres_db as db
from keyboards import inline
from utils.robokassa import generate_payment_link
from config import SUBSCRIPTIONS, STAR_PACKAGES


router = Router()


def fmt(n): 
    return f"{n:,}".replace(",", " ")


def format_date(date_str):
    if not date_str:
        return "Бессрочно"
    return date_str[:10]


def get_plans_text():
    return """<b>Доступные тарифы:</b>

⭐ <b>Мини</b> — 490 ₽/мес

✨ Психолог нового поколения
✨ Память и эмоции — помнит ваши разговоры
✨ Мотивация, поддержка, решение задач
✨ Голосовые сообщения и фото
✨ 4 000 ⭐ (~70 диалогов)

❌ Нет доступа к Обучению

<i>Первый ИИ, который слышит и понимает</i>

👑 <b>Стандарт</b> — 990 ₽/мес

<b>Всё из Мини, плюс:</b>

🧠 Claude Opus 4 — самая умная модель
🎓 Все курсы в твоём телефоне
📚 Разбивает материал на шаги как лучший репетитор
❓ Задаёт вопросы, разбирает сложные темы
📝 Конспекты для глубокого усвоения
✨ 9 000 ⭐ (~158 диалогов)

<i>Полный доступ к обучению без границ</i>"""


# === МЕНЮ ПОДПИСКИ ===
@router.message(F.text == "💠 Подписка")
async def subscription_menu(msg: Message):
    stars = await db.get_available_stars(msg.from_user.id)
    has_sub = await db.has_active_subscription(msg.from_user.id)
    
    if has_sub:
        sub = await db.get_subscription(msg.from_user.id)
        sub_info = SUBSCRIPTIONS.get(sub['type'], {})
        sub_name = sub_info.get('name', sub['type'])
        stars_limit = sub['stars_limit']
        
        text = f"""⭐ <b>Ваша подписка</b>

⭐ Тариф: <b>{sub_name}</b>
📅 Действует до: <b>{format_date(sub['expires_at'])}</b>

⭐ Звёзд: <b>{fmt(stars)}</b> из {fmt(stars_limit)}
💬 Примерно сообщений: ~{stars // 37}

Выберите действие:"""
        
        await msg.answer(text, reply_markup=inline.subscription_active_kb())
    elif stars > 0:
        # Есть бонусные звёзды, но нет подписки
        text = f"""⭐ <b>Подписка</b>

🎁 У вас <b>{fmt(stars)}</b> бонусных звёзд
💬 Примерно сообщений: ~{stars // 37}

{get_plans_text()}

Выберите тариф:"""
        
        await msg.answer(text, reply_markup=inline.subscription_plans_kb())
    else:
        # Нет звёзд и нет подписки
        text = f"""⭐ <b>Подписка</b>

⚠️ У вас закончились звёзды

{get_plans_text()}

Выберите тариф:"""
        
        await msg.answer(text, reply_markup=inline.subscription_plans_kb())


# === ВЫБОР ТАРИФА ===
@router.callback_query(F.data.startswith("sub:buy:"))
async def buy_subscription(cb: CallbackQuery):
    sub_type = cb.data.split(":")[2]
    
    if sub_type not in SUBSCRIPTIONS:
        await cb.answer("❌ Неизвестный тариф", show_alert=True)
        return
    
    plan = SUBSCRIPTIONS[sub_type]
    
    tx_id = await db.create_transaction(
        uid=cb.from_user.id,
        amount=plan['price'],
        stars=plan['stars'],
        tx_type=f"subscription:{sub_type}"
    )
    
    payment_url = generate_payment_link(
        order_id=tx_id,
        amount=plan['price'],
        description=f"Подписка {plan['name']} - Душа AI",
        user_id=cb.from_user.id,
        payment_type=f"subscription:{sub_type}"
    )
    
    text = f"""💳 <b>Оплата подписки</b>

⭐ Тариф: <b>{plan['name']}</b>
💰 Сумма: <b>{plan['price']} ₽</b>
⭐ Звёзд: <b>{fmt(plan['stars'])}</b>

Нажмите кнопку для оплаты:"""
    
    await cb.message.edit_text(text, reply_markup=inline.payment_kb(payment_url, tx_id))
    await cb.answer()


# === ДОКУПКА ЗВЁЗД ===
@router.callback_query(F.data == "sub:stars")
async def stars_menu(cb: CallbackQuery):
    has_sub = await db.has_active_subscription(cb.from_user.id)
    
    if not has_sub:
        await cb.answer("⚠️ Докупка доступна только подписчикам", show_alert=True)
        text = """⚠️ <b>Докупка звёзд</b>

Докупка звёзд доступна только для пользователей с активной подпиской.

👉 Оформите подписку, чтобы получить доступ."""
        await cb.message.edit_text(text, reply_markup=inline.back_to_sub_kb())
        return
    
    stars = await db.get_available_stars(cb.from_user.id)
    
    text = f"""⭐ <b>Докупка звёзд</b>

⭐ Текущий баланс: <b>{fmt(stars)}</b>

<b>Пакеты:</b>

📦 1,000 ⭐ — <b>149 ₽</b>
📦 2,000 ⭐ — <b>249 ₽</b>

Выберите пакет:"""
    
    await cb.message.edit_text(text, reply_markup=inline.stars_packages_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("stars:buy:"))
async def buy_stars(cb: CallbackQuery):
    package_id = cb.data.split(":")[2]
    
    has_sub = await db.has_active_subscription(cb.from_user.id)
    if not has_sub:
        await cb.answer("⚠️ Докупка доступна только подписчикам", show_alert=True)
        return
    
    if package_id not in STAR_PACKAGES:
        await cb.answer("❌ Неизвестный пакет", show_alert=True)
        return
    
    package = STAR_PACKAGES[package_id]
    
    tx_id = await db.create_transaction(
        uid=cb.from_user.id,
        amount=package['price'],
        stars=package['stars'],
        tx_type=f"stars:{package_id}"
    )
    
    payment_url = generate_payment_link(
        order_id=tx_id,
        amount=package['price'],
        description=f"Докупка {package['name']} - Душа AI",
        user_id=cb.from_user.id,
        payment_type=f"stars:{package_id}"
    )
    
    text = f"""💳 <b>Оплата звёзд</b>

📦 Пакет: <b>{package['name']}</b>
💰 Сумма: <b>{package['price']} ₽</b>

Нажмите кнопку для оплаты:"""
    
    await cb.message.edit_text(text, reply_markup=inline.payment_kb(payment_url, tx_id))
    await cb.answer()


# === ПРОВЕРКА ОПЛАТЫ ===
@router.callback_query(F.data.startswith("pay:check:"))
async def check_payment(cb: CallbackQuery):
    tx_id = int(cb.data.split(":")[2])
    
    tx = await db.get_transaction(tx_id)
    if not tx:
        await cb.answer("❌ Транзакция не найдена", show_alert=True)
        return
    
    if tx['status'] == 'completed':
        await cb.answer("✅ Оплата уже подтверждена!", show_alert=True)
        await cb.message.edit_text(
            "✅ <b>Оплата подтверждена!</b>\n\nЗвёзды зачислены на ваш баланс.",
            reply_markup=inline.back_to_sub_kb()
        )
    else:
        await cb.answer("⏳ Оплата ещё не поступила. Подождите немного.", show_alert=True)


# === НАВИГАЦИЯ ===
@router.callback_query(F.data == "sub:back")
async def back_to_subscription(cb: CallbackQuery):
    await cb.answer()
    stars = await db.get_available_stars(cb.from_user.id)
    has_sub = await db.has_active_subscription(cb.from_user.id)
    
    if has_sub:
        sub = await db.get_subscription(cb.from_user.id)
        sub_info = SUBSCRIPTIONS.get(sub['type'], {})
        sub_name = sub_info.get('name', sub['type'])
        stars_limit = sub['stars_limit']
        
        text = f"""⭐ <b>Ваша подписка</b>

⭐ Тариф: <b>{sub_name}</b>
📅 Действует до: <b>{format_date(sub['expires_at'])}</b>

⭐ Звёзд: <b>{fmt(stars)}</b> из {fmt(stars_limit)}

Выберите действие:"""
        
        await cb.message.edit_text(text, reply_markup=inline.subscription_active_kb())
    else:
        text = f"""⭐ <b>Подписка</b>

{"🎁 Бонусных звёзд: " + fmt(stars) if stars > 0 else "⚠️ Звёзды закончились"}

{get_plans_text()}

Выберите тариф:"""
        await cb.message.edit_text(text, reply_markup=inline.subscription_plans_kb())


@router.callback_query(F.data == "sub:plans")
async def show_plans(cb: CallbackQuery):
    await cb.answer()
    text = f"""⭐ <b>Тарифы подписки</b>

{get_plans_text()}

Выберите тариф:"""
    
    await cb.message.edit_text(text, reply_markup=inline.subscription_plans_kb())


# === ОБРАБОТКА УСПЕШНОЙ ОПЛАТЫ ===
async def process_successful_payment(tx_id: int, robokassa_id: int = None):
    """
    Обработка успешной оплаты и начисление рефераль rewards
    Эта функция должна вызываться из webhook ResultURL от Robokassa
    """
    from aiogram import Bot
    from config import BOT_TOKEN
    
    tx = await db.get_transaction(tx_id)
    if not tx or tx['status'] == 'completed':
        return
    
    user_id = tx['user_id']
    tx_type = tx['type']
    stars = tx['stars']
    
    # Подтверждаем транзакцию
    await db.complete_transaction(tx_id, robokassa_id)
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        # Определяем тип платежа
        if tx_type.startswith('subscription:'):
            sub_type = tx_type.split(':')[1]
            
            # Создаём/обновляем подписку
            await db.create_subscription(user_id, sub_type, stars, days=30)
            
            # Уведомляем пользователя
            plan_name = SUBSCRIPTIONS.get(sub_type, {}).get('name', sub_type)
            await bot.send_message(
                user_id,
                f"✅ <b>Подписка активирована!</b>\n\n"
                f"⭐ Тариф: <b>{plan_name}</b>\n"
                f"⭐ Звёзд: <b>{fmt(stars)}</b>\n"
                f"📅 Действует: <b>30 дней</b>\n\n"
                f"Спасибо за покупку! 🎉"
            )
            
            # Проверяем реферальную систему
            referrer_id = await db.get_referrer_id(user_id)
            if referrer_id:
                # Начисляем награду рефереру
                if sub_type == 'mini':
                    reward_stars = 1000  # 1,000 ⭐ за Mini
                elif sub_type == 'standard':
                    reward_stars = 2000  # 2,000 ⭐ за Standard
                elif sub_type == 'premium':
                    reward_stars = 4000  # 4,000 ⭐ за Premium
                else:
                    reward_stars = 0
                
                if reward_stars > 0:
                    await db.add_referral_reward(referrer_id, user_id, reward_stars, sub_type)
                    
                    # Уведомляем реферера
                    try:
                        await bot.send_message(
                            referrer_id,
                            f"🎉🎉🎉 <b>Реферальная награда!</b>\n\n"
                            f"Ваш реферал оформил подписку <b>{plan_name}</b>!\n\n"
                            f"⭐ Вам начислено: <b>{fmt(reward_stars)}</b>\n\n"
                            f"Продолжайте делиться ссылкой и зарабатывайте больше! 🚀"
                        )
                    except:
                        pass  # Реферер мог заблокировать бота
                    
        elif tx_type.startswith('stars:'):
            # Докупка звёзд
            await db.add_subscription_stars(user_id, stars)
            
            package_id = tx_type.split(':')[1]
            package_name = STAR_PACKAGES.get(package_id, {}).get('name', 'Звёзды')
            
            await bot.send_message(
                user_id,
                f"✅ <b>Звёзды зачислены!</b>\n\n"
                f"📦 Пакет: <b>{package_name}</b>\n"
                f"⭐ Начислено: <b>{fmt(stars)}</b>\n\n"
                f"Спасибо за покупку! 🎉"
            )
    except Exception as e:
        print(f"Error sending payment notification: {e}")
    finally:
        await bot.session.close()
