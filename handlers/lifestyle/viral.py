"""
Обработчик вирусного разбора
Оптимизирован с core/ интеграцией
"""
import asyncio
import base64
import logging
import os
import aiohttp

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import postgres_db as db
from keyboards import reply, inline
from utils.stars import calculate_stars
from utils.video_downloader import download_video_from_url, extract_key_frames, cleanup_temp_files
from utils.markdown import md_to_html
from utils.conversations import save_message, clean_response, get_chat_button
from utils.balance_guard import ensure_balance
from utils.status_manager import show_status
from utils.streaming import stream_response
from prompts.viral_expert import VIRAL_EXPERT_PROMPT, VIRAL_TEXT_ADVICE_PROMPT
from config import MIN_STARS, OPENROUTER_API_KEY
from loader import bot

# Core infrastructure
from core import rate_limiter, cleanup_manager
from core.cache import LRUCache
from core.config import MSG_RATE_LIMITED

logger = logging.getLogger(__name__)

router = Router()


class ViralAnalysisSt(StatesGroup):
    """Состояния для вирусного разбора"""
    menu = State()
    text_advice = State()
    wait_video = State()
    wait_link = State()


# Цены (маржа уже включена)
PRICES = {
    "text_advice": 50,  # Минимальная цена за текстовый совет (рассчитывается автоматически с маржой 2.5x)
    "video_analysis": 300,  # За анализ видео (Vision API ~ 120 звёзд × 2.5 = 300)
    "link_analysis": 300  # За анализ по ссылке (Vision API ~ 120 звёзд × 2.5 = 300)
}


# ========== МЕНЮ ==========

@router.message(F.text == "🎬 Вирусный разбор")
async def viral_menu(msg: Message, state: FSMContext):
    """Главное меню вирусного разбора"""
    cfg = await db.get_bot_cfg('titus')  # Используем конфиг обучения
    if not cfg['enabled']:
        await msg.answer("🔴 Функция временно недоступна")
        return
    
    await state.set_state(ViralAnalysisSt.menu)
    stars = await db.get_available_stars(msg.from_user.id)
    
    await msg.answer(
        "🎬 <b>Вирусный разбор</b>\n\n"
        "Я помогу твоим роликам набрать миллионы просмотров!\n\n"
        "⭐ Баланс: <b>{:,}</b> звёзд\n\n"
        "Выбери что нужно:".format(stars),
        reply_markup=reply.viral_kb(msg.from_user.id),
        parse_mode="HTML"
    )


@router.message(ViralAnalysisSt.menu, F.text == "💬 Текстовый совет")
async def text_advice_start(msg: Message, state: FSMContext):
    """Начать текстовый совет"""
    if not await ensure_balance(msg, required=MIN_STARS):
        return
    
    await state.set_state(ViralAnalysisSt.text_advice)
    
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🛑 Отменить")]],
        resize_keyboard=True
    )
    
    await msg.answer(
        "💬 <b>Текстовый совет</b>\n\n"
        "Задай любой вопрос по созданию вирусных видео!\n\n"
        "<i>Примеры:\n"
        "• Как снять хук на первые 3 секунды?\n"
        "• Какая музыка сейчас в трендах?\n"
        "• Как попасть в рекомендации TikTok?</i>",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )


@router.message(ViralAnalysisSt.menu, F.text == "📤 Загрузить видео")
async def upload_video_start(msg: Message, state: FSMContext):
    """Начать загрузку видео"""
    if not await ensure_balance(msg, required=PRICES['video_analysis']):
        return
    
    await state.set_state(ViralAnalysisSt.wait_video)
    
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🛑 Отменить")]],
        resize_keyboard=True
    )
    
    await msg.answer(
        "📤 <b>Загрузить видео</b>\n\n"
        "Отправьте видео для анализа\n\n"
        f"⭐ Стоимость: {PRICES['video_analysis']:,} звёзд\n\n"
        "<i>⚠️ Максимальный размер: 20 MB\n"
        "📏 Длительность: до 3 минут\n\n"
        "Если видео больше 20 MB — используйте кнопку 🔗 Отправить ссылку</i>",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )


@router.message(ViralAnalysisSt.menu, F.text == "🔗 Отправить ссылку")
async def link_start(msg: Message, state: FSMContext):
    """Начать анализ по ссылке"""
    if not await ensure_balance(msg, required=PRICES['link_analysis']):
        return
    
    await state.set_state(ViralAnalysisSt.wait_link)
    
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🛑 Отменить")]],
        resize_keyboard=True
    )
    
    await msg.answer(
        "🔗 <b>Отправить ссылку</b>\n\n"
        "Отправьте ссылку на видео\n\n"
        f"⭐ Стоимость: {PRICES['link_analysis']:,} звёзд\n\n"
        "<i>Поддержка:\n"
        "• TikTok\n"
        "• Instagram Reels\n"
        "• YouTube Shorts</i>",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )


@router.message(F.text == "🛑 Отменить")
async def cancel_operation(msg: Message, state: FSMContext):
    """Отменить операцию и вернуться в меню Вирусного разбора"""
    current_state = await state.get_state()
    if current_state and current_state.startswith("ViralAnalysisSt"):
        # Возвращаем в меню Вирусного разбора (не очищаем состояние!)
        await state.set_state(ViralAnalysisSt.menu)
        await msg.answer("❌ Операция отменена", reply_markup=reply.viral_kb(msg.from_user.id))


@router.message(ViralAnalysisSt.menu, F.text == "◀️ Назад")
async def back_from_viral(msg: Message, state: FSMContext):
    """Возврат из меню вирусного разбора в Соцсети"""
    from handlers.socials import SocialsStates
    from keyboards.reply import socials_menu_kb
    await state.set_state(SocialsStates.menu)
    await msg.answer("📲 Соцсети", reply_markup=socials_menu_kb(msg.from_user.id))


@router.message(ViralAnalysisSt.menu, F.text == "🛑 Завершить")
async def exit_viral(msg: Message, state: FSMContext):
    """Выход из вирусного разбора"""
    await state.clear()
    from keyboards.reply import socials_menu_kb
    await msg.answer("📲 Соцсети", reply_markup=socials_menu_kb(msg.from_user.id))


# ========== ТЕКСТОВЫЙ СОВЕТ ==========

# Кэш активных запросов с автоочисткой (вместо dict)
active_requests_cache = LRUCache(max_size=500, default_ttl=3600)

# Регистрация очистки
cleanup_manager.register(active_requests_cache.cleanup)

@router.message(ViralAnalysisSt.text_advice)
async def process_text_advice(msg: Message, state: FSMContext):
    """Обработка текстового совета со стримингом"""
    if not msg.text or msg.text == "🛑 Отменить":
        return
    
    user_id = msg.from_user.id
    text = msg.text
    
    # Rate limiting через core
    allowed, wait_time = await rate_limiter.check(user_id)
    if not allowed:
        await msg.answer(MSG_RATE_LIMITED.format(seconds=wait_time))
        return
    
    # Проверка звёзд
    if not await ensure_balance(msg, required=MIN_STARS):
        await state.clear()
        return
    
    # Инициализируем состояние запроса через кэш
    request_state = {'cancelled': False}
    await active_requests_cache.set(user_id, request_state)
    
    # Кнопка отмены
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏹ Отменить", callback_data=f"viral_text_cancel:{user_id}")]
    ])
    cancel_msg = await msg.answer("⏹ Можно отменить запрос", reply_markup=cancel_kb)
    try:
        # Получаем модель пользователя
        model = await db.get_user_model(user_id)
        
        # Формируем запрос
        messages = [
            {"role": "system", "content": VIRAL_TEXT_ADVICE_PROMPT},
            {"role": "user", "content": text}
        ]
        
        # Стриминг ответа через единый модуль
        resp, sent_msg = await stream_response(
            bot=bot,
            message=msg,
            messages=messages,
            model=model,
            status_type="text"
        )
        if cancel_msg:
            try:
                await cancel_msg.delete()
            except:
                pass
        
        if not resp:
            await msg.answer("❌ Пустой ответ от AI")
            await active_requests_cache.delete(user_id)
            await state.clear()
            return
        
        # Очищаем ответ
        resp = clean_response(resp)
        
        # Точный подсчёт звёзд
        stars_used = calculate_stars(messages, resp)
        
        # Списываем звёзды параллельно
        await asyncio.gather(
            db.use_stars_smart(user_id, stars_used, 'titus'),
            db.increment_requests(user_id)
        )
        
        # Сохраняем в диалог
        conv_id = await save_message(user_id, 'user', text, 'viral', model)
        await save_message(user_id, 'assistant', resp, 'viral', model)
        
        new_balance = await db.get_available_stars(user_id)
        
        # Получаем кнопку диалога
        dialog_kb = get_chat_button(conv_id, len(resp))
        
        # Добавляем кнопку и инфо о звездых к существующему сообщению
        if sent_msg:
            try:
                # Добавляем footer с звездыми к существующему тексту
                current_text = sent_msg.text or ""
                final_text = f"{current_text}\n\n<i>⭐ Списано: {stars_used:,} | Остаток: {new_balance:,}</i>"
                await sent_msg.edit_text(final_text, reply_markup=dialog_kb, parse_mode="HTML")
            except Exception:
                # Если не удалось отредактировать - отправляем отдельное info-сообщение
                await msg.answer(
                    f"<i>⭐ Списано: {stars_used:,} | Остаток: {new_balance:,}</i>",
                    reply_markup=dialog_kb,
                    parse_mode="HTML"
                )
        else:
            await msg.answer(
                f"<i>⭐ Списано: {stars_used:,} | Остаток: {new_balance:,}</i>",
                reply_markup=dialog_kb,
                parse_mode="HTML"
            )
        
    except Exception as e:
        logger.exception(f"Viral text advice error: {e}")
        if cancel_msg:
            try:
                await cancel_msg.delete()
            except:
                pass
    
    await active_requests_cache.delete(user_id)
    await state.clear()


@router.callback_query(F.data.startswith("viral_text_cancel:"))
async def cancel_viral_text_request(callback: CallbackQuery, state: FSMContext):
    """Отмена текстового запроса"""
    user_id = int(callback.data.split(":")[1])
    
    if callback.from_user.id != user_id:
        await callback.answer("❌ Это не ваш запрос")
        return
    
    # Устанавливаем флаг отмены через кэш
    request_state = await active_requests_cache.get(user_id)
    if request_state:
        request_state['cancelled'] = True
        await active_requests_cache.set(user_id, request_state)
    
    await callback.message.edit_text("⏹ Запрос отменён", reply_markup=None)
    await callback.answer("✅ Запрос отменён")


# ========== АНАЛИЗ ВИДЕО ==========

@router.message(ViralAnalysisSt.wait_video, F.video | F.document)
async def process_video(msg: Message, state: FSMContext):
    """Обработка загруженного видео"""
    user_id = msg.from_user.id
    
    # Проверка звёзд
    if not await ensure_balance(msg, required=PRICES['video_analysis']):
        await state.clear()
        return
    
    # Получаем видео (может быть как video, так и document)
    video = msg.video or msg.document
    
    if not video:
        await msg.answer("❌ Отправьте видео файл")
        return
    
    # Проверка размера файла (лимит Telegram Bot API - 20 MB)
    MAX_SIZE = 20 * 1024 * 1024  # 20 MB
    file_size = video.file_size
    
    if file_size > MAX_SIZE:
        size_mb = file_size / (1024 * 1024)
        await msg.answer(
            f"⚠️ <b>Видео слишком большое!</b>\n\n"
            f"📦 Размер: {size_mb:.1f} MB\n"
            f"📏 Лимит: 20 MB\n\n"
            f"<b>Варианты:</b>\n"
            f"• Сожми видео и отправь снова\n"
            f"• Отправь ссылку на видео через кнопку <b>🔗 Отправить ссылку</b>\n\n"
            f"<i>Поддерживаются: TikTok, Instagram, YouTube Shorts</i>",
            parse_mode="HTML"
        )
        return
    
    # Инициализируем состояние запроса
    request_state = {'cancelled': False}
    await state.update_data(request_state=request_state)
    
    # Кнопка отмены
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏹ Отменить", callback_data=f"viral_cancel:{user_id}")]
    ])
    
    cancel_msg = await msg.answer("⏹ Можно отменить запрос", reply_markup=cancel_kb)
    status = await show_status(msg.bot, msg.chat.id, "photo")
    
    temp_files = []
    
    try:
        # Проверка на отмену
        data = await state.get_data()
        if data.get('request_state', {}).get('cancelled'):
            if status:
                await status.stop()
            if cancel_msg:
                await cancel_msg.edit_text("⏹ Запрос отменён", reply_markup=None)
            await state.clear()
            return
        
        # Скачиваем видео
        file = await bot.get_file(video.file_id)
        file_path = file.file_path
        
        # Скачиваем во временный файл
        import tempfile
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        temp_files.append(temp_video.name)
        
        video_data = await bot.download_file(file_path)
        temp_video.write(await video_data.read())
        temp_video.close()
        
        # Проверка на отмену
        data = await state.get_data()
        if data.get('request_state', {}).get('cancelled'):
            if status:
                await status.stop()
            if cancel_msg:
                await cancel_msg.edit_text("⏹ Запрос отменён", reply_markup=None)
            cleanup_temp_files(temp_files)
            await state.clear()
            return
        
        # Извлекаем кадры
        frames = await extract_key_frames(temp_video.name, num_frames=6)
        temp_files.extend(frames)
        
        # Проверка на отмену
        data = await state.get_data()
        if data.get('request_state', {}).get('cancelled'):
            if status:
                await status.stop()
            if cancel_msg:
                await cancel_msg.edit_text("⏹ Запрос отменён", reply_markup=None)
            cleanup_temp_files(temp_files)
            await state.clear()
            return
        
        # Анализируем через ProxyAPI Vision
        try:
            analysis = await analyze_video_frames(frames)
        except Exception as vision_error:
            # Если Vision API отказался, используем текстовый анализ
            error_msg = str(vision_error)
            if "отказался анализировать" in error_msg or "I'm sorry" in error_msg or "I can't assist" in error_msg:
                if status:
                    await status.stop()
                if cancel_msg:
                    await cancel_msg.delete()
                await msg.answer(
                    "⚠️ Анализ кадров недоступен.\n"
                    "💡 Используйте <b>💬 Текстовый совет</b> - опишите своё видео текстом, и я дам рекомендации!",
                    parse_mode="HTML"
                )
                cleanup_temp_files(temp_files)
                await state.clear()
                return
            else:
                raise vision_error
        
        # Проверка на отмену перед отправкой
        data = await state.get_data()
        if data.get('request_state', {}).get('cancelled'):
            await status.edit_text("⏹ Запрос отменён", reply_markup=None)
            cleanup_temp_files(temp_files)
            await state.clear()
            return
        
        # Списываем звёзды и получаем модель параллельно
        model = await db.get_user_model(user_id)
        await asyncio.gather(
            db.use_stars_smart(user_id, PRICES['video_analysis'], 'titus'),
            db.increment_requests(user_id)
        )
        
        # Сохраняем в диалог
        conv_id = await save_message(user_id, 'user', '📤 Загрузил видео для анализа', 'viral', model)
        await save_message(user_id, 'assistant', analysis, 'viral', model)
        
        new_balance = await db.get_available_stars(user_id)
        
        if status:
            await status.stop()
        if cancel_msg:
            await cancel_msg.delete()
        
        # Получаем кнопку диалога
        dialog_kb = get_chat_button(conv_id, len(analysis))
        
        # Отправляем результат с кнопкой диалога
        await msg.answer(
            f"{analysis}\n\n"
            f"<i>⭐ Списано: {PRICES['video_analysis']:,} | Остаток: {new_balance:,}</i>",
            reply_markup=dialog_kb,
            parse_mode="HTML"
        )
        
    except Exception as e:
        error_text = str(e)
        await msg.answer(
            f"❌ <b>Ошибка</b>\n\n<code>{error_text[:300]}</code>",
            parse_mode="HTML"
        )
    finally:
        # Очищаем временные файлы
        cleanup_temp_files(temp_files)
        if status:
            await status.stop()
        if cancel_msg:
            try:
                await cancel_msg.delete()
            except Exception:
                pass
    
    await state.clear()


@router.callback_query(F.data.startswith("viral_cancel:"))
async def cancel_viral_request(callback: CallbackQuery, state: FSMContext):
    """Отмена запроса в вирусном разборе"""
    user_id = int(callback.data.split(":")[1])
    
    if callback.from_user.id != user_id:
        await callback.answer("❌ Это не ваш запрос")
        return
    
    # Устанавливаем флаг отмены
    await state.update_data(request_state={'cancelled': True})
    
    await callback.message.edit_text("⏹ Запрос отменён", reply_markup=None)
    await callback.answer("✅ Запрос отменён")


# ========== АНАЛИЗ ПО ССЫЛКЕ ==========

@router.message(ViralAnalysisSt.wait_link)
async def process_link(msg: Message, state: FSMContext):
    """Обработка ссылки на видео"""
    if not msg.text or msg.text == "🛑 Отменить":
        return
    
    user_id = msg.from_user.id
    url = msg.text.strip()
    
    # Проверка что это ссылка
    if not url.startswith(("http://", "https://")):
        await msg.answer("❌ Отправьте корректную ссылку на видео")
        return
    
    # Проверка звёзд
    if not await ensure_balance(msg, required=PRICES['link_analysis']):
        await state.clear()
        return
    
    # Инициализируем состояние запроса
    request_state = {'cancelled': False}
    await state.update_data(request_state=request_state)
    
    # Кнопка отмены
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏹ Отменить", callback_data=f"viral_cancel:{user_id}")]
    ])
    
    cancel_msg = await msg.answer("⏹ Можно отменить запрос", reply_markup=cancel_kb)
    status = await show_status(msg.bot, msg.chat.id, "photo")
    
    temp_files = []
    
    try:
        # Проверка на отмену
        data = await state.get_data()
        if data.get('request_state', {}).get('cancelled'):
            if status:
                await status.stop()
            if cancel_msg:
                await cancel_msg.edit_text("⏹ Запрос отменён", reply_markup=None)
            await state.clear()
            return
        
        # Скачиваем видео по ссылке
        video_path = await download_video_from_url(url)
        temp_files.append(video_path)
        
        # Проверка на отмену
        data = await state.get_data()
        if data.get('request_state', {}).get('cancelled'):
            if status:
                await status.stop()
            if cancel_msg:
                await cancel_msg.edit_text("⏹ Запрос отменён", reply_markup=None)
            cleanup_temp_files(temp_files)
            await state.clear()
            return
        
        # Извлекаем кадры
        frames = await extract_key_frames(video_path, num_frames=6)
        temp_files.extend(frames)
        
        # Проверка на отмену
        data = await state.get_data()
        if data.get('request_state', {}).get('cancelled'):
            if status:
                await status.stop()
            if cancel_msg:
                await cancel_msg.edit_text("⏹ Запрос отменён", reply_markup=None)
            cleanup_temp_files(temp_files)
            await state.clear()
            return
        
        # Анализируем
        try:
            analysis = await analyze_video_frames(frames)
        except Exception as vision_error:
            # Если Vision API отказался, используем текстовый анализ
            error_msg = str(vision_error)
            if "отказался анализировать" in error_msg or "I'm sorry" in error_msg or "I can't assist" in error_msg:
                if status:
                    await status.stop()
                if cancel_msg:
                    await cancel_msg.delete()
                await msg.answer(
                    "⚠️ Анализ кадров недоступен.\n"
                    "💡 Используйте <b>💬 Текстовый совет</b> - опишите своё видео текстом, и я дам рекомендации!",
                    parse_mode="HTML"
                )
                cleanup_temp_files(temp_files)
                await state.clear()
                return
            else:
                raise vision_error
        
        # Проверка на отмену перед отправкой
        data = await state.get_data()
        if data.get('request_state', {}).get('cancelled'):
            if status:
                await status.stop()
            if cancel_msg:
                await cancel_msg.edit_text("⏹ Запрос отменён", reply_markup=None)
            cleanup_temp_files(temp_files)
            await state.clear()
            return
        
        # Списываем звёзды и получаем модель параллельно
        model = await db.get_user_model(user_id)
        await asyncio.gather(
            db.use_stars_smart(user_id, PRICES['link_analysis'], 'titus'),
            db.increment_requests(user_id)
        )
        
        # Сохраняем в диалог
        conv_id = await save_message(user_id, 'user', f'🔗 Отправил ссылку: {url}', 'viral', model)
        await save_message(user_id, 'assistant', analysis, 'viral', model)
        
        new_balance = await db.get_available_stars(user_id)
        
        if status:
            await status.stop()
        if cancel_msg:
            await cancel_msg.delete()
        
        # Получаем кнопку диалога
        dialog_kb = get_chat_button(conv_id, len(analysis))
        
        # Отправляем результат с кнопкой диалога
        await msg.answer(
            f"{analysis}\n\n"
            f"<i>⭐ Списано: {PRICES['link_analysis']:,} | Остаток: {new_balance:,}</i>",
            reply_markup=dialog_kb,
            parse_mode="HTML"
        )
        
    except Exception as e:
        error_text = str(e)
        
        # Красивое сообщение об ошибке
        if "Instagram временно недоступен" in error_text:
            await msg.answer(
                "❌ <b>Instagram временно недоступен</b>\n\n"
                "💡 <b>Что делать:</b>\n"
                "• Попробуйте загрузить видео напрямую через кнопку <b>📤 Загрузить видео</b>\n"
                "• Или попробуйте позже",
                parse_mode="HTML"
            )
        elif "Видео недоступно" in error_text or "приватное" in error_text:
            await msg.answer(
                "❌ <b>Видео недоступно</b>\n\n"
                "Возможные причины:\n"
                "• Видео приватное\n"
                "• Видео удалено\n"
                "• Аккаунт закрыт",
                parse_mode="HTML"
            )
        elif "не поддерживается" in error_text:
            await msg.answer(
                "❌ <b>Платформа не поддерживается</b>\n\n"
                "✅ Поддерживаются:\n"
                "• TikTok\n"
                "• YouTube Shorts\n"
                "• Instagram Reels (не всегда)\n\n"
                "💡 Попробуйте загрузить видео напрямую",
                parse_mode="HTML"
            )
        else:
            await msg.answer(
                f"❌ <b>Ошибка</b>\n\n<code>{error_text[:300]}</code>",
                parse_mode="HTML"
            )
    finally:
        # Очищаем временные файлы
        cleanup_temp_files(temp_files)
        if status:
            await status.stop()
        if cancel_msg:
            try:
                await cancel_msg.delete()
            except Exception:
                pass
    
    await state.clear()


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

async def analyze_video_frames(frames: list) -> str:
    """
    Анализирует кадры видео через ProxyAPI Vision
    Возвращает красиво отформатированный ответ
    """
    from config import OPENAI_API_KEY as PROXYAPI_KEY
    
    # Конвертируем кадры в base64
    content = [
        {
            "type": "text", 
            "text": f"""{VIRAL_EXPERT_PROMPT}

Проанализируй эти {len(frames)} кадров из короткого видео (TikTok/Reels/Shorts). 
Дай конкретные рекомендации по улучшению для достижения вирусности."""
        }
    ]
    
    # Читаем файлы асинхронно чтобы не блокировать event loop
    def read_frame_sync(path: str) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    
    for i, frame_path in enumerate(frames, 1):
        img_base64 = await asyncio.to_thread(read_frame_sync, frame_path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img_base64}",
                "detail": "high"
            }
        })
    
    # Запрос к ProxyAPI
    headers = {
        "Authorization": f"Bearer {PROXYAPI_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 2000,
        "temperature": 0.7
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.proxyapi.ru/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=180)
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise Exception(f"ProxyAPI Error {resp.status}: {error}")
            
            result = await resp.json()
            raw_response = result["choices"][0]["message"]["content"]
            
            # Проверяем на отказ
            if "I'm sorry" in raw_response or "I can't assist" in raw_response or "I cannot" in raw_response:
                raise Exception("Vision API отказался анализировать видео. Попробуйте другое видео или используйте текстовый совет.")
            
            # Форматируем ответ красиво
            formatted = format_viral_response(raw_response)
            return formatted


def format_viral_response(text: str) -> str:
    """Форматирует ответ с HTML разметкой для Telegram"""
    
    # Сначала конвертируем весь Markdown в HTML
    text = md_to_html(text)
    
    # Добавляем заголовок
    formatted = "🎬 <b>РАЗБОР ТВОЕГО ВИДЕО</b>\n\n"
    formatted += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Заменяем заголовки секций на жирные с эмодзи
    text = text.replace("### ⚡ ПЕРВЫЕ 3 СЕКУНДЫ", "⚡ <b>1. ПЕРВЫЕ 3 СЕКУНДЫ</b>")
    text = text.replace("### 📊 СТРУКТУРА", "📊 <b>2. СТРУКТУРА</b>")
    text = text.replace("### 🎵 ЗВУК", "🎵 <b>3. ЗВУК</b>")
    text = text.replace("### 📝 ТЕКСТ", "📝 <b>4. ТЕКСТ И СУБТИТРЫ</b>")
    text = text.replace("### 🏷 ХЕШТЕГИ", "🏷 <b>5. ХЕШТЕГИ</b>")
    text = text.replace("### 🔥 СЕКРЕТНЫЕ ФИШКИ", "🔥 <b>6. СЕКРЕТНЫЕ ФИШКИ</b>")
    text = text.replace("### ⭐ ВЕРДИКТ", "⭐ <b>ИТОГОВЫЙ ВЕРДИКТ</b>")
    
    # Убираем лишние ### и ##
    text = text.replace("###", "").replace("##", "")
    
    # Добавляем разделители между секциями
    sections = text.split('\n\n')
    result_sections = []
    
    for section in sections:
        if section.strip():
            result_sections.append(section.strip())
            # Добавляем разделитель после секций (кроме последней)
            if any(marker in section for marker in ['<b>1.', '<b>2.', '<b>3.', '<b>4.', '<b>5.', '<b>6.']):
                result_sections.append("\n━━━━━━━━━━━━━━━━━━━━\n")
    
    formatted += '\n\n'.join(result_sections)
    
    return formatted
