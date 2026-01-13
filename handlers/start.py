from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from database import db
from keyboards import reply, inline
from config import SUBSCRIPTIONS, NEW_USER_BONUS
HELP_TEXT = """💫 <b>От создателя</b>

Когда мне было очень тяжело — я нашёл поддержку в искусственном интеллекте. Он помог мне стать лучше.

Я решил поделиться этим с людьми.

Изучил программирование, написал тысячи строк кода — чтобы создать инструмент, который поможет:

• Справиться с трудностями и одиночеством
• Найти мотивацию для саморазвития
• Изучить новое и прокачать навыки
• Разобраться в себе и своих целях
• Получить поддержку когда это нужно

Относитесь к этому как к разговору со своей душой.

Здесь самые последние технологии, лучшие разработки — и вложенная душа. Чтобы сделать вас осознаннее и счастливее.

<i>Правда — в глазах смотрящего.</i>

━━━━━━━━━━━━━━━

📢 <a href="https://t.me/soulai_ru">Наш Telegram-канал</a>

🛠 <a href="https://t.me/aidusha_support_bot">Тех. поддержка</a>"""

router = Router()
class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
def fmt(n): 
    return f"{n:,}".replace(",", " ")
async def get_text(key, default=""):
    t = await db.get_text(key)
    return t if t else default
DEFAULT_AGREEMENT = "📜 Соглашение"
@router.message(CommandStart())
async def start(msg: Message, state: FSMContext, command: CommandObject = None):
    await state.clear()
    
    # ВАЖНО: Проверяем deep link для парных сессий ПЕРВЫМ ДЕЛОМ
    # до всех остальных проверок (пользователь, соглашение и т.д.)
    
    # Получаем аргументы команды (для deep link)
    args = None
    if command and command.args:
        args = command.args.strip()
    elif msg.text:
        parts = msg.text.split()
        if len(parts) > 1:
            args = parts[1]  # После /start
    
    if args and args.startswith('pair_'):
        # Это deep link для парной сессии
        pair_code = args.replace('pair_', '').upper().strip()
        
        print(f"🔵 [Deep Link] Обнаружен pair_ код: {pair_code}, user_id: {msg.from_user.id}")
        
        # Проверяем существование сессии
        session = None
        try:
            from database.postgres_db import get_pair_session
            session = await get_pair_session(pair_code)
            
            if not session:
                await msg.answer(
                    "❌ <b>Сессия не найдена</b>\n\n"
                    "Возможно, ссылка устарела или сессия была отменена."
                )
                return
            
            if session.get('status') == 'ended':
                await msg.answer(
                    "❌ <b>Сессия завершена</b>\n\n"
                    "Эта парная сессия уже завершена."
                )
                return
            
        except Exception as e:
            print(f"⚠️ [Deep Link] Ошибка проверки сессии: {e}")
            import traceback
            traceback.print_exc()
            # Продолжаем даже если проверка не удалась
        
        # Создаём кнопку с Web App для присоединения
        join_url = f"https://soul-bot.ru/silas/pair/join?code={pair_code}&user_id={msg.from_user.id}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="👥 Присоединиться к сессии",
                web_app=WebAppInfo(url=join_url)
            )]
        ])
        
        # Получаем информацию о сессии для красивого сообщения
        session_info = ""
        try:
            if session:
                topic_names = {
                    'partner': '💑 Отношения с партнёром',
                    'family': '👨‍👩‍👧 Семейный конфликт',
                    'friend': '👥 С другом/коллегой',
                    'work': '💼 Рабочий конфликт',
                    'other': '🎯 Другое'
                }
                topic = topic_names.get(session.get('topic', ''), 'Не указана')
                session_info = f"\n📋 Тема: {topic}\n"
        except:
            pass
        
        await msg.answer(
            "🔗 <b>Вас пригласили на парную терапию!</b>\n\n"
            f"Код сессии: <code>{pair_code}</code>{session_info}\n"
            "Нажмите кнопку ниже, чтобы присоединиться к сессии:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        print(f"✅ [Deep Link] Отправлено сообщение с кнопкой для user_id: {msg.from_user.id}")
        
        # Восстанавливаем Reply Keyboard после отправки inline-кнопки
        # Важно: InlineKeyboardMarkup не заменяет ReplyKeyboardMarkup,
        # но после отправки inline-кнопки нужно явно восстановить reply-клавиатуру
        try:
            from handlers.silas.keyboards import psycho_kb
            # Отправляем пустое сообщение с reply-клавиатурой для восстановления
            # Используем reply_to_message_id=None чтобы не было связи с предыдущим сообщением
            await msg.answer(
                "💬 Используйте кнопки ниже для навигации",
                reply_markup=psycho_kb(msg.from_user.id)
            )
        except Exception as e:
            print(f"⚠️ [Deep Link] Не удалось восстановить клавиатуру: {e}")
            import traceback
            traceback.print_exc()
        
        return
    
    # Если не deep link для парной сессии - продолжаем обычную логику
    u = await db.get_user(msg.from_user.id)
    
    # Проверяем реферальную ссылку
    referrer_id = None
    if msg.text and len(msg.text.split()) > 1:
        args = msg.text.split()[1]  # После /start
        if args.startswith('ref_'):
            try:
                referrer_id = int(args.replace('ref_', ''))
                # Проверяем что реферер существует и это не сам пользователь
                if referrer_id == msg.from_user.id:
                    referrer_id = None
                elif referrer_id:
                    referrer = await db.get_user(referrer_id)
                    if not referrer:
                        referrer_id = None
            except:
                referrer_id = None
    
    if not u:
        u = await db.create_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name, referrer_id)
        
        # Уведомляем реферера о новом пользователе
        if referrer_id:
            try:
                from aiogram import Bot
                from config import BOT_TOKEN
                bot = Bot(token=BOT_TOKEN)
                await bot.send_message(
                    referrer_id,
                    f"🎉 <b>Новый реферал!</b>\n\n"
                    f"Пользователь {msg.from_user.first_name or 'Новый пользователь'} зарегистрировался по вашей ссылке!\n\n"
                    f"💡 Когда он оформит подписку, вы получите бонусные токены."
                )
            except:
                pass
        
        agreement_text = await get_text("agreement", DEFAULT_AGREEMENT)
        await msg.answer(agreement_text, reply_markup=inline.agree_kb())
        return
    
    if not u['agreement']:
        agreement_text = await get_text("agreement", DEFAULT_AGREEMENT)
        await msg.answer(agreement_text, reply_markup=inline.agree_kb())
        return
    
    # Получаем токены универсальной функцией
    tokens = await db.get_available_tokens(msg.from_user.id)
    has_sub = await db.has_active_subscription(msg.from_user.id)
    
    if has_sub:
        sub = await db.get_subscription(msg.from_user.id)
        sub_info = SUBSCRIPTIONS.get(sub['type'], {})
        start_text = f"✨ <b>С возвращением в Душа AI!</b>\n\n💎 Подписка: <b>{sub_info.get('name', sub['type'])}</b>\n🔢 Токенов: <b>{fmt(tokens)}</b>"
    elif tokens > 0:
        start_text = f"✨ <b>С возвращением в Душа AI!</b>\n\n🎁 Бонусных токенов: <b>{fmt(tokens)}</b>\n\n💡 Оформите подписку для полного доступа"
    else:
        start_text = "✨ <b>С возвращением в Душа AI!</b>\n\n⚠️ Токены закончились\n👉 Оформите подписку в разделе 💠 Подписка"
    
    await msg.answer(start_text, reply_markup=reply.main_kb(msg.from_user.id))
@router.callback_query(F.data == "agree_yes")
async def agree_yes(cb: CallbackQuery, state: FSMContext):
    await db.accept_agreement(cb.from_user.id)
    await cb.message.edit_text(
        "✅ <b>Соглашение принято!</b>\n\n"
        "Давайте познакомимся 🤝\n\n"
        "📝 <b>Как вас зовут?</b>",
        reply_markup=inline.skip_kb("skip:name")
    )
    await state.set_state(Registration.name)
@router.callback_query(F.data == "agree_no")
async def agree_no(cb: CallbackQuery):
    await cb.message.edit_text("❌ Нажмите /start чтобы принять соглашение")
@router.callback_query(F.data == "skip:name")
async def skip_name(cb: CallbackQuery, state: FSMContext):
    await state.update_data(reg_name=None)
    await cb.message.edit_text(
        "📅 <b>Сколько вам лет?</b>",
        reply_markup=inline.skip_kb("skip:age")
    )
    await state.set_state(Registration.age)
@router.message(Registration.name)
async def reg_name(msg: Message, state: FSMContext):
    name = msg.text.strip()[:50]
    await state.update_data(reg_name=name)
    await msg.answer(
        f"Приятно познакомиться, <b>{name}</b>! 👋\n\n📅 <b>Сколько вам лет?</b>",
        reply_markup=inline.skip_kb("skip:age")
    )
    await state.set_state(Registration.age)
@router.callback_query(F.data == "skip:age")
async def skip_age(cb: CallbackQuery, state: FSMContext):
    await state.update_data(reg_age=None)
    await cb.message.edit_text(
        "👤 <b>Укажите ваш пол</b>",
        reply_markup=inline.gender_kb()
    )
    await state.set_state(Registration.gender)
@router.message(Registration.age)
async def reg_age(msg: Message, state: FSMContext):
    try:
        age = int(msg.text.strip())
        if age < 10 or age > 100:
            await msg.answer("❌ Введите возраст от 10 до 100")
            return
        await state.update_data(reg_age=age)
    except:
        await msg.answer("❌ Введите число", reply_markup=inline.skip_kb("skip:age"))
        return
    
    await msg.answer("👤 <b>Укажите ваш пол</b>", reply_markup=inline.gender_kb())
    await state.set_state(Registration.gender)
@router.callback_query(F.data.startswith("gender:"))
async def reg_gender(cb: CallbackQuery, state: FSMContext):
    gender = cb.data.split(":")[1]
    data = await state.get_data()
    
    user_info = []
    if data.get('reg_name'):
        user_info.append(f"Имя: {data['reg_name']}")
    if data.get('reg_age'):
        user_info.append(f"Возраст: {data['reg_age']} лет")
    if gender != 'skip':
        user_info.append(f"Пол: {'мужской' if gender == 'male' else 'женский'}")
    
    # Сохраняем в память ботов
    if user_info:
        for bot_name in ['luca', 'silas', 'titus']:
            existing = await db.get_memory(cb.from_user.id, bot_name)
            await db.save_memory(cb.from_user.id, bot_name, user_info + existing[:47])
    
    # Сохраняем в профиль для кабинета
    gender_text = None
    if gender == 'male':
        gender_text = 'мужской'
    elif gender == 'female':
        gender_text = 'женский'
    
    await db.save_profile(
        cb.from_user.id,
        name=data.get('reg_name'),
        age=data.get('reg_age'),
        gender=gender_text
    )
    
    await state.clear()
    
    # Приветствие (редактируем сообщение с выбором пола)
    await cb.message.edit_text(
        "✨ <b>Добро пожаловать в Soul AI</b>\n\n"
        "Здесь технологии обретают душу.\n\n"
        "Мы создали пространство, где вы найдёте:\n"
        "• Поддержку в трудные моменты\n"
        "• Ответы на важные вопросы\n"
        "• Новые знания и вдохновение\n\n"
        "Это не просто бот — это помощник, который понимает и запоминает.\n\n"
        "👉 <b>Начните с раздела 🔍 Помощь</b>"
    )
    
    # Бонус отдельным сообщением
    await cb.message.answer(
        f"🎁🎁🎁\n\n"
        f"<b>Вам начислено {fmt(NEW_USER_BONUS)} токенов!</b>\n\n"
        f"Попробуйте бесплатно"
    )
    
    await cb.message.answer("Выберите раздел:", reply_markup=reply.main_kb(cb.from_user.id))

# === МЕНЮ БОТОВ ===
@router.message(F.text == "🫧 Soul AI")
async def bots_menu(msg: Message):
    text = """💭 <b>Диалог</b>
Твой внутренний голос — усиленный ИИ.
Находи идеи, вдохновляйся, чувствуй поддержку.

🛋️ <b>Психолог</b>
То, что внутри — влияет на всё вокруг.
Пойми себя глубже, чтобы жить легче.

📓 <b>Обучение</b>
Курсы за сотни тысяч — теперь у тебя.
Шаги • Конспекты • Разбор сложного.
Лучшие репетиторы изменят твоё сознание."""
    await msg.answer(text, reply_markup=reply.bots_menu_kb())
@router.message(F.text == "◀️ Главное меню")
async def back_main_menu(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("🏠 Главное меню", reply_markup=reply.main_kb(msg.from_user.id))
@router.message(F.text == "📱 Кабинет")
async def cabinet(msg: Message):
    u = await db.get_user(msg.from_user.id)
    if not u: return
    
    tokens = await db.get_available_tokens(msg.from_user.id)
    has_sub = await db.has_active_subscription(msg.from_user.id)
    profile = await db.get_profile(msg.from_user.id)
    
    # Профиль
    name = profile.get('name', '—') if profile else '—'
    age = profile.get('age', '—') if profile else '—'
    gender = profile.get('gender', '—') if profile else '—'
    
    # Подписка
    if has_sub:
        sub = await db.get_subscription(msg.from_user.id)
        sub_info = SUBSCRIPTIONS.get(sub['type'], {})
        sub_name = sub_info.get('name', sub['type'])
    else:
        sub_name = "Нет подписки"
    
    text = (
        f"👤 <b>Кабинет</b>\n\n🆔 ID: {msg.from_user.id}\n"
        f"👋 Имя: {name}\n"
        f"🎂 Возраст: {age}\n"
        f"👤 Пол: {gender}\n\n"
        f"💎 {sub_name}\n"
        f"🔢 {fmt(tokens)} токенов"
    )
    
    await msg.answer(text, reply_markup=inline.cabinet_kb())

@router.callback_query(F.data == "my_stats")
async def my_stats_cb(cb: CallbackQuery):
    u = await db.get_user(cb.from_user.id)
    if not u:
        await cb.answer("Ошибка")
        return
    
    total_used = u.get("total_used", 0)
    total_requests = u.get("total_requests", 0)
    created = u.get("created_at", "—")
    
    tokens = await db.get_available_tokens(cb.from_user.id)
    
    # Получаем статистику по ботам
    bots_tokens = await db.get_all_bots_tokens(cb.from_user.id)
    luca_tokens = bots_tokens.get('luca', 0)
    silas_tokens = bots_tokens.get('silas', 0)
    titus_tokens = bots_tokens.get('titus', 0)
    
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"📅 Регистрация: {created[:10] if created else '—'}\n"
        f"💬 Всего запросов: {fmt(total_requests)}\n\n"
        f"💰 <b>Баланс:</b> {fmt(tokens)} токенов\n"
        f"📉 <b>Потрачено всего:</b> {fmt(total_used)} токенов\n\n"
        f"🤖 <b>Использование по ботам:</b>\n"
        f"💭 Luca (Диалог): {fmt(luca_tokens)}\n"
        f"🛋️ Silas (Психолог): {fmt(silas_tokens)}\n"
        f"📓 Titus (Обучение): {fmt(titus_tokens)}"
    )
    await cb.message.edit_text(text, reply_markup=inline.back_kb("cabinet"))

@router.callback_query(F.data == "cabinet")
async def cabinet_cb(cb: CallbackQuery):
    u = await db.get_user(cb.from_user.id)
    if not u: return
    
    tokens = await db.get_available_tokens(cb.from_user.id)
    has_sub = await db.has_active_subscription(cb.from_user.id)
    profile = await db.get_profile(cb.from_user.id)
    
    name = profile.get("name", "—") if profile else "—"
    age = profile.get("age", "—") if profile else "—"
    gender = profile.get("gender", "—") if profile else "—"
    
    if has_sub:
        sub = await db.get_subscription(cb.from_user.id)
        sub_info = SUBSCRIPTIONS.get(sub["type"], {})
        sub_name = sub_info.get("name", sub["type"])
    else:
        sub_name = "Нет подписки"
    
    text = (
        f"👤 <b>Кабинет</b>\n\n🆔 ID: {cb.from_user.id}\n"
        f"👋 Имя: {name}\n"
        f"🎂 Возраст: {age}\n"
        f"👤 Пол: {gender}\n\n"
        f"💎 {sub_name}\n"
        f"🔢 {fmt(tokens)} токенов"
    )
    
    await cb.message.edit_text(text, reply_markup=inline.cabinet_kb())

@router.callback_query(F.data == "topup")
async def topup_cb(cb: CallbackQuery):
    has_sub = await db.has_active_subscription(cb.from_user.id)
    if has_sub:
        await cb.message.edit_text("💰 <b>Докупка токенов</b>", reply_markup=inline.tokens_packages_kb())
    else:
        await cb.answer("⚠️ Докупка доступна только подписчикам", show_alert=True)
        await cb.message.edit_text("⚠️ Для докупки токенов нужна подписка", reply_markup=inline.subscription_plans_kb())
# === ПОМОЩЬ ===
@router.message(F.text == "🔍 Помощь")
async def help_cmd(msg: Message):
    await msg.answer(HELP_TEXT, reply_markup=inline.help_kb())
@router.callback_query(F.data.startswith("help:"))
async def help_section(cb: CallbackQuery):
    s = cb.data.split(":")[1]
    db_keys = {
        'dialog': 'help_dialog', 'psycho': 'help_psycho', 'study': 'help_study', 'pay': 'help_pay',
        'luca': 'help_dialog', 'silas': 'help_psycho', 'titus': 'help_study'
    }
    defaults = {
        'dialog': '💭 Диалог — умный собеседник с памятью',
        'psycho': '🛋️ Психолог — поддержка и работа с эмоциями',
        'study': '📓 Обучение — персональные курсы',
        'pay': '💳 Оплата — пополнение баланса',
        'luca': '💭 Диалог', 'silas': '🛋️ Психолог', 'titus': '📓 Обучение'
    }
    text = await get_text(db_keys.get(s, ""), defaults.get(s, "?"))
    await cb.message.edit_text(text, reply_markup=inline.back_kb("help_back"))
@router.callback_query(F.data == "help_back")
async def help_back(cb: CallbackQuery):
    await cb.message.edit_text(HELP_TEXT, reply_markup=inline.help_kb())
@router.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery):
    await cb.message.delete()
@router.callback_query(F.data == "bots")
async def bots_cb(cb: CallbackQuery):
    text = """

🛋️ <b>Психолог</b>
То, что внутри — влияет на всё вокруг.
Пойми себя глубже, чтобы жить легче.

📓 <b>Обучение</b>
Курсы за сотни тысяч — теперь у тебя.
Шаги • Конспекты • Разбор сложного.
Лучшие репетиторы изменят твоё сознание."""
    await cb.message.edit_text(text, reply_markup=inline.bots_kb())
@router.message(Command("restart"), StateFilter("*"))
async def cmd_restart(msg: Message, state: FSMContext):
    """Перезапуск бота - сброс состояния и возврат в главное меню"""
    await state.clear()
    u = await db.get_user(msg.from_user.id)
    
    if not u:
        agreement_text = await get_text("agreement", DEFAULT_AGREEMENT)
        await msg.answer(agreement_text, reply_markup=inline.agree_kb())
        return
    
    if not u['agreement']:
        agreement_text = await get_text("agreement", DEFAULT_AGREEMENT)
        await msg.answer(agreement_text, reply_markup=inline.agree_kb())
        return
    
    tokens = await db.get_available_tokens(msg.from_user.id)
    await msg.answer(
        f"🔄 Бот перезапущен!\n\n💎 Ваши токены: {fmt(tokens)}\n\nВыберите собеседника:",
        reply_markup=reply.main_kb(msg.from_user.id)
    )

@router.message(Command("help"))
async def cmd_help(msg: Message):
    """Помощь и поддержка"""
    help_text = """🆘 <b>Помощь и поддержка</b>

📞 <b>Техническая поддержка:</b>
@soulrus_support_bot

📢 <b>Наш Telegram-канал:</b>
https://t.me/soulai_ru"""
    
    await msg.answer(help_text, disable_web_page_preview=True)
