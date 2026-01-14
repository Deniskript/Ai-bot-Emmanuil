from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards.reply import photo_kb, bots_menu_kb
import aiohttp
import base64
import os
import json
import asyncio
import traceback
from PIL import Image
import io
from database import db
from loader import bot

router = Router()

PROXYAPI_KEY = os.getenv("OPENAI_API_KEY", "")
API_URL = "https://api.proxyapi.ru/openai/v1/images/generations"
EDIT_API_URL = "https://api.proxyapi.ru/openai/v1/images/edits"
# UPSCALE_API_URL удален - ProxyAPI не поддерживает отдельный upscale endpoint

# Важно: НЕ хранить ключи в коде/чате. Для VseGPT (в будущем) используем env: VSEGPT_API_KEY.
VSEGPT_API_KEY = os.getenv("VSEGPT_API_KEY", "")
VSEGPT_VIDEO_BASE_URL = os.getenv("VSEGPT_VIDEO_BASE_URL", "https://api.vsegpt.ru/v1/video")

# Дефолтные модели (используются если у пользователя нет настроек)
DEFAULT_MODELS = {
    "create": {"name": "📷 Создание", "model": "gpt-image-1-mini", "quality": "medium", "price": 8000, "time": "20-40 сек"},
    "upscale": {"name": "🎨 Улучшение качества", "model": "auto_max", "quality": "hd", "price": 33000, "time": "40-60 сек"},
    "edit": {"name": "✏️ Редактор", "model": "gpt-image-1.5", "quality": "medium", "price": 15000, "time": "30-50 сек"}
}

# Конфигурация моделей для API
MODEL_CONFIGS = {
    # Создание
    "gpt-image-1-mini": {"api_model": "gpt-image-1", "quality": "low", "size": "1024x1024"},
    "gpt-image-1": {"api_model": "gpt-image-1", "quality": "medium", "size": "1024x1024"},
    "gpt-image-1.5": {"api_model": "gpt-image-1", "quality": "high", "size": "1024x1024"},
    "gpt-image-1.5-hd": {"api_model": "gpt-image-1", "quality": "hd", "size": "1024x1024"},
    
    # Upscale - ТОЛЬКО поддерживаемые размеры ProxyAPI /edits endpoint
    "standard_1024": {"api_model": "gpt-image-1", "quality": "hd", "size": "1024x1024"},
    "wide_1536": {"api_model": "gpt-image-1", "quality": "hd", "size": "1536x1024"},
    "tall_1536": {"api_model": "gpt-image-1", "quality": "hd", "size": "1024x1536"},
    "auto_max": {"api_model": "gpt-image-1", "quality": "hd", "size": "auto"},
    
    # Редактирование
    # "gpt-image-1" уже определен выше
    # "gpt-image-1.5" уже определен выше
}

async def convert_to_png(image_bytes: bytes) -> bytes:
    """Конвертирует изображение в PNG формат с альфа-каналом (RGBA)"""
    image = Image.open(io.BytesIO(image_bytes))
    
    # Конвертируем в RGBA (с альфа-каналом) - API требует именно этот формат
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    # Сохраняем как PNG
    output = io.BytesIO()
    image.save(output, format='PNG')
    output.seek(0)
    return output.read()


async def get_user_model_settings(user_id: int, action: str) -> dict:
    """Получить настройки модели пользователя для конкретного действия"""
    from database.postgres_db import get_image_settings
    
    settings = await get_image_settings(user_id)
    
    model_key = settings.get(f"{action}_model", DEFAULT_MODELS[action]["model"])
    price = settings.get(f"{action}_price", DEFAULT_MODELS[action]["price"])
    config = MODEL_CONFIGS.get(model_key, MODEL_CONFIGS["gpt-image-1-mini"])
    
    return {
        "model": config["api_model"],
        "quality": config["quality"],
        "size": config["size"],
        "price": price,
        "name": DEFAULT_MODELS[action]["name"],
        "time": DEFAULT_MODELS[action]["time"],
        "model_key": model_key
    }

class ImageStates(StatesGroup):
    waiting_create_prompt = State()
    waiting_upscale_photo = State()
    waiting_for_photo_with_caption = State()  # Новое состояние: фото с подписью в одном сообщении
    waiting_video_confirm = State()
    waiting_video_text = State()
    waiting_video_photo = State()


@router.message(F.text.in_(["📷 Фото", "📸 Фото"]))
async def photo_menu(message: Message):
    """Показать меню фото"""
    tokens = await db.get_available_tokens(message.from_user.id)
    
    await message.answer(
        f"📷 <b>Генерация изображений</b>\n\n"
        f"💰 Баланс: <b>{tokens:,}</b> токенов\n\n"
        f"📷 <b>Создать</b> — создать фото по тексту\n"
        f"🎨 <b>4K Фото</b> — улучшить ваше фото до 4K\n"
        f"✏️ <b>Редактор</b> — изменить фото по команде\n"
        f"🎬 <b>Видео</b> — фото/текст → видео (настройки в ⚙️)\n"
        f"⚙️ <b>Настройки</b> — параметры на сайте",
        reply_markup=photo_kb(message.from_user.id),
        parse_mode="HTML"
    )


@router.message(F.web_app_data)
async def handle_images_webapp_data(message: Message, state: FSMContext):
    """
    Получаем данные из Telegram WebApp (images_settings.html) и запускаем нужную функцию в боте.
    Ожидаемый формат: {"type":"images_start","action":"create|upscale|edit", ...}
    """
    try:
        raw = message.web_app_data.data if message.web_app_data else ""
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {}

    if payload.get("type") != "images_start":
        return

    action = payload.get("action")
    if action == "create":
        await create_photo_start(message, state)
    elif action == "upscale":
        await upscale_photo_start(message, state)
    elif action == "edit":
        await editor_start(message, state)
    elif action == "video":
        # Запуск из веба — сразу в сценарий (без промежуточного подтверждения)
        await state.update_data(video_direct_start=True)
        await video_start(message, state)
    else:
        await message.answer("⚠️ Неизвестное действие. Откройте ⚙️ Настройки и попробуйте снова.", reply_markup=photo_kb(message.from_user.id))


def _default_video_settings() -> dict:
    # Дефолт: эконом, фото->видео, 16:9, 5 секунд
    return {
        "mode": "photo_to_video",   # photo_to_video | text_to_video | animate_photo
        "tier": "econom",           # econom | standard | premium
        "audio": False,
        "aspect_ratio": "16:9",
        "seconds": 5,
        "price": 12000
    }


def _resolve_vsegpt_video_model_id(video_settings: dict) -> str:
    """
    Выбираем model_id VseGPT по tier + mode + audio.
    model_id'ы из Docs/Models:
    - LTX: txt2vid-ltx/097-distilled, img2vid-ltx/097-distilled
    - Veo 3.1 Fast: txt2vid-google/..., img2vid-google/...
    - Sora 2: txt2vid-openai/sora-2-audio, txt2vid-openai/sora-2-audio-8s
    - Kling Pro Turbo 2.5: txt2vid-kling/pro25-turbo, img2vid-kling/pro25-turbo, img2vid-kling/pro25-turbo-10s
    """
    tier = (video_settings.get("tier") or "econom").lower()
    mode = (video_settings.get("mode") or "photo_to_video").lower()
    audio = bool(video_settings.get("audio", False))
    seconds = int(video_settings.get("seconds") or 5)

    if tier == "econom":
        # LTX
        if mode in ("text_to_video",):
            return "txt2vid-ltx/097-distilled"
        return "img2vid-ltx/097-distilled"

    if tier == "standard":
        # Veo 3.1 Fast
        if mode in ("text_to_video",):
            return "txt2vid-google/veo3.1-fast-with-audio" if audio else "txt2vid-google/veo3.1-fast-no-audio"
        return "img2vid-google/veo3.1-fast-with-audio" if audio else "img2vid-google/veo3.1-fast-no-audio"

    # premium
    if mode in ("text_to_video",):
        # Sora 2
        return "txt2vid-openai/sora-2-audio-8s" if seconds >= 8 else "txt2vid-openai/sora-2-audio"
    # Kling image-to-video
    return "img2vid-kling/pro25-turbo-10s" if seconds >= 10 else "img2vid-kling/pro25-turbo"


async def _get_user_video_settings(user_id: int) -> dict:
    from database.postgres_db import get_image_settings
    settings = await get_image_settings(user_id)
    extra = settings.get("extra_settings") or {}
    video = extra.get("video") if isinstance(extra, dict) else None
    if not isinstance(video, dict):
        return _default_video_settings()
    base = _default_video_settings()
    base.update(video)
    return base


async def _vsegpt_generate_video_and_wait(
    *,
    model_id: str,
    prompt: str,
    image_bytes,
    aspect_ratio: str,
    timeout_seconds: int = 20 * 60
) -> bytes:
    if not VSEGPT_API_KEY:
        raise Exception("VSEGPT_API_KEY не установлен в .env")

    headers_bearer = {"Authorization": f"Bearer {VSEGPT_API_KEY}", "Content-Type": "application/json"}
    headers_key = {"Authorization": f"Key {VSEGPT_API_KEY}", "Content-Type": "application/json"}

    payload: dict = {
        "model": model_id,
        "action": "generate",
        "prompt": prompt,
        "aspect_ratio": aspect_ratio
    }
    if image_bytes is not None:
        # VseGPT принимает data:image/jpeg;base64,...
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload["image_url"] = f"data:image/jpeg;base64,{b64}"

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
        async with session.post(f"{VSEGPT_VIDEO_BASE_URL}/generate", headers=headers_bearer, json=payload) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise Exception(f"VseGPT video generate error {resp.status}: {text[:300]}")
            data = json.loads(text) if text else {}

        request_id = data.get("request_id") or data.get("id")
        if not request_id:
            raise Exception(f"VseGPT: не получили request_id. Ответ: {text[:300]}")

        # Poll статус
        import time
        start = time.time()
        while time.time() - start < timeout_seconds:
            # По докам встречается и Bearer, и Key — пробуем оба
            sdata = None
            stext = ""
            for hdr in (headers_bearer, headers_key):
                async with session.get(f"{VSEGPT_VIDEO_BASE_URL}/status", headers=hdr, params={"request_id": request_id}) as sresp:
                    stext = await sresp.text()
                    if sresp.status == 200:
                        sdata = json.loads(stext) if stext else {}
                        break
            if sdata is None:
                await asyncio.sleep(5)
                continue

            status = (sdata.get("status") or "").upper()
            if status == "COMPLETED":
                url = sdata.get("url")
                if not url:
                    raise Exception(f"VseGPT: COMPLETED, но нет url. Ответ: {stext[:300]}")
                async with session.get(url) as vresp:
                    vbytes = await vresp.read()
                if not vbytes:
                    raise Exception("VseGPT: скачали пустое видео")
                return vbytes
            if status == "FAILED":
                raise Exception(f"VseGPT: генерация видео FAILED. Ответ: {stext[:300]}")

            await asyncio.sleep(5)

        raise Exception("VseGPT: таймаут ожидания видео")

def _video_settings_url(user_id: int) -> str:
    return f"https://soul-bot.ru/images/settings?user_id={user_id}"


def _video_menu_kb(user_id: int) -> ReplyKeyboardMarkup:
    # UX: когда пользователь нажал 🎬 Видео — сначала показать “Начать”/“Настройки”
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="▶️ Начать видео"), KeyboardButton(text="⚙️ Настройки", web_app=WebAppInfo(url=_video_settings_url(user_id)))],
            [KeyboardButton(text="🛑 Отменить"), KeyboardButton(text="◀️ Назад")],
        ],
        resize_keyboard=True
    )


async def _enter_video_flow(message: Message, state: FSMContext, video_settings: dict):
    cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True)
    mode = video_settings.get("mode", "photo_to_video")
    if mode == "text_to_video":
        await state.set_state(ImageStates.waiting_video_text)
        await message.answer("📝 Отправьте текст-описание для видео", reply_markup=cancel_kb)
    else:
        await state.set_state(ImageStates.waiting_video_photo)
        await message.answer("📸 Отправьте фото (можно с подписью: что должно происходить в видео)", reply_markup=cancel_kb)


@router.message(F.text == "🎬 Видео")
async def video_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    video_settings = await _get_user_video_settings(user_id)

    # Проверяем баланс
    tokens = await db.get_available_tokens(user_id)
    price = int(video_settings.get("price") or 0)
    if price > 0 and tokens < price:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        return

    mode = video_settings.get("mode", "photo_to_video")
    tier = video_settings.get("tier", "econom")
    audio = "да" if video_settings.get("audio") else "нет"
    aspect = video_settings.get("aspect_ratio", "16:9")
    seconds = video_settings.get("seconds", 5)
    price = int(video_settings.get("price") or 0)

    # Если пришли из веба с “Начать в боте” — стартуем сразу
    data = await state.get_data()
    if data.get("video_direct_start"):
        await state.update_data(video_direct_start=False)
        await message.answer(
            "🎬 <b>Видео</b>\n\n"
            f"Режим: <b>{mode}</b>\n"
            f"Уровень: <b>{tier}</b>\n"
            f"Аудио: <b>{audio}</b>\n"
            f"Формат: <b>{aspect}</b> • <b>{seconds}</b> сек\n"
            f"Стоимость: <b>{price:,}</b> токенов\n",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True),
            parse_mode="HTML"
        )
        await _enter_video_flow(message, state, video_settings)
        return

    await state.set_state(ImageStates.waiting_video_confirm)
    await message.answer(
        "🎬 <b>Видео</b>\n\n"
        f"Текущие настройки:\n"
        f"• Режим: <b>{mode}</b>\n"
        f"• Уровень: <b>{tier}</b>\n"
        f"• Аудио: <b>{audio}</b>\n"
        f"• Формат: <b>{aspect}</b> • <b>{seconds}</b> сек\n"
        f"• Стоимость: <b>{price:,}</b> токенов\n\n"
        "Нажмите <b>▶️ Начать видео</b> или измените настройки.",
        reply_markup=_video_menu_kb(user_id),
        parse_mode="HTML"
    )


@router.message(ImageStates.waiting_video_confirm, F.text == "▶️ Начать видео")
async def video_confirm_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    video_settings = await _get_user_video_settings(user_id)
    await _enter_video_flow(message, state, video_settings)


@router.message(ImageStates.waiting_video_text, F.text)
async def process_video_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    prompt = (message.text or "").strip()
    if len(prompt) < 3:
        await message.answer("⚠️ Слишком коротко. Опишите видео подробнее.")
        return

    video_settings = await _get_user_video_settings(user_id)
    price = int(video_settings.get("price") or 0)
    tokens = await db.get_available_tokens(user_id)
    if price > 0 and tokens < price:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        await state.clear()
        return

    status = await message.answer("🎬 Генерирую видео... Это может занять 1–6 минут.")

    try:
        model_id = _resolve_vsegpt_video_model_id(video_settings)
        aspect_ratio = video_settings.get("aspect_ratio") or "16:9"
        vbytes = await _vsegpt_generate_video_and_wait(
            model_id=model_id,
            prompt=prompt,
            image_bytes=None,
            aspect_ratio=aspect_ratio
        )

        await db.use_tokens_smart(user_id, price, bot_name="images") if price > 0 else None
        new_balance = await db.get_available_tokens(user_id)

        video_file = BufferedInputFile(vbytes, filename="video.mp4")
        await message.answer_video(
            video_file,
            caption=f"✅ <b>Видео готово!</b>\n\n💰 Списано: {price:,} токенов\n💳 Остаток: {new_balance:,}",
            reply_markup=photo_kb(user_id),
            parse_mode="HTML"
        )
        await status.delete()
    except Exception as e:
        traceback.print_exc()
        await status.edit_text(f"❌ Ошибка видео:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
    finally:
        await state.clear()


@router.message(ImageStates.waiting_video_photo, F.photo)
async def process_video_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    video_settings = await _get_user_video_settings(user_id)
    price = int(video_settings.get("price") or 0)

    tokens = await db.get_available_tokens(user_id)
    if price > 0 and tokens < price:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        await state.clear()
        return

    # caption -> подсказка, иначе общий промпт
    prompt = (message.caption or "").strip()
    if not prompt:
        mode = video_settings.get("mode", "photo_to_video")
        prompt = "Animate this image." if mode == "animate_photo" else "Generate a video based on this image."

    status = await message.answer("🎬 Генерирую видео... Это может занять 1–6 минут.")
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        photo_data = await bot.download_file(file.file_path)
        image_bytes = photo_data.read()

        model_id = _resolve_vsegpt_video_model_id(video_settings)
        aspect_ratio = video_settings.get("aspect_ratio") or "16:9"
        vbytes = await _vsegpt_generate_video_and_wait(
            model_id=model_id,
            prompt=prompt,
            image_bytes=image_bytes,
            aspect_ratio=aspect_ratio
        )

        await db.use_tokens_smart(user_id, price, bot_name="images") if price > 0 else None
        new_balance = await db.get_available_tokens(user_id)

        video_file = BufferedInputFile(vbytes, filename="video.mp4")
        await message.answer_video(
            video_file,
            caption=f"✅ <b>Видео готово!</b>\n\n💰 Списано: {price:,} токенов\n💳 Остаток: {new_balance:,}",
            reply_markup=photo_kb(user_id),
            parse_mode="HTML"
        )
        await status.delete()
    except Exception as e:
        traceback.print_exc()
        await status.edit_text(f"❌ Ошибка видео:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
    finally:
        await state.clear()


@router.message(F.text == "📷 Создать")
async def create_photo_start(message: Message, state: FSMContext):
    """Начать создание фото"""
    tokens = await db.get_available_tokens(message.from_user.id)
    
    model = await get_user_model_settings(message.from_user.id, 'create')
    if tokens < model['price']:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        return
    
    await state.set_state(ImageStates.waiting_create_prompt)
    
    # Кнопка отмены
    cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True)
    
    await message.answer(
        "📷 <b>Создание фото</b>\n\n"
        "Опишите что хотите увидеть:\n\n"
        f"<i>Пример: Космический кот в скафандре на Марсе, digital art</i>",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )


@router.message(F.text == "🎨 4K Фото")
async def upscale_photo_start(message: Message, state: FSMContext):
    """Начать upscale фото"""
    tokens = await db.get_available_tokens(message.from_user.id)
    
    model = await get_user_model_settings(message.from_user.id, 'upscale')
    if tokens < model['price']:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        return
    
    await state.set_state(ImageStates.waiting_upscale_photo)
    
    cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True)
    
    await message.answer(
        "🎨 <b>Улучшение фото до 4K</b>\n\n"
        "Отправьте фото которое хотите улучшить",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )


@router.message(F.text == "✏️ Редактор")
async def editor_start(message: Message, state: FSMContext):
    """Начать редактирование - фото с подписью в одном сообщении"""
    tokens = await db.get_available_tokens(message.from_user.id)
    
    model = await get_user_model_settings(message.from_user.id, 'edit')
    if tokens < model['price']:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        return
    
    await state.set_state(ImageStates.waiting_for_photo_with_caption)
    
    cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True)
    
    await message.answer(
        "✏️ <b>Редактор фото</b>\n\n"
        "📸 Отправьте фото <b>с подписью</b> — что нужно изменить.\n\n"
        "💡 <b>Как это сделать:</b>\n"
        "1. Выберите фото\n"
        "2. Перед отправкой напишите подпись\n"
        "3. Отправьте\n\n"
        "📝 <b>Примеры подписей:</b>\n"
        "• <code>добавь улыбку</code>\n"
        "• <code>надень солнечные очки</code>\n"
        "• <code>измени фон на пляж</code>\n"
        "• <code>убери текст с картинки</code>\n"
        "• <code>сделай вечернее освещение</code>\n\n"
        "✅ Пишите на русском — бот сам переведёт!",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )


@router.message(F.text == "🛑 Отменить")
async def cancel_operation(message: Message, state: FSMContext):
    """Отменить операцию"""
    await state.clear()
    await message.answer("❌ Операция отменена", reply_markup=photo_kb(message.from_user.id))


@router.message(F.text == "◀️ Назад")
async def back_from_photo(message: Message, state: FSMContext):
    """Возврат из меню фото"""
    await state.clear()
    # Просто меняем клавиатуру без сообщения
    await message.answer("🫧 Soul AI", reply_markup=bots_menu_kb())


# === СОЗДАНИЕ ФОТО ПО ТЕКСТУ ===
@router.message(ImageStates.waiting_create_prompt)
async def process_create(message: Message, state: FSMContext):
    """Создать фото по тексту"""
    if not message.text:
        return
    
    tokens = await db.get_available_tokens(message.from_user.id)
    model = await get_user_model_settings(message.from_user.id, 'create')
    
    if tokens < model['price']:
        await message.answer("❌ Недостаточно токенов!")
        await state.clear()
        return
    
    prompt = message.text
    
    status = await message.answer(
        f"🎨 <b>{model['name']}...</b>\n\n"
        f"⏱ ~{model['time']}\n"
        f"<i>Подождите...</i>",
        parse_mode="HTML"
    )
    
    try:
        headers = {"Authorization": f"Bearer {PROXYAPI_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": model['model'],
            "prompt": prompt,
            "size": model['size'],
            "quality": model['quality'],
            "n": 1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise Exception(f"API Error {resp.status}: {error}")
                
                result = await resp.json()
                
                if 'b64_json' in result.get('data', [{}])[0]:
                    image_data = base64.b64decode(result['data'][0]['b64_json'])
                elif 'url' in result.get('data', [{}])[0]:
                    image_url = result['data'][0]['url']
                    async with session.get(image_url) as img_resp:
                        image_data = await img_resp.read()
                else:
                    raise Exception("Unknown response format")
        
        photo = BufferedInputFile(image_data, filename="created.png")
        
        # Используем единую систему токенов (поддержка подписок)
        await db.use_tokens_smart(message.from_user.id, model['price'], bot_name='images')
        new_balance = await db.get_available_tokens(message.from_user.id)
        
        await status.delete()
        await message.answer_photo(
            photo,
            caption=f"✅ <b>Готово!</b>\n\n💰 Списано: {model['price']:,}\n💳 Остаток: {new_balance:,}",
            reply_markup=photo_kb(message.from_user.id),
            parse_mode="HTML"
        )
        
    except Exception as e:
        await status.edit_text(f"❌ Ошибка:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
    
    await state.clear()


# === UPSCALE 4K ===
@router.message(ImageStates.waiting_upscale_photo, F.photo)
async def process_upscale(message: Message, state: FSMContext):
    """Улучшить фото до 4K"""
    tokens = await db.get_available_tokens(message.from_user.id)
    model = await get_user_model_settings(message.from_user.id, 'upscale')
    
    if tokens < model['price']:
        await message.answer("❌ Недостаточно токенов!")
        await state.clear()
        return
    
    photo = message.photo[-1]
    
    status = await message.answer(
        f"🎨 <b>{model['name']}...</b>\n\n"
        f"⏱ ~{model['time']}\n"
        f"<i>Улучшаю качество фото...</i>",
        parse_mode="HTML"
    )
    
    try:
        # Скачиваем фото
        file = await bot.get_file(photo.file_id)
        file_path = file.file_path
        
        # Скачиваем изображение
        photo_data = await bot.download_file(file_path)
        # download_file возвращает BytesIO, read() - синхронный метод (не async!)
        image_bytes_raw = photo_data.read()
        
        # Конвертируем в PNG (ProxyAPI /edits принимает только PNG)
        image_bytes = await convert_to_png(image_bytes_raw)
        
        headers = {
            "Authorization": f"Bearer {PROXYAPI_KEY}"
        }
        
        async with aiohttp.ClientSession() as session:
            # ProxyAPI /edits поддерживает только: 1024x1024, 1536x1024, 1024x1536, auto
            # Все размеры из MODEL_CONFIGS теперь поддерживаются, проверка не нужна
            target_size = model['size']  # Уже содержит только поддерживаемые размеры: 1024x1024, 1536x1024, 1024x1536, auto
            
            # ВСЕГДА используем /edits endpoint для работы с существующими изображениями
            # /generations не поддерживает работу с существующими изображениями
            # ProxyAPI /edits принимает ТОЛЬКО PNG формат
            form_data = aiohttp.FormData()
            form_data.add_field('image', image_bytes, filename='photo.png', content_type='image/png')
            form_data.add_field('prompt', f'Upscale and enhance this image to maximum quality. Improve sharpness, clarity, details, and overall quality. Maintain the original composition and style.')
            form_data.add_field('n', '1')
            form_data.add_field('size', target_size)  # Используем размер из MODEL_CONFIGS (всегда поддерживается)
            
            headers_form = {"Authorization": f"Bearer {PROXYAPI_KEY}"}
            
            try:
                # Используем edits endpoint (единственный способ работать с существующими изображениями)
                async with session.post(EDIT_API_URL, headers=headers_form, data=form_data, timeout=aiohttp.ClientTimeout(total=180)) as edit_resp:
                    if edit_resp.status == 200:
                        result = await edit_resp.json()
                    else:
                        error_text = await edit_resp.text()
                        raise Exception(f"Edits API Error {edit_resp.status}: {error_text[:500]}")
            except Exception as e:
                # Если edits endpoint не работает, выбрасываем ошибку
                # /generations не может улучшить существующее изображение
                error_msg = str(e)
                print(f"❌ [Upscale Error] {error_msg}")
                traceback.print_exc()
                raise Exception(f"Не удалось улучшить изображение: {error_msg}")
            
            # Обрабатываем ответ
            if not result.get('data') or len(result.get('data', [])) == 0:
                raise Exception("Empty response from API")
            
            if 'b64_json' in result['data'][0]:
                image_data = base64.b64decode(result['data'][0]['b64_json'])
            elif 'url' in result['data'][0]:
                image_url = result['data'][0]['url']
                async with session.get(image_url) as img_resp:
                    image_data = await img_resp.read()
            else:
                raise Exception(f"Unknown response format: {result}")
        
        photo_result = BufferedInputFile(image_data, filename="upscaled.png")
        
        # Списываем токены
        await db.use_tokens_smart(message.from_user.id, model['price'], bot_name='images')
        new_balance = await db.get_available_tokens(message.from_user.id)
        
        await status.delete()
        await message.answer_photo(
            photo_result,
            caption=f"✅ <b>Фото улучшено до 4K!</b>\n\n💰 Списано: {model['price']:,}\n💳 Остаток: {new_balance:,}",
            reply_markup=photo_kb(message.from_user.id),
            parse_mode="HTML"
        )
        
    except Exception as e:
        error_msg = str(e)[:300]
        print(f"❌ [Upscale Error] {error_msg}")
        traceback.print_exc()
        await status.edit_text(f"❌ Ошибка улучшения фото:\n<code>{error_msg}</code>", parse_mode="HTML")
    
    await state.clear()


# === РЕДАКТОР ===
@router.message(ImageStates.waiting_for_photo_with_caption, F.photo, ~F.caption)
async def photo_without_caption(message: Message, state: FSMContext):
    """Пользователь отправил фото БЕЗ подписи"""
    await message.answer(
        "⚠️ <b>Вы отправили фото без подписи!</b>\n\n"
        "Я не знаю что нужно изменить на фото 🤔\n\n"
        "📝 <b>Попробуйте ещё раз:</b>\n"
        "1. Нажмите 📎 (скрепка)\n"
        "2. Выберите фото\n"
        "3. <b>Напишите подпись</b> перед отправкой\n"
        "   Например: <code>add smile</code>\n"
        "4. Отправьте\n\n"
        "💡 Подпись пишется в поле под фото перед отправкой!",
        parse_mode="HTML"
    )


@router.message(ImageStates.waiting_for_photo_with_caption, F.text, ~F.photo)
async def text_without_photo(message: Message, state: FSMContext):
    """Пользователь отправил текст вместо фото"""
    # Проверяем команду отмены
    if message.text.lower() in ['/cancel', 'отмена', 'cancel', '🛑 отменить']:
        await state.clear()
        await message.answer("❌ Редактирование отменено")
        return
    
    await message.answer(
        "⚠️ <b>Вы отправили только текст!</b>\n\n"
        "Мне нужно фото для редактирования 📸\n\n"
        "📝 <b>Как отправить правильно:</b>\n"
        "1. Нажмите 📎 (скрепка) → Фото\n"
        "2. Выберите фото из галереи\n"
        "3. Напишите подпись: <code>" + message.text[:30] + "</code>\n"
        "4. Отправьте\n\n"
        "💡 Фото и подпись должны быть в <b>одном сообщении</b>!",
        parse_mode="HTML"
    )


@router.message(ImageStates.waiting_for_photo_with_caption, F.photo, F.caption)
async def process_photo_with_caption(message: Message, state: FSMContext):
    """Обработка фото с подписью для редактирования"""
    edit_command = message.caption.strip()
    user_id = message.from_user.id
    
    # Проверка на слишком короткую команду
    if len(edit_command) < 3:
        await message.answer(
            "⚠️ <b>Слишком короткая подпись!</b>\n\n"
            "Опишите подробнее что нужно изменить.\n"
            "Например: <code>add a red hat</code>",
            parse_mode="HTML"
        )
        return
    
    print(f"=" * 60)
    print(f"📝 РЕДАКТОР: Фото с подписью")
    print(f"📝 User: {user_id}")
    print(f"📝 Команда: {edit_command}")
    print(f"=" * 60)
    
    # Получаем настройки модели
    model = await get_user_model_settings(user_id, 'edit')
    
    # Проверяем баланс
    tokens = await db.get_available_tokens(user_id)
    if tokens < model['price']:
        await message.answer(
            f"❌ <b>Недостаточно токенов</b>\n\n"
            f"💰 Нужно: {model['price']:,} токенов\n"
            f"👛 У вас: {tokens:,} токенов\n\n"
            f"Пополните баланс в разделе 💎 Токены",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    status_msg = await message.answer(
        "✏️ <b>Редактирую фото...</b>\n\n"
        f"📝 Команда: <i>{edit_command}</i>\n"
        "⏱ Подождите 30-60 секунд",
        parse_mode="HTML"
    )
    
    try:
        # Скачиваем фото из сообщения
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        photo_data = await bot.download_file(file.file_path)
        image_bytes_raw = photo_data.read()
        
        print(f"📝 Фото: {len(image_bytes_raw)} байт")
        
        # Конвертируем в PNG RGBA
        image_bytes = await convert_to_png(image_bytes_raw)
        
        # Переводим промпт на английский если нужно
        has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in edit_command)
        
        if has_cyrillic:
            try:
                from deep_translator import GoogleTranslator
                translated_prompt = GoogleTranslator(source='ru', target='en').translate(edit_command)
                print(f"🔍 [DEBUG] Переведено: '{edit_command}' → '{translated_prompt}'")
                english_prompt = f"Edit this image: {translated_prompt}. Follow the instruction precisely."
            except ImportError:
                simple_translations = {
                    'улыбка': 'smile', 'улыбнуться': 'smile', 'улыбнулся': 'smiling',
                    'фон': 'background', 'задний фон': 'background',
                    'море': 'sea', 'океан': 'ocean',
                    'ночь': 'night', 'ночной': 'night',
                    'добавь': 'add', 'добавить': 'add',
                    'убери': 'remove', 'удалить': 'remove',
                    'сделай': 'make', 'сделать': 'make',
                    'человек': 'person', 'человека': 'person',
                    'на фото': 'in the photo', 'на изображении': 'in the image'
                }
                translated_prompt = edit_command.lower()
                for ru, en in simple_translations.items():
                    translated_prompt = translated_prompt.replace(ru, en)
                
                if translated_prompt == edit_command.lower():
                    english_prompt = f"Edit this image according to the user's request: {edit_command}. Make the requested changes precisely."
                else:
                    english_prompt = f"Edit this image: {translated_prompt}. Follow the instruction precisely."
                print(f"🔍 [DEBUG] Простой перевод: '{edit_command}' → '{english_prompt}'")
            except Exception as e:
                print(f"⚠️ [WARNING] Ошибка перевода: {e}. Используем общий промпт.")
                english_prompt = f"Edit this image according to the user's request: {edit_command}. Make the requested changes precisely."
        else:
            english_prompt = f"Edit this image: {edit_command}. Follow the instruction precisely."
        
        # API запрос
        headers = {"Authorization": f"Bearer {PROXYAPI_KEY}"}
        
        print(f"📝 API: {EDIT_API_URL}")
        print(f"📝 Prompt: {english_prompt}")
        
        async with aiohttp.ClientSession() as session:
            form_data = aiohttp.FormData()
            form_data.add_field('image', image_bytes, filename='photo.png', content_type='image/png')
            form_data.add_field('prompt', english_prompt)
            form_data.add_field('model', model['model'])
            form_data.add_field('n', '1')
            form_data.add_field('size', model['size'])
            
            async with session.post(EDIT_API_URL, headers=headers, data=form_data, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                response_text = await resp.text()
                print(f"📝 Status: {resp.status}")
                print(f"📝 Response (FULL): {response_text}")
                print(f"=" * 60)
                
                if resp.status != 200:
                    error_msg = response_text[:200]
                    raise Exception(f"API Error: {error_msg}")
                
                result = json.loads(response_text)
                print(f"📝 Parsed result keys: {list(result.keys())}")
                print(f"📝 Result has 'data': {'data' in result}")
                if 'data' in result:
                    print(f"📝 Data length: {len(result['data'])}")
                    if len(result['data']) > 0:
                        print(f"📝 First item keys: {list(result['data'][0].keys())}")
                
                if 'data' in result and len(result['data']) > 0:
                    image_data = result['data'][0]
                    
                    print(f"📝 Image data keys: {list(image_data.keys())}")
                    
                    if 'b64_json' in image_data:
                        print(f"📝 Using b64_json (size: {len(image_data['b64_json'])} chars)")
                        img_bytes = base64.b64decode(image_data['b64_json'])
                    elif 'url' in image_data:
                        print(f"📝 Downloading from URL: {image_data['url'][:100]}...")
                        async with session.get(image_data['url']) as img_resp:
                            img_bytes = await img_resp.read()
                            print(f"📝 Downloaded image size: {len(img_bytes)} bytes")
                    else:
                        raise Exception(f"Нет изображения в ответе. Keys: {list(image_data.keys())}")
                    
                    # Отправляем результат
                    result_photo = BufferedInputFile(img_bytes, filename="edited.png")
                    
                    # Списываем токены
                    await db.use_tokens_smart(user_id, model['price'], bot_name='images')
                    new_balance = await db.get_available_tokens(user_id)
                    
                    await message.answer_photo(
                        result_photo,
                        caption=f"✅ <b>Готово!</b>\n\n"
                                f"📝 Команда: <i>{edit_command}</i>\n"
                                f"💰 Списано: {model['price']:,} токенов\n"
                                f"💳 Остаток: {new_balance:,}",
                        reply_markup=photo_kb(user_id),
                        parse_mode="HTML"
                    )
                    
                    await status_msg.delete()
                else:
                    raise Exception("Пустой ответ от API")
                    
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        traceback.print_exc()
        
        await status_msg.edit_text(
            f"❌ <b>Ошибка редактирования</b>\n\n"
            f"<code>{str(e)[:150]}</code>\n\n"
            f"💡 Попробуйте другую команду или фото",
            parse_mode="HTML"
        )
    
    await state.clear()


@router.message(ImageStates.waiting_for_photo_with_caption)
async def wrong_content_type(message: Message, state: FSMContext):
    """Пользователь отправил что-то другое"""
    await message.answer(
        "🤔 <b>Не понимаю...</b>\n\n"
        "Отправьте <b>фото с подписью</b> для редактирования.\n\n"
        "❌ Для отмены: /cancel",
        parse_mode="HTML"
    )
