from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from database import db
from keyboards import inline
from utils.robokassa import generate_payment_link
from config import SUBSCRIPTIONS, TOKEN_PACKAGES, NEW_USER_BONUS


router = Router()


def fmt(n): 
    return f"{n:,}".replace(",", " ")


def format_date(date_str):
    if not date_str:
        return "Бессрочно"
    return date_str[:10]


def get_plans_text():
    return """<b>Доступные тарифы:</b>

💎 <b>Мини</b> — 490 ₽/мес

✨ Психолог нового поколения
✨ Память и эмоции — помнит ваши разговоры
✨ Мотивация, поддержка, решение задач
✨ Голосовые сообщения и фото
✨ 400 000 токенов (~70 диалогов)

❌ Нет доступа к Обучению

<i>Первый ИИ, который слышит и понимает</i>

👑 <b>Стандарт</b> — 990 ₽/мес

<b>Всё из Мини, плюс:</b>

🧠 Claude Opus 4 — самая умная модель
🎓 Все курсы в твоём телефоне
📚 Разбивает материал на шаги как лучший репетитор
❓ Задаёт вопросы, разбирает сложные темы
📝 Конспекты для глубокого усвоения
✨ 900 000 токенов (~158 диалогов)

<i>Полный доступ к обучению без границ</i>"""


# === МЕНЮ ПОДПИСКИ ===
@router.message(F.text == "💠 Подписка")
async def subscription_menu(msg: Message):
    tokens = await db.get_available_tokens(msg.from_user.id)
    has_sub = await db.has_active_subscription(msg.from_user.id)
    
    if has_sub:
        sub = await db.get_subscription(msg.from_user.id)
        sub_info = SUBSCRIPTIONS.get(sub['type'], {})
        sub_name = sub_info.get('name', sub['type'])
        total = sub['tokens_limit']
        
        text = f"""⭐ <b>Ваша подписка</b>

💎 Тариф: <b>{sub_name}</b>
📅 Действует до: <b>{format_date(sub['expires_at'])}</b>

🔢 Токенов: <b>{fmt(tokens)}</b> из {fmt(total)}
💬 Примерно сообщений: ~{tokens // 3700}

Выберите действие:"""
        
        await msg.answer(text, reply_markup=inline.subscription_active_kb())
    elif tokens > 0:
        # Есть бонусные токены, но нет подписки
        text = f"""⭐ <b>Подписка</b>

🎁 У вас <b>{fmt(tokens)}</b> бонусных токенов
💬 Примерно сообщений: ~{tokens // 3700}

{get_plans_text()}

Выберите тариф:"""
        
        await msg.answer(text, reply_markup=inline.subscription_plans_kb())
    else:
        # Нет токенов и нет подписки
        text = f"""⭐ <b>Подписка</b>

⚠️ У вас закончились токены

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
        tokens=plan['tokens'],
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

💎 Тариф: <b>{plan['name']}</b>
💰 Сумма: <b>{plan['price']} ₽</b>
🔢 Токенов: <b>{fmt(plan['tokens'])}</b>

Нажмите кнопку для оплаты:"""
    
    await cb.message.edit_text(text, reply_markup=inline.payment_kb(payment_url, tx_id))
    await cb.answer()


# === ДОКУПКА ТОКЕНОВ ===
@router.callback_query(F.data == "sub:tokens")
async def tokens_menu(cb: CallbackQuery):
    has_sub = await db.has_active_subscription(cb.from_user.id)
    
    if not has_sub:
        await cb.answer("⚠️ Докупка доступна только подписчикам", show_alert=True)
        text = """⚠️ <b>Докупка токенов</b>

Докупка токенов доступна только для пользователей с активной подпиской.

👉 Оформите подписку, чтобы получить доступ."""
        await cb.message.edit_text(text, reply_markup=inline.back_to_sub_kb())
        return
    
    tokens = await db.get_available_tokens(cb.from_user.id)
    
    text = f"""💎 <b>Докупка токенов</b>

🔢 Текущий баланс: <b>{fmt(tokens)}</b> токенов

<b>Пакеты:</b>

📦 100K токенов — <b>90 ₽</b>
📦 200K токенов — <b>180 ₽</b>

Выберите пакет:"""
    
    await cb.message.edit_text(text, reply_markup=inline.tokens_packages_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("tokens:buy:"))
async def buy_tokens(cb: CallbackQuery):
    package_id = cb.data.split(":")[2]
    
    has_sub = await db.has_active_subscription(cb.from_user.id)
    if not has_sub:
        await cb.answer("⚠️ Докупка доступна только подписчикам", show_alert=True)
        return
    
    if package_id not in TOKEN_PACKAGES:
        await cb.answer("❌ Неизвестный пакет", show_alert=True)
        return
    
    package = TOKEN_PACKAGES[package_id]
    
    tx_id = await db.create_transaction(
        uid=cb.from_user.id,
        amount=package['price'],
        tokens=package['tokens'],
        tx_type=f"tokens:{package_id}"
    )
    
    payment_url = generate_payment_link(
        order_id=tx_id,
        amount=package['price'],
        description=f"Докупка {package['name']} - Душа AI",
        user_id=cb.from_user.id,
        payment_type=f"tokens:{package_id}"
    )
    
    text = f"""💳 <b>Оплата токенов</b>

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
            "✅ <b>Оплата подтверждена!</b>\n\nТокены зачислены на ваш баланс.",
            reply_markup=inline.back_to_sub_kb()
        )
    else:
        await cb.answer("⏳ Оплата ещё не поступила. Подождите немного.", show_alert=True)


# === НАВИГАЦИЯ ===
@router.callback_query(F.data == "sub:back")
async def back_to_subscription(cb: CallbackQuery):
    await cb.answer()
    tokens = await db.get_available_tokens(cb.from_user.id)
    has_sub = await db.has_active_subscription(cb.from_user.id)
    
    if has_sub:
        sub = await db.get_subscription(cb.from_user.id)
        sub_info = SUBSCRIPTIONS.get(sub['type'], {})
        sub_name = sub_info.get('name', sub['type'])
        total = sub['tokens_limit']
        
        text = f"""⭐ <b>Ваша подписка</b>

💎 Тариф: <b>{sub_name}</b>
📅 Действует до: <b>{format_date(sub['expires_at'])}</b>

🔢 Токенов: <b>{fmt(tokens)}</b> из {fmt(total)}

Выберите действие:"""
        
        await cb.message.edit_text(text, reply_markup=inline.subscription_active_kb())
    else:
        text = f"""⭐ <b>Подписка</b>

{"🎁 Бонусных токенов: " + fmt(tokens) if tokens > 0 else "⚠️ Токены закончились"}

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
    tokens = tx['tokens']
    
    # Подтверждаем транзакцию
    await db.complete_transaction(tx_id, robokassa_id)
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        # Определяем тип платежа
        if tx_type.startswith('subscription:'):
            sub_type = tx_type.split(':')[1]
            
            # Создаём/обновляем подписку
            await db.create_subscription(user_id, sub_type, tokens, days=30)
            
            # Уведомляем пользователя
            plan_name = SUBSCRIPTIONS.get(sub_type, {}).get('name', sub_type)
            await bot.send_message(
                user_id,
                f"✅ <b>Подписка активирована!</b>\n\n"
                f"💎 Тариф: <b>{plan_name}</b>\n"
                f"🔢 Токенов: <b>{fmt(tokens)}</b>\n"
                f"📅 Действует: <b>30 дней</b>\n\n"
                f"Спасибо за покупку! 🎉"
            )
            
            # Проверяем реферальную систему
            referrer_id = await db.get_referrer_id(user_id)
            if referrer_id:
                # Начисляем награду рефереру
                if sub_type == 'mini':
                    reward_tokens = 100000  # 100K за Mini
                elif sub_type == 'standard':
                    reward_tokens = 200000  # 200K за Standard
                else:
                    reward_tokens = 0
                
                if reward_tokens > 0:
                    await db.add_referral_reward(referrer_id, user_id, reward_tokens, sub_type)
                    
                    # Уведомляем реферера
                    try:
                        await bot.send_message(
                            referrer_id,
                            f"🎉🎉🎉 <b>Реферальная награда!</b>\n\n"
                            f"Ваш реферал оформил подписку <b>{plan_name}</b>!\n\n"
                            f"💰 Вам начислено: <b>{fmt(reward_tokens)}</b> токенов\n\n"
                            f"Продолжайте делиться ссылкой и зарабатывайте больше! 🚀"
                        )
                    except:
                        pass  # Реферер мог заблокировать бота
                    
        elif tx_type.startswith('tokens:'):
            # Докупка токенов
            await db.add_subscription_tokens(user_id, tokens)
            
            package_id = tx_type.split(':')[1]
            package_name = TOKEN_PACKAGES.get(package_id, {}).get('name', 'Токены')
            
            await bot.send_message(
                user_id,
                f"✅ <b>Токены зачислены!</b>\n\n"
                f"📦 Пакет: <b>{package_name}</b>\n"
                f"🔢 Начислено: <b>{fmt(tokens)}</b> токенов\n\n"
                f"Спасибо за покупку! 🎉"
            )
    except Exception as e:
        print(f"Error sending payment notification: {e}")
    finally:
        await bot.session.close()
