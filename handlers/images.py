from aiogram import Router, F
from aiogram.types import (
    Message,
    BufferedInputFile,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards.reply import photo_kb, bots_menu_kb
import aiohttp
import base64
import os
import json
import asyncio
import traceback
from PIL import Image, ImageDraw, ImageFont
import io
from database import db
from database.db import get_available_tokens as get_available_tokens_web, use_tokens_smart as use_tokens_smart_web
from utils.status_manager import show_status
from loader import bot

router = Router()

# VseGPT
VSEGPT_API_KEY = os.getenv("VSEGPT_API_KEY", "")
VSEGPT_VIDEO_BASE_URL = os.getenv("VSEGPT_VIDEO_BASE_URL", "https://api.vsegpt.ru/v1/video")
VSEGPT_BASE_URL = os.getenv("VSEGPT_BASE_URL", "https://api.vsegpt.ru/v1")
VSEGPT_IMAGES_URL = f"{VSEGPT_BASE_URL}/images/generations"

# Дефолтные модели (используются если у пользователя нет настроек)
DEFAULT_MODELS = {
    # Create (text->image)
    "create": {"name": "📷 Создание", "model": "img-flux/schnell", "price": 3600, "time": "15-40 сек"},
    # Upscale (img->img)
    "upscale": {"name": "🎨 Улучшение качества", "model": "img2img-recraft/v3-upscale-crisp", "price": 1600, "time": "20-60 сек"},
    # Edit (img->img)
    "edit": {"name": "✏️ Редактор", "model": "img2img-flux/kontext-pro-edit", "price": 15000, "time": "20-60 сек"},
}

# Legacy mappings: старые значения в БД -> новые VseGPT model_id
LEGACY_MODEL_MAP = {
    "create": {
        "gpt-image-1-mini": "img-flux/schnell",
        "gpt-image-1": "img-flux/flux-2",
        "gpt-image-1.5": "img-flux/kontext-pro",
        "gpt-image-1.5-hd": "img-flux/kontext-max",
    },
    "edit": {
        "gpt-image-1": "img2img-flux/kontext-pro-edit",
        "gpt-image-1.5": "img2img-flux/kontext-max-edit",
    },
    "upscale": {
        "standard_1024": "img2img-recraft/v3-upscale-crisp",
        "wide_1536": "img2img-recraft/v3-upscale-crisp",
        "tall_1536": "img2img-recraft/v3-upscale-crisp",
        "auto_max": "img2img-recraft/v3-upscale-crisp",
    },
}

def _convert_to_jpeg(image_bytes: bytes) -> bytes:
    """VseGPT img2img обычно принимает data:image/jpeg;base64,..."""
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode not in ("RGB",):
        image = image.convert("RGB")
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=95, optimize=True)
    out.seek(0)
    return out.read()


def _resize_to_exact(image_bytes: bytes, size: str) -> bytes:
    """Center-crop to aspect ratio, then resize to exact WxH."""
    try:
        w, h = size.lower().split("x")
        target_w, target_h = int(w), int(h)
    except Exception:
        return image_bytes

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        # too wide -> crop width
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, src_h))
    else:
        # too tall -> crop height
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        img = img.crop((0, top, src_w, top + new_h))

    img = img.resize((target_w, target_h), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out.read()


def _resolve_blogger_model(model_key: str) -> str | None:
    """Web key -> VseGPT model_id."""
    key = (model_key or "").strip().lower()
    if key in ("flux-1.1", "flux-1_1", "flux1.1"):
        return "img-flux/schnell"
    if key in ("flux-pro", "fluxpro", "flux_pro"):
        return "img-flux/flux-2"
    if key in ("flux-max", "fluxmax", "flux_max"):
        return "img-flux/kontext-max"
    if key in ("midjourney", "mj"):
        # В VseGPT API "Midjourney" недоступен как image model_id — используем лучший доступный аналог.
        return "img-flux/kontext-max"
    # allow passing raw VseGPT model_id
    return model_key


def _pretty_cover_platform(platform: str) -> str:
    p = (platform or "").strip().lower()
    return {
        "instagram_post": "Instagram Пост",
        "instagram_story": "Instagram Сторис",
        "youtube": "YouTube",
        "telegram": "Telegram",
    }.get(p, platform or "—")


def _pretty_logo_style(style: str) -> str:
    s = (style or "").strip().lower()
    return {"text": "Текст", "icon": "Иконка", "combo": "Комбо"}.get(s, style or "—")


def _pretty_logo_color(color: str) -> str:
    c = (color or "").strip().lower()
    return {"blue": "Синий", "red": "Красный", "green": "Зелёный", "yellow": "Жёлтый", "black": "Ч/Б"}.get(c, color or "—")


async def _get_user_blogger_settings(user_id: int) -> dict:
    """Настройки блогера из extra_settings.blogger (cover/logo/presentation)."""
    from database.postgres_db import get_image_settings
    settings = await get_image_settings(user_id)
    extra = settings.get("extra_settings") or {}
    blogger = extra.get("blogger") if isinstance(extra, dict) else None
    return blogger if isinstance(blogger, dict) else {}


async def _get_user_creative_settings(user_id: int) -> dict:
    """Настройки креатива из extra_settings.creative."""
    from database.postgres_db import get_image_settings
    settings = await get_image_settings(user_id)
    extra = settings.get("extra_settings") or {}
    creative = extra.get("creative") if isinstance(extra, dict) else None
    return creative if isinstance(creative, dict) else {}


def _resolve_creative_model(subtype: str, tier: str) -> str:
    """Tier from WebApp -> VseGPT model_id."""
    subtype = (subtype or "").lower()
    tier = (tier or "standard").lower()

    # meme is text2img; style/effect are img2img
    if subtype == "meme":
        if tier in ("econom", "economy", "mini"):
            return "img-flux/schnell"
        if tier in ("standard", "pro", "flux-1.1"):
            return "img-flux/flux-2"
        return "img-flux/kontext-max"

    # style/effect
    if tier in ("econom", "economy", "mini"):
        return "img2img-google/flash-edit"
    if tier in ("standard", "pro", "flux-1.1"):
        return "img2img-flux/kontext-pro-edit"
    return "img2img-flux/kontext-max-edit"


def _overlay_meme_text(image_bytes: bytes, top: str, bottom: str) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size
    draw = ImageDraw.Draw(img)
    pad = int(h * 0.06)
    font_size = int(h * 0.09)
    font = _load_font(max(18, font_size))
    stroke = max(2, int(h * 0.004))

    def draw_centered(text: str, y: int):
        if not text:
            return
        max_w = int(w * 0.92)
        lines = _wrap_text(draw, text.upper(), font, max_w)
        line_h = int(font.size * 1.10) if hasattr(font, "size") else int(font_size * 1.10)
        total_h = len(lines) * line_h
        cy = y - total_h // 2
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            lw = bbox[2] - bbox[0]
            x = (w - lw) // 2
            draw.text((x, cy), line, font=font, fill=(255, 255, 255, 255),
                      stroke_width=stroke, stroke_fill=(0, 0, 0, 200))
            cy += line_h

    draw_centered(top.strip(), pad + int(font.size * 0.8))
    draw_centered(bottom.strip(), h - pad - int(font.size * 0.8))

    out = io.BytesIO()
    img.convert("RGB").save(out, format="PNG")
    out.seek(0)
    return out.read()


# --- Meme templates (local-by-URL with caching) ---
_MEME_TEMPLATE_URLS: dict[str, str] = {
    # imgflip stable CDN-ish links
    "doge": "https://i.imgflip.com/4t0m5.jpg",
    "grumpy_cat": "https://i.imgflip.com/8p0a.jpg",
    "hide_pain": "https://i.imgflip.com/gk5el.jpg",
    "think": "https://i.imgflip.com/1otk96.jpg",
}
_MEME_TEMPLATE_CACHE: dict[str, bytes] = {}


async def _fetch_bytes(url: str) -> bytes:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Template download failed {resp.status}")
            return await resp.read()


async def _get_meme_template_image(template_key: str) -> bytes:
    key = (template_key or "doge").strip().lower()
    if key in _MEME_TEMPLATE_CACHE:
        return _MEME_TEMPLATE_CACHE[key]
    url = _MEME_TEMPLATE_URLS.get(key) or _MEME_TEMPLATE_URLS["doge"]
    b = await _fetch_bytes(url)
    # normalize to PNG
    img = Image.open(io.BytesIO(b)).convert("RGB")
    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    res = out.read()
    _MEME_TEMPLATE_CACHE[key] = res
    return res


def _parse_meme_top_bottom(text: str) -> tuple[str, str]:
    t = (text or "").strip()
    if not t:
        return "", ""
    lines = [x.strip() for x in t.splitlines() if x.strip()]
    top = ""
    bottom = ""
    for ln in lines:
        low = ln.lower()
        if low.startswith("верх"):
            top = ln.split(":", 1)[1].strip() if ":" in ln else ln[4:].strip()
        elif low.startswith("низ"):
            bottom = ln.split(":", 1)[1].strip() if ":" in ln else ln[3:].strip()
    if top or bottom:
        return top, bottom
    # fallback: first line top, second line bottom
    top = lines[0] if lines else ""
    bottom = lines[1] if len(lines) > 1 else ""
    return top, bottom


async def creative_start(message: Message, state: FSMContext, user_id: int | None = None):
    user_id = user_id or message.from_user.id
    data = await state.get_data()

    # If started via "again" without payload — load saved settings
    if not data.get("creative_subtype"):
        saved = await _get_user_creative_settings(user_id)
        last = (saved.get("last_subtype") or "style").strip().lower()
        if last == "style":
            s = saved.get("style") if isinstance(saved.get("style"), dict) else {}
            await state.update_data(
                creative_subtype="style",
                creative_style=s.get("style", "anime"),
                creative_custom_text=s.get("custom_text"),
                creative_model=s.get("model", "standard"),
                creative_price=s.get("price", 15000),
            )
        elif last == "meme":
            s = saved.get("meme") if isinstance(saved.get("meme"), dict) else {}
            await state.update_data(
                creative_subtype="meme",
                creative_meme_mode=s.get("mode", "create"),
                creative_meme_template=s.get("template", "doge"),
                creative_meme_top=s.get("text_top"),
                creative_meme_bottom=s.get("text_bottom"),
                creative_model=s.get("model", "econom"),
                creative_price=s.get("price", 15000),
            )
        else:
            s = saved.get("effect") if isinstance(saved.get("effect"), dict) else {}
            await state.update_data(
                creative_subtype="effect",
                creative_effect=s.get("effect", "fire"),
                creative_model=s.get("model", "standard"),
                creative_price=s.get("price", 15000),
            )
        data = await state.get_data()

    subtype = (data.get("creative_subtype") or "style").strip().lower()
    price = int(data.get("creative_price") or 0)

    tokens = await get_available_tokens_web(user_id)
    if price > 0 and tokens < price:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        await state.clear()
        return

    if subtype == "meme":
        mode = (data.get("creative_meme_mode") or "create").strip().lower()
        if mode == "template":
            # if texts already provided from WebApp, generate immediately
            if (data.get("creative_meme_top") or data.get("creative_meme_bottom")):
                await creative_generate_meme(message, state, user_id=user_id)
                return
            await state.set_state(ImageStates.waiting_creative_meme_idea)
            await message.answer(
                "<b>😂 Мем (шаблон)</b>\n\n"
                f"<b>Стоимость:</b> {_fmt_tokens(price)} токенов\n\n"
                "📝 Напишите текст для мема:\n"
                "Верх: ...\n"
                "Низ: ...\n\n"
                "<i>Текст будет без ошибок (рисуется ботом).</i>",
                reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True),
                parse_mode="HTML",
            )
            return
        await state.set_state(ImageStates.waiting_creative_meme_idea)
        await message.answer(
            "<b>😂 Мем</b>\n\n"
            f"<b>Стоимость:</b> {_fmt_tokens(price)} токенов\n\n"
            "📝 Напишите идею мема (1–2 предложения).\n"
            "<i>Текст на картинке будет без ошибок (рисуется ботом).</i>",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True),
            parse_mode="HTML",
        )
        return

    # style/effect need a photo
    await state.set_state(ImageStates.waiting_creative_photo)
    if subtype == "style":
        style = (data.get("creative_style") or "anime").strip().lower()
        custom = (data.get("creative_custom_text") or "").strip()
        style_h = {
            "anime": "🎌 Аниме",
            "oil": "🖼 Масло",
            "pixel": "👾 Пиксель",
            "3d": "🎮 3D",
            "neon": "✨ Неон",
            "retro": "🌅 Ретро",
        }.get(style, style)
        extra = f"\n<b>Свой стиль:</b> {custom}" if custom else ""
        await message.answer(
            "<b>🎨 Стиль</b>\n\n"
            f"<b>Выбрано:</b> {style_h}{extra}\n"
            f"<b>Стоимость:</b> {_fmt_tokens(price)} токенов\n\n"
            "📸 Отправьте фото, к которому применить стиль.",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True),
            parse_mode="HTML",
        )
        return

    effect = (data.get("creative_effect") or "fire").strip().lower()
    effect_h = {
        "fire": "🔥 Огонь",
        "lightning": "⚡ Молния",
        "magic": "💫 Магия",
        "water": "🌊 Вода",
        "ice": "❄️ Лёд",
        "fireworks": "🎆 Фейерверк",
        "ghost": "👻 Призрак",
        "rainbow": "🌈 Радуга",
    }.get(effect, effect)
    await message.answer(
        "<b>🎪 Эффект</b>\n\n"
        f"<b>Выбрано:</b> {effect_h}\n"
        f"<b>Стоимость:</b> {_fmt_tokens(price)} токенов\n\n"
        "📸 Отправьте фото — добавлю эффект аккуратно.",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True),
        parse_mode="HTML",
    )


async def creative_generate_meme(message: Message, state: FSMContext, *, user_id: int):
    data = await state.get_data()
    price = int(data.get("creative_price") or 0)
    tier = data.get("creative_model") or "econom"
    model_id = _resolve_creative_model("meme", str(tier))

    mode = (data.get("creative_meme_mode") or "create").strip().lower()
    template = (data.get("creative_meme_template") or "doge").strip().lower()
    top = (data.get("creative_meme_top") or "").strip()
    bottom = (data.get("creative_meme_bottom") or "").strip()
    idea = (data.get("creative_meme_idea") or "").strip()

    tokens = await get_available_tokens_web(user_id)
    if price > 0 and tokens < price:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        await state.clear()
        return

    status = await show_status(bot, message.chat.id, "generate")
    try:
        if mode == "template":
            img_bytes = await _get_meme_template_image(template)
        else:
            prompt_en = await _to_english(idea)
            prompt = (
                f"Create a funny meme image for this idea: {prompt_en}. "
                "Leave empty space at top and bottom for captions. "
                "No text, no watermark."
            )
            img_bytes = await _vsegpt_images_generate(model_id=model_id, prompt=prompt, image_bytes=None)
        if top or bottom:
            img_bytes = _overlay_meme_text(img_bytes, top, bottom)

        if price > 0:
            await use_tokens_smart_web(user_id, price, bot_name="images")
        new_balance = await get_available_tokens_web(user_id)

        await message.answer_photo(
            BufferedInputFile(img_bytes, filename="meme.png"),
            caption=f"✅ <b>Готово!</b>\n\n💰 Списано: {_fmt_tokens(price)} токенов\n💳 Остаток: {_fmt_tokens(new_balance)} токенов",
            reply_markup=_done_inline_kb("creative"),
            parse_mode="HTML",
        )
        await message.answer(
            "✨ <b>Готово!</b> Что делаем дальше?",
            reply_markup=_flow_done_kb("creative"),
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
    finally:
        if status:
            await status.stop()
        await state.clear()


async def creative_meme_idea(message: Message, state: FSMContext):
    """impl; decorator is defined below after ImageStates."""
    text = (message.text or "").strip()
    data = await state.get_data()
    mode = (data.get("creative_meme_mode") or "create").strip().lower()
    if mode == "template":
        top, bottom = _parse_meme_top_bottom(text)
        if not (top or bottom):
            await message.answer("⚠️ Добавьте текст. Например:\nВерх: ...\nНиз: ...")
            return
        await state.update_data(creative_meme_top=top, creative_meme_bottom=bottom, creative_meme_idea="")
        await creative_generate_meme(message, state, user_id=message.from_user.id)
        return
    if len(text) < 3:
        await message.answer("⚠️ Слишком коротко. Опишите идею подробнее.")
        return
    await state.update_data(creative_meme_idea=text, creative_meme_top="", creative_meme_bottom="")
    await creative_generate_meme(message, state, user_id=message.from_user.id)


async def creative_process_photo(message: Message, state: FSMContext):
    """impl; decorator is defined below after ImageStates."""
    user_id = message.from_user.id
    data = await state.get_data()
    subtype = (data.get("creative_subtype") or "").strip().lower()
    price = int(data.get("creative_price") or 0)
    tier = data.get("creative_model") or "standard"
    model_id = _resolve_creative_model(subtype, str(tier))

    tokens = await get_available_tokens_web(user_id)
    if price > 0 and tokens < price:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        await state.clear()
        return

    # download photo
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    bio = io.BytesIO()
    await bot.download_file(file.file_path, bio)
    jpeg_bytes = _convert_to_jpeg(bio.getvalue())

    status = await show_status(bot, message.chat.id, "generate")
    try:
        if subtype == "style":
            style = (data.get("creative_style") or "anime").strip().lower()
            custom = (data.get("creative_custom_text") or "").strip()
            preset = {
                "anime": "Transform the photo into high-quality japanese anime style.",
                "oil": "Transform the photo into an oil painting with visible brush strokes.",
                "pixel": "Transform the photo into pixel art (8-bit), keep the subject recognizable.",
                "3d": "Transform the photo into a clean 3D render style.",
                "neon": "Add neon lighting and glowing accents, cyberpunk mood.",
                "retro": "Make it retro film look, vintage colors and grain.",
            }.get(style, f"Transform the photo into {style} style.")
            if custom:
                preset = f"Transform the photo into this style: {await _to_english(custom)}."
            prompt = (
                f"{preset} Preserve the person's identity, face, age, and key features. "
                "No text, no watermark."
            )
        else:
            effect = (data.get("creative_effect") or "fire").strip().lower()
            preset = {
                "fire": "Add realistic fire/flames effects around the subject, safe and natural.",
                "lightning": "Add dramatic lightning/electric arcs in the scene.",
                "magic": "Add magical glow/aura and particles around the subject.",
                "water": "Add realistic water splashes and wet reflections.",
                "ice": "Add ice/frost crystals and cold mist effects.",
                "fireworks": "Add fireworks/sparks in the background.",
                "ghost": "Add ghostly mist and translucent silhouettes, subtle.",
                "rainbow": "Add soft rainbow light beams and gradients.",
            }.get(effect, f"Add {effect} visual effect.")
            prompt = (
                f"{preset} Preserve the person's identity, face, age, and key features. "
                "No text, no watermark."
            )

        out_bytes = await _vsegpt_images_generate(model_id=model_id, prompt=prompt, image_bytes=jpeg_bytes)

        if price > 0:
            await use_tokens_smart_web(user_id, price, bot_name="images")
        new_balance = await get_available_tokens_web(user_id)

        await message.answer_photo(
            BufferedInputFile(out_bytes, filename="creative.png"),
            caption=f"✅ <b>Готово!</b>\n\n💰 Списано: {_fmt_tokens(price)} токенов\n💳 Остаток: {_fmt_tokens(new_balance)} токенов",
            reply_markup=_done_inline_kb("creative"),
            parse_mode="HTML",
        )
        await message.answer(
            "✨ <b>Готово!</b> Что делаем дальше?",
            reply_markup=_flow_done_kb("creative"),
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
    finally:
        if status:
            await status.stop()
        await state.clear()


def _load_font(size: int) -> ImageFont.ImageFont:
    # Prefer DejaVu (usually present on Ubuntu)
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = (text or "").replace("\r", "").split()
    if not words:
        return []
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        test = (" ".join(cur + [w])).strip()
        if not test:
            continue
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] <= max_width or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def _overlay_text_on_image(image_bytes: bytes, text: str, *, layout: str = "presentation") -> bytes:
    """
    Накладываем текст поверх изображения программно (без ошибок в тексте).
    layout: presentation | cover
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    pad = int(min(w, h) * 0.06)
    box_w = int(w * 0.86)
    box_h = int(h * (0.52 if layout == "presentation" else 0.42))
    x0 = pad
    y0 = pad if layout == "presentation" else int(h * 0.56)
    x1, y1 = x0 + box_w, y0 + box_h

    # background for readability
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([x0, y0, x1, y1], radius=24, fill=(0, 0, 0, 110))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    raw = (text or "").strip()
    # make nicer multiline for numbered lists
    if "\n" not in raw and any(s in raw for s in ("1.", "2.", "3.", "4.", "5.")):
        raw = raw.replace(". ", ".\n")

    # split title/body
    parts = [p.strip() for p in raw.split("\n") if p.strip()]
    title = parts[0] if parts else raw
    body = "\n".join(parts[1:]) if len(parts) > 1 else ""

    title_size = int(h * 0.055)
    body_size = int(h * 0.034)

    # Fit fonts if too big
    for _ in range(18):
        title_font = _load_font(max(14, title_size))
        body_font = _load_font(max(12, body_size))
        # measure wrapped lines
        max_line_w = box_w - 2 * pad
        t_lines = _wrap_text(draw, title, title_font, max_line_w)
        b_lines: list[str] = []
        if body:
            for line in body.split("\n"):
                b_lines.extend(_wrap_text(draw, line, body_font, max_line_w))
        # height estimate
        lh_t = int(title_font.size * 1.15) if hasattr(title_font, "size") else int(title_size * 1.15)
        lh_b = int(body_font.size * 1.25) if hasattr(body_font, "size") else int(body_size * 1.25)
        total_h = len(t_lines) * lh_t + (lh_b * max(0, len(b_lines))) + int(pad * 0.8)
        if total_h <= box_h - pad:
            break
        title_size = int(title_size * 0.92)
        body_size = int(body_size * 0.92)

    cx, cy = x0 + pad, y0 + pad
    stroke = max(2, int(h * 0.003))

    for line in t_lines:
        draw.text((cx, cy), line, font=title_font, fill=(255, 255, 255, 255),
                  stroke_width=stroke, stroke_fill=(0, 0, 0, 140))
        cy += int(title_font.size * 1.15) if hasattr(title_font, "size") else int(title_size * 1.15)

    if body:
        cy += int(pad * 0.4)
        for line in b_lines:
            draw.text((cx, cy), line, font=body_font, fill=(255, 255, 255, 230),
                      stroke_width=max(1, stroke - 1), stroke_fill=(0, 0, 0, 120))
            cy += int(body_font.size * 1.25) if hasattr(body_font, "size") else int(body_size * 1.25)

    out = io.BytesIO()
    img.convert("RGB").save(out, format="PNG")
    out.seek(0)
    return out.read()


async def blogger_start(message: Message, state: FSMContext, user_id: int | None = None):
    """Старт сценариев для блогеров: обложки/логотипы/презентации."""
    user_id = user_id or message.from_user.id
    data = await state.get_data()
    # если пользователь нажал "Ещё дизайн" без WebApp payload — берём сохранённые настройки
    if not data.get("blogger_subtype"):
        saved = await _get_user_blogger_settings(user_id)
        last = (saved.get("last_subtype") or "cover").strip().lower()
        # merge last subtype settings into state defaults
        if last == "cover":
            s = saved.get("cover") if isinstance(saved.get("cover"), dict) else {}
            await state.update_data(
                blogger_subtype="cover",
                blogger_platform=s.get("platform"),
                blogger_size=s.get("size"),
                blogger_allow_text=bool(s.get("allow_text")),
                blogger_model=s.get("model"),
                blogger_price=s.get("price"),
            )
        elif last == "logo":
            s = saved.get("logo") if isinstance(saved.get("logo"), dict) else {}
            await state.update_data(
                blogger_subtype="logo",
                blogger_style=s.get("style"),
                blogger_color=s.get("color"),
                blogger_model=s.get("model"),
                blogger_price=s.get("price"),
            )
        else:
            s = saved.get("presentation") if isinstance(saved.get("presentation"), dict) else {}
            await state.update_data(
                blogger_subtype="presentation",
                blogger_format=s.get("format"),
                blogger_size=s.get("size"),
                blogger_allow_text=bool(s.get("allow_text")),
                blogger_model=s.get("model"),
                blogger_price=s.get("price"),
            )
        data = await state.get_data()

    subtype = (data.get("blogger_subtype") or "cover").strip().lower()
    price = int(data.get("blogger_price") or 0)
    model_key = data.get("blogger_model")
    allow_text = bool(data.get("blogger_allow_text")) if subtype in ("presentation", "cover") else False

    tokens = await get_available_tokens_web(user_id)
    if price > 0 and tokens < price:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        await state.clear()
        return

    await state.set_state(ImageStates.waiting_blogger_prompt)

    if subtype == "cover":
        platform = data.get("blogger_platform") or "instagram_post"
        size = data.get("blogger_size") or "1080x1080"
        text_note = ""
        if allow_text:
            text_note = "\n\n🅰️ <b>Текст на изображении:</b> включён\n<i>Текст будет добавлен без ошибок. Если текста много — он станет мельче и перенесётся.</i>"
        await message.answer(
            "<b>📱 Обложка</b>\n\n"
            f"<b>Платформа:</b> {_pretty_cover_platform(platform)}\n"
            f"<b>Размер:</b> {size}\n"
            f"<b>Стоимость:</b> {_fmt_tokens(price)} токенов"
            f"{text_note}\n\n"
            "📝 Напишите тему/идею обложки (1–2 предложения).",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True),
            parse_mode="HTML",
        )
        return

    if subtype == "logo":
        style = data.get("blogger_style") or "icon"
        color = data.get("blogger_color") or "green"
        await message.answer(
            "<b>🎨 Логотип</b>\n\n"
            f"<b>Стиль:</b> {_pretty_logo_style(style)}\n"
            f"<b>Цвет:</b> {_pretty_logo_color(color)}\n"
            f"<b>Стоимость:</b> {_fmt_tokens(price)} токенов\n\n"
            "📝 Напишите идею/название бренда и сферу (например: «Coffee Wave, кофейня у моря»).",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True),
            parse_mode="HTML",
        )
        return

    # presentation
    fmt = data.get("blogger_format") or "9:16"
    size = data.get("blogger_size") or ("1080x1920" if fmt == "9:16" else "1920x1080")
    text_note = ""
    if allow_text:
        text_note = "\n\n🅰️ <b>Текст на изображении:</b> включён\n<i>Текст будет добавлен без ошибок, но если он слишком длинный — станет мельче и перенесётся на строки.</i>"
    await message.answer(
        "<b>📄 Презентация</b>\n\n"
        f"<b>Формат:</b> {fmt}\n"
        f"<b>Размер:</b> {size}\n"
        f"<b>Стоимость:</b> {_fmt_tokens(price)} токенов\n"
        f"{text_note}\n\n"
        "📝 Напишите тему/текст для слайда (лучше: заголовок + до 6 пунктов).",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True),
        parse_mode="HTML",
    )


async def get_user_model_settings(user_id: int, action: str) -> dict:
    """Получить настройки модели пользователя для конкретного действия"""
    from database.postgres_db import get_image_settings
    
    settings = await get_image_settings(user_id)
    
    model_key = settings.get(f"{action}_model", DEFAULT_MODELS[action]["model"])
    # Миграция "на лету" старых значений (Proxy/OpenAI keys) -> VseGPT model_id
    model_id = LEGACY_MODEL_MAP.get(action, {}).get(model_key, model_key)
    price = settings.get(f"{action}_price", DEFAULT_MODELS[action]["price"])
    
    return {
        "model": model_id,  # VseGPT model_id
        "price": price,
        "name": DEFAULT_MODELS[action]["name"],
        "time": DEFAULT_MODELS[action]["time"],
        "model_key": model_key
    }

class ImageStates(StatesGroup):
    waiting_create_prompt = State()
    waiting_upscale_photo = State()
    waiting_for_photo_with_caption = State()  # Новое состояние: фото с подписью в одном сообщении
    waiting_process_photo = State()
    waiting_blogger_prompt = State()
    waiting_creative_photo = State()
    waiting_creative_meme_idea = State()
    waiting_video_confirm = State()
    waiting_video_text = State()
    waiting_video_photo = State()


@router.message(ImageStates.waiting_blogger_prompt, F.text)
async def blogger_process_prompt(message: Message, state: FSMContext):
    user_id = message.from_user.id
    prompt_ru = (message.text or "").strip()
    if len(prompt_ru) < 3:
        await message.answer("⚠️ Слишком коротко. Опишите подробнее.")
        return

    data = await state.get_data()
    subtype = (data.get("blogger_subtype") or "cover").strip().lower()
    price = int(data.get("blogger_price") or 0)
    model_key = data.get("blogger_model")
    allow_text = bool(data.get("blogger_allow_text")) if subtype in ("presentation", "cover") else False
    model_id = _resolve_blogger_model(model_key)
    if not model_id:
        await message.answer("⚠️ Модель не поддерживается. Откройте настройки и выберите другую.", reply_markup=photo_kb(user_id))
        await state.clear()
        return

    tokens = await get_available_tokens_web(user_id)
    if price > 0 and tokens < price:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        await state.clear()
        return

    status = await show_status(bot, message.chat.id, "generate")
    try:
        prompt_en = await _to_english(prompt_ru)

        final_size = None

        if subtype == "cover":
            final_size = data.get("blogger_size") or "1080x1080"
            platform = data.get("blogger_platform") or "instagram_post"
            prompt = (
                f"Create a high-quality social media cover image for {platform}. "
                f"Topic: {prompt_en}. "
                "Make it clearly relevant to the topic (use suitable symbols/illustrations/icons). "
                "Leave clean empty space for a headline overlay, but DO NOT render any text. "
                "Modern, high contrast, strong composition. No watermark, no logo."
            )
        elif subtype == "logo":
            final_size = "1024x1024"
            style = data.get("blogger_style") or "icon"
            color = data.get("blogger_color") or "green"
            prompt = (
                f"Design a modern logo. Style: {style}. Color scheme: {color}. "
                f"Brand idea: {prompt_en}. "
                "Minimal, vector-like, clean shapes, white background, no watermark."
            )
        else:  # presentation
            final_size = data.get("blogger_size") or "1080x1920"
            fmt = data.get("blogger_format") or "9:16"
            prompt = (
                f"Create a presentation cover slide background (not abstract). Format {fmt}. "
                f"Topic: {prompt_en}. "
                "Use clean layout and subtle iconography/illustrations that match the topic. "
                "Leave empty areas for title and bullets, but DO NOT render any text. "
                "Modern, professional, high quality. No watermark."
            )

        img_bytes = await _vsegpt_images_generate(model_id=model_id, prompt=prompt, image_bytes=None)
        if final_size:
            img_bytes = _resize_to_exact(img_bytes, final_size)
        if subtype == "cover" and allow_text:
            img_bytes = _overlay_text_on_image(img_bytes, prompt_ru, layout="cover")
        if subtype == "presentation" and allow_text:
            img_bytes = _overlay_text_on_image(img_bytes, prompt_ru, layout="presentation")

        if price > 0:
            await use_tokens_smart_web(user_id, price, bot_name="images")
        new_balance = await get_available_tokens_web(user_id)

        await message.answer_photo(
            BufferedInputFile(img_bytes, filename="blogger.png"),
            caption=(
                "✅ <b>Готово!</b>\n\n"
                f"💰 Списано: {_fmt_tokens(price)} токенов\n"
                f"💳 Остаток: {_fmt_tokens(new_balance)} токенов"
            ),
            reply_markup=_done_inline_kb("blogger"),
            parse_mode="HTML",
        )
        await message.answer(
            "✨ <b>Готово!</b> Что делаем дальше?",
            reply_markup=_flow_done_kb("blogger"),
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
    finally:
        if status:
            await status.stop()
        await state.clear()


@router.message(ImageStates.waiting_creative_meme_idea, F.text)
async def creative_meme_idea_handler(message: Message, state: FSMContext):
    await creative_meme_idea(message, state)


@router.message(ImageStates.waiting_creative_photo, F.photo)
async def creative_process_photo_handler(message: Message, state: FSMContext):
    await creative_process_photo(message, state)


@router.message(F.text.in_(["🎨 Творчество", "📷 Фото", "📸 Фото"]))
async def photo_menu(message: Message):
    """Показать меню творчества (WebApp-кнопки)"""
    tokens = await get_available_tokens_web(message.from_user.id)
    
    await message.answer(
        f"🎨 <b>Творчество</b>\n\n"
        f"💰 Баланс: <b>{tokens:,}</b> токенов\n\n"
        f"📷 <b>Фото</b> — создание / 4K / редактор\n"
        f"🎬 <b>Видео</b> — настройки и запуск\n"
        f"🎵 <b>Аудио</b> — скоро в разработке\n\n"
        f"Нажмите нужную кнопку — откроются настройки.",
        reply_markup=photo_kb(message.from_user.id),
        parse_mode="HTML"
    )


@router.message(F.text == "🎵 Аудио")
async def audio_stub(message: Message):
    await message.answer(
        "🎵 Аудио — скоро в разработке! Следи за обновлениями ✨",
        reply_markup=photo_kb(message.from_user.id),
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

    # other webapps may send data too (e.g., video notes share)
    if payload.get("type") == "video_notes_share":
        try:
            from database.postgres_db import get_video_note
            note_id = int(payload.get("note_id") or 0)
            note = await get_video_note(message.from_user.id, note_id)
            if not note:
                await message.answer("⚠️ Конспект не найден.")
                return
            await message.answer(
                f"📂 <b>Конспект</b>\n\n"
                f"🎬 <b>{note['title']}</b>\n"
                f"🔗 {note['url']}\n"
                f"📅 {note['date_label']}\n\n"
                f"{note['text']}",
                parse_mode="HTML",
            )
        except Exception as e:
            await message.answer(f"❌ Ошибка:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
        return

    if payload.get("type") != "images_start":
        return

    action = payload.get("action")
    if action == "create":
        await create_photo_start(message, state)
    elif action == "upscale":
        # дополнительная настройка "соотношение" из WebApp (если передали)
        try:
            if "upscale_size" in payload:
                await state.update_data(upscale_size=payload.get("upscale_size"))
        except Exception:
            pass
        await upscale_photo_start(message, state)
    elif action == "edit":
        await editor_start(message, state)
    elif action == "video":
        # Запуск из веба — сразу в сценарий (без промежуточного подтверждения)
        await state.update_data(video_direct_start=True)
        await video_start(message, state)
    elif action == "process":
        # Запуск обработки фото из веба
        await state.update_data(
            process_action=payload.get("process_action"),
            process_model=payload.get("model"),
            process_price=payload.get("price"),
        )
        await process_start(message, state)
    elif action == "blogger":
        await state.update_data(
            blogger_subtype=payload.get("subtype"),
            blogger_platform=payload.get("platform"),
            blogger_size=payload.get("size"),
            blogger_style=payload.get("style"),
            blogger_color=payload.get("color"),
            blogger_format=payload.get("format"),
            blogger_allow_text=payload.get("allow_text"),
            blogger_model=payload.get("model"),
            blogger_price=payload.get("price"),
        )
        await blogger_start(message, state)
    elif action == "creative":
        await state.update_data(
            creative_subtype=payload.get("subtype"),
            creative_style=payload.get("style"),
            creative_custom_text=payload.get("custom_text"),
            creative_effect=payload.get("effect"),
            creative_meme_mode=payload.get("mode"),
            creative_meme_template=payload.get("template"),
            creative_meme_top=payload.get("text_top"),
            creative_meme_bottom=payload.get("text_bottom"),
            creative_model=payload.get("model"),
            creative_price=payload.get("price"),
        )
        await creative_start(message, state)
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


def _has_cyrillic(text: str) -> bool:
    return any('\u0400' <= char <= '\u04FF' for char in (text or ""))


async def _to_english(text: str) -> str:
    """
    Переводим на английский (если есть кириллица) — модели для видео чаще лучше реагируют на EN.
    Если deep_translator не установлен/ошибка — вернем исходный текст.
    """
    if not text:
        return ""
    if not _has_cyrillic(text):
        return text
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source='ru', target='en').translate(text)
    except Exception:
        return text


async def _vsegpt_images_generate(*, model_id: str, prompt: str, image_bytes: bytes | None = None) -> bytes:
    """
    Унифицированный вызов VseGPT /v1/images/generations:
    - text->image: image_bytes=None
    - img2img/edit/upscale: image_bytes=bytes, передаем как data:image/jpeg;base64,...
    """
    if not VSEGPT_API_KEY:
        raise Exception("VSEGPT_API_KEY не установлен в .env")

    headers = {"Authorization": f"Bearer {VSEGPT_API_KEY}", "Content-Type": "application/json"}

    payload: dict = {
        "model": model_id,
        "prompt": prompt,
        "response_format": "b64_json",
    }
    if image_bytes is not None:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload["image_url"] = f"data:image/jpeg;base64,{b64}"

    # transient errors do happen on VseGPT side; retry a few times
    transient = {429, 500, 501, 502, 503, 504}
    last_err: str | None = None

    # fallback model chain (if given model is unstable/unavailable)
    fallbacks: list[str] = []
    if model_id == "img-flux/kontext-max":
        fallbacks = ["img-flux/kontext-pro", "img-flux/flux-2", "img-flux/schnell"]
    elif model_id == "img-flux/kontext-pro":
        fallbacks = ["img-flux/flux-2", "img-flux/schnell"]

    candidates = [model_id] + [m for m in fallbacks if m and m != model_id]

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as session:
        for mi, mid in enumerate(candidates):
            payload["model"] = mid
            for attempt in range(3):
                async with session.post(VSEGPT_IMAGES_URL, headers=headers, json=payload) as resp:
                    text = await resp.text()
                    if resp.status == 200:
                        data = json.loads(text) if text else {}
                        break

                    last_err = f"VseGPT image error {resp.status}: {text[:300]}"
                    if resp.status not in transient:
                        raise Exception(last_err)

                # backoff before retry
                await asyncio.sleep(1.0 * (2 ** attempt))
            else:
                # exhausted retries for this model, try next candidate if any
                continue

            # success for this model, proceed to parse
            break
        else:
            # exhausted all candidates
            raise Exception(
                (last_err or "VseGPT: неизвестная ошибка")
                + "\n\nПохоже, это временная проблема на стороне VseGPT. Попробуйте ещё раз через 1–2 минуты."
            )

    # OpenAI-like response: {"data":[{"b64_json": "..."}]}
    d0 = (data.get("data") or [{}])[0] if isinstance(data, dict) else {}
    if isinstance(d0, dict) and d0.get("b64_json"):
        return base64.b64decode(d0["b64_json"])
    if isinstance(d0, dict) and d0.get("url"):
        # fallback: download
        url = d0["url"]
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as session:
            async with session.get(url) as r:
                return await r.read()

    raise Exception("VseGPT: пустой/непонятный ответ изображения")


async def _build_video_prompt(
    *,
    mode: str,
    user_text: str,
    tier: str,
    aspect_ratio: str,
    seconds: int,
    audio: bool,
    has_image: bool
) -> str:
    """
    Унифицированная структура промпта для video моделей.
    Цель: повысить управляемость (стабильность персонажей/объектов), убрать артефакты, добавить motion-описание.
    """
    mode = (mode or "photo_to_video").lower()
    tier = (tier or "econom").lower()
    aspect_ratio = aspect_ratio or "16:9"
    seconds = int(seconds or 5)

    base_request = (user_text or "").strip()
    base_request_en = (await _to_english(base_request)).strip()

    # Небольшой “каркас” для движения/качества. Для econom — проще, чтобы не “перегружать”.
    motion = {
        "animate_photo": "Subtle natural motion: gentle parallax, slight camera push-in, minor ambient movement. Keep faces and details stable.",
        "photo_to_video": "Cinematic motion: smooth camera movement, natural dynamics, stable subject. Keep the main person/object identity unchanged.",
        "text_to_video": "Cinematic scene with smooth camera movement, coherent motion, consistent characters and objects."
    }.get(mode, "Cinematic, smooth motion, consistent details.")

    # Аудио: по умолчанию — только окружение, без речи.
    audio_line = ""
    if audio:
        audio_line = "Audio: matching ambient sounds/music only. No spoken words unless explicitly requested."

    constraints = [
        f"Duration: {seconds}s.",
        f"Aspect ratio: {aspect_ratio}.",
        "No subtitles, no on-screen text, no logos, no watermarks.",
        "Avoid flicker, distortion, sudden morphing, extra limbs, duplicate faces.",
        "Maintain consistent lighting and style throughout the clip."
    ]
    if has_image:
        constraints.insert(0, "Use the provided image as the main reference. Preserve identity, face, clothing, and composition.")

    # Если пользователь не написал ничего — делаем безопасный дефолт
    if not base_request_en:
        if mode == "animate_photo":
            base_request_en = "Animate the photo naturally."
        elif mode == "photo_to_video":
            base_request_en = "Create a short video based on the photo."
        else:
            base_request_en = "Create a short cinematic video."

    # Собираем промпт
    # Для econom убираем часть ограничений (чтобы не “съедать” лимиты/качество)
    if tier == "econom":
        constraints = constraints[:4]

    prompt_parts = [
        base_request_en,
        motion,
        audio_line,
        "Constraints: " + " ".join([c for c in constraints if c])
    ]

    final_prompt = "\n".join([p for p in prompt_parts if p])
    return final_prompt[:2000]


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
    return f"https://soul-bot.ru/creativity/video?user_id={user_id}"

def _pretty_video_mode(mode: str) -> str:
    mode = (mode or "").lower()
    return {
        "photo_to_video": "Фото → Видео",
        "text_to_video": "Текст → Видео",
        "animate_photo": "Анимация фото",
    }.get(mode, mode or "—")


def _pretty_video_tier(tier: str) -> str:
    tier = (tier or "").lower()
    return {
        "econom": "Эконом",
        "standard": "Стандарт",
        "premium": "Премиум",
    }.get(tier, tier or "—")


def _pretty_aspect(aspect: str) -> str:
    aspect = (aspect or "").strip()
    return {
        "16:9": "16:9 (широкий)",
        "9:16": "9:16 (вертикальный)",
        "1:1": "1:1 (квадрат)",
        "4:3": "4:3",
        "3:4": "3:4",
    }.get(aspect, aspect or "—")


def _fmt_tokens(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")


def _flow_done_kb(kind: str) -> ReplyKeyboardMarkup:
    """Кнопки закрытия сценария после результата."""
    kind = (kind or "").lower()
    label = {
        "create": "🔁 Создать ещё",
        "upscale": "🔁 Улучшить ещё",
        "edit": "🔁 Редактировать ещё",
        "video": "🔁 Ещё видео",
        "process": "🔁 Обработать ещё",
        "blogger": "🔁 Ещё дизайн",
        "creative": "🔁 Ещё креатив",
    }.get(kind, "🔁 Ещё раз")
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=label), KeyboardButton(text="✅ Завершить")],
            [KeyboardButton(text="🎨 Творчество")],
        ],
        resize_keyboard=True
    )


def _done_inline_kb(kind: str) -> InlineKeyboardMarkup:
    """Inline-кнопки под результатом (видны сразу под медиа)."""
    kind = (kind or "").lower()
    label = {
        "create": "🔁 Создать ещё",
        "upscale": "🔁 Улучшить ещё",
        "edit": "🔁 Редактировать ещё",
        "video": "🔁 Ещё видео",
        "process": "🔁 Обработать ещё",
        "blogger": "🔁 Ещё дизайн",
        "creative": "🔁 Ещё креатив",
    }.get(kind, "🔁 Ещё раз")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=label, callback_data=f"flow_again:{kind}"),
            InlineKeyboardButton(text="✅ Завершить", callback_data="flow_finish"),
        ]
    ])



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
async def video_start(message: Message, state: FSMContext, user_id: int | None = None):
    user_id = user_id or message.from_user.id
    video_settings = await _get_user_video_settings(user_id)

    # Проверяем баланс
    tokens = await get_available_tokens_web(user_id)
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

    mode_h = _pretty_video_mode(mode)
    tier_h = _pretty_video_tier(tier)
    aspect_h = _pretty_aspect(aspect)

    # Если пришли из веба с “Начать в боте” — стартуем сразу
    data = await state.get_data()
    if data.get("video_direct_start"):
        await state.update_data(video_direct_start=False)
        await message.answer(
            "🎬 <b>Видео</b>\n\n"
            f"🧩 Режим: <b>{mode_h}</b>\n"
            f"💎 Уровень: <b>{tier_h}</b>\n"
            f"🔊 Аудио: <b>{audio}</b>\n"
            f"📐 Формат: <b>{aspect_h}</b> • <b>{seconds}</b> сек\n"
            f"💳 Стоимость: <b>{_fmt_tokens(price)}</b> токенов\n",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True),
            parse_mode="HTML"
        )
        await _enter_video_flow(message, state, video_settings)
        return

    await state.set_state(ImageStates.waiting_video_confirm)
    await message.answer(
        "🎬 <b>Видео</b>\n\n"
        f"Текущие настройки:\n\n"
        f"🧩 Режим: <b>{mode_h}</b>\n"
        f"💎 Уровень: <b>{tier_h}</b>\n"
        f"🔊 Аудио: <b>{audio}</b>\n"
        f"📐 Формат: <b>{aspect_h}</b> • <b>{seconds}</b> сек\n"
        f"💳 Стоимость: <b>{_fmt_tokens(price)}</b> токенов\n\n"
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
    tokens = await get_available_tokens_web(user_id)
    if price > 0 and tokens < price:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        await state.clear()
        return

    status = await show_status(bot, message.chat.id, "generate")
    try:
        model_id = _resolve_vsegpt_video_model_id(video_settings)
        aspect_ratio = video_settings.get("aspect_ratio") or "16:9"
        final_prompt = await _build_video_prompt(
            mode=video_settings.get("mode"),
            user_text=prompt,
            tier=video_settings.get("tier"),
            aspect_ratio=aspect_ratio,
            seconds=int(video_settings.get("seconds") or 5),
            audio=bool(video_settings.get("audio", False)),
            has_image=False
        )
        vbytes = await _vsegpt_generate_video_and_wait(
            model_id=model_id,
            prompt=final_prompt,
            image_bytes=None,
            aspect_ratio=aspect_ratio
        )

        await use_tokens_smart_web(user_id, price, bot_name="images") if price > 0 else None
        new_balance = await get_available_tokens_web(user_id)

        video_file = BufferedInputFile(vbytes, filename="video.mp4")
        await message.answer_video(
            video_file,
            caption=f"✅ <b>Видео готово!</b>\n\n💰 Списано: {_fmt_tokens(price)} токенов\n💳 Остаток: {_fmt_tokens(new_balance)} токенов",
            reply_markup=_done_inline_kb("video"),
            parse_mode="HTML"
        )
        await message.answer(
            "✨ <b>Готово!</b> Что делаем дальше?",
            reply_markup=_flow_done_kb("video"),
            parse_mode="HTML"
        )
    except Exception as e:
        traceback.print_exc()
        await message.answer(f"❌ Ошибка видео:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
    finally:
        if status:
            await status.stop()
        await state.clear()


@router.message(ImageStates.waiting_video_photo, F.photo)
async def process_video_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    video_settings = await _get_user_video_settings(user_id)
    price = int(video_settings.get("price") or 0)

    tokens = await get_available_tokens_web(user_id)
    if price > 0 and tokens < price:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        await state.clear()
        return

    # caption -> запрос пользователя (что должно происходить), иначе дефолт
    user_caption = (message.caption or "").strip()
    if not user_caption:
        user_caption = ""

    status = await show_status(bot, message.chat.id, "generate")
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        photo_data = await bot.download_file(file.file_path)
        image_bytes = photo_data.read()

        model_id = _resolve_vsegpt_video_model_id(video_settings)
        aspect_ratio = video_settings.get("aspect_ratio") or "16:9"
        final_prompt = await _build_video_prompt(
            mode=video_settings.get("mode"),
            user_text=user_caption,
            tier=video_settings.get("tier"),
            aspect_ratio=aspect_ratio,
            seconds=int(video_settings.get("seconds") or 5),
            audio=bool(video_settings.get("audio", False)),
            has_image=True
        )
        vbytes = await _vsegpt_generate_video_and_wait(
            model_id=model_id,
            prompt=final_prompt,
            image_bytes=image_bytes,
            aspect_ratio=aspect_ratio
        )

        await use_tokens_smart_web(user_id, price, bot_name="images") if price > 0 else None
        new_balance = await get_available_tokens_web(user_id)

        video_file = BufferedInputFile(vbytes, filename="video.mp4")
        await message.answer_video(
            video_file,
            caption=f"✅ <b>Видео готово!</b>\n\n💰 Списано: {_fmt_tokens(price)} токенов\n💳 Остаток: {_fmt_tokens(new_balance)} токенов",
            reply_markup=_done_inline_kb("video"),
            parse_mode="HTML"
        )
        await message.answer(
            "✨ <b>Готово!</b> Что делаем дальше?",
            reply_markup=_flow_done_kb("video"),
            parse_mode="HTML"
        )
    except Exception as e:
        traceback.print_exc()
        await message.answer(f"❌ Ошибка видео:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
    finally:
        if status:
            await status.stop()
        await state.clear()


@router.message(F.text == "📷 Создать")
async def create_photo_start(message: Message, state: FSMContext, user_id: int | None = None):
    """Начать создание фото"""
    uid = user_id or message.from_user.id
    tokens = await get_available_tokens_web(uid)
    
    model = await get_user_model_settings(uid, 'create')
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
async def upscale_photo_start(message: Message, state: FSMContext, user_id: int | None = None):
    """Начать upscale фото"""
    uid = user_id or message.from_user.id
    tokens = await get_available_tokens_web(uid)
    
    model = await get_user_model_settings(uid, 'upscale')
    if tokens < model['price']:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        return
    
    await state.set_state(ImageStates.waiting_upscale_photo)
    
    cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True)
    
    await message.answer(
        "✨ <b>Улучшение качества</b>\n\n"
        "📸 Отправьте фото, которое хотите улучшить.\n"
        "Я постараюсь сохранить лицо и похожесть максимально.",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )


@router.message(F.text == "✏️ Редактор")
async def editor_start(message: Message, state: FSMContext, user_id: int | None = None):
    """Начать редактирование - фото с подписью в одном сообщении"""
    uid = user_id or message.from_user.id
    tokens = await get_available_tokens_web(uid)
    
    model = await get_user_model_settings(uid, 'edit')
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


async def _get_user_process_settings(user_id: int) -> dict:
    """Получить настройки 'Обработка' из extra_settings.photo.process."""
    from database.postgres_db import get_image_settings
    settings = await get_image_settings(user_id)
    extra = settings.get("extra_settings") or {}
    photo = extra.get("photo") if isinstance(extra, dict) else None
    process = photo.get("process") if isinstance(photo, dict) else None
    if not isinstance(process, dict):
        # дефолт: удалить фон, эконом
        return {
            "action": "remove_background",
            "model": "img2img-aitransform/background-change",
            "price": 19800,
        }
    return {
        "action": process.get("action", "remove_background"),
        "model": process.get("model", "img2img-aitransform/background-change"),
        "price": int(process.get("price") or 19800),
    }


async def process_start(message: Message, state: FSMContext, user_id: int | None = None):
    """Старт сценария 'Обработка' (настройки в Web, контент в боте)."""
    user_id = user_id or message.from_user.id

    # Если пришло из WebApp — приоритет у payload
    data = await state.get_data()
    proc_action = data.get("process_action")
    proc_model = data.get("process_model")
    proc_price = data.get("process_price")
    if not (proc_action and proc_model and proc_price is not None):
        s = await _get_user_process_settings(user_id)
        proc_action, proc_model, proc_price = s["action"], s["model"], s["price"]
        await state.update_data(process_action=proc_action, process_model=proc_model, process_price=proc_price)

    tokens = await get_available_tokens_web(user_id)
    if int(proc_price) > 0 and tokens < int(proc_price):
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        await state.clear()
        return

    await state.set_state(ImageStates.waiting_process_photo)
    cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True)

    action_h = {
        "remove_background": "🖼 Удалить фон",
        "remove_text": "🧽 Удалить текст",
        "remove_object": "🪄 Удалить объект",
    }.get(proc_action, proc_action)

    extra_hint = ""
    if proc_action == "remove_object":
        extra_hint = "\n\n📝 <b>Важно:</b> отправьте фото <b>с подписью</b> — что именно убрать.\nНапример: <code>удали бутылку справа</code>"
    if proc_action == "remove_background":
        extra_hint = "\n\n📝 <b>Можно с подписью:</b> какой фон сделать.\nНапример: <code>белый фон</code>, <code>прозрачный фон</code>, <code>уютная кухня</code>"

    await message.answer(
        "🧰 <b>Обработка фото</b>\n\n"
        f"Действие: <b>{action_h}</b>\n"
        f"Стоимость: <b>{_fmt_tokens(proc_price)}</b> токенов\n\n"
        "📸 Отправьте фото для обработки."
        f"{extra_hint}",
        reply_markup=cancel_kb,
        parse_mode="HTML",
    )


@router.message(ImageStates.waiting_process_photo, F.photo)
async def process_process_photo(message: Message, state: FSMContext):
    """Применить обработку к фото."""
    user_id = message.from_user.id
    data = await state.get_data()
    proc_action = (data.get("process_action") or "").strip()
    model_id = data.get("process_model")
    price = int(data.get("process_price") or 0)

    tokens = await get_available_tokens_web(user_id)
    if price > 0 and tokens < price:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
        await state.clear()
        return

    caption = (message.caption or "").strip()
    if proc_action == "remove_object" and len(caption) < 3:
        await message.answer("⚠️ Добавьте подпись к фото: что именно убрать (например: <code>удали бутылку справа</code>)", parse_mode="HTML")
        return

    status = await show_status(bot, message.chat.id, "generate")
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        photo_data = await bot.download_file(file.file_path)
        image_bytes_raw = photo_data.read()
        jpeg_bytes = _convert_to_jpeg(image_bytes_raw)

        user_text = caption
        user_en = await _to_english(user_text) if user_text else ""

        if proc_action == "remove_background":
            bg = user_en.strip()
            if not bg:
                bg = "plain white background"
            prompt = (
                f"Replace the background with: {bg}. "
                "Keep the main subject intact. Preserve identity, face, age, and main features. "
                "No text, no watermark."
            )
        elif proc_action == "remove_text":
            prompt = (
                "Remove all text, captions, watermarks, and logos. Reconstruct the background naturally. "
                "Preserve identity and face. No new text."
            )
        else:  # remove_object
            prompt = (
                f"Remove the following object(s) from the image: {user_en}. "
                "Fill the removed area naturally (inpainting). "
                "Preserve the person's identity, face, age, and main features. "
                "No text, no watermark."
            )

        out_bytes = await _vsegpt_images_generate(model_id=model_id, prompt=prompt, image_bytes=jpeg_bytes)

        await use_tokens_smart_web(user_id, price, bot_name="images") if price > 0 else None
        new_balance = await get_available_tokens_web(user_id)

        await message.answer_photo(
            BufferedInputFile(out_bytes, filename="processed.png"),
            caption=f"✅ <b>Готово!</b>\n\n💰 Списано: {_fmt_tokens(price)} токенов\n💳 Остаток: {_fmt_tokens(new_balance)} токенов",
            reply_markup=_done_inline_kb("process"),
            parse_mode="HTML",
        )
        await message.answer(
            "✨ <b>Готово!</b> Что делаем дальше?",
            reply_markup=_flow_done_kb("process"),
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка обработки:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
    finally:
        if status:
            await status.stop()
        await state.clear()


@router.message(F.text == "🛑 Отменить")
async def cancel_operation(message: Message, state: FSMContext):
    """Отменить операцию"""
    await state.clear()
    await message.answer("❌ Операция отменена", reply_markup=photo_kb(message.from_user.id))


@router.message(F.text.in_(["🔁 Создать ещё", "🔁 Улучшить ещё", "🔁 Редактировать ещё", "🔁 Ещё видео", "🔁 Обработать ещё", "🔁 Ещё дизайн", "🔁 Ещё креатив"]))
async def flow_again(message: Message, state: FSMContext):
    """Повторить сценарий после результата."""
    await state.clear()
    t = message.text or ""
    if "Улучшить" in t:
        await upscale_photo_start(message, state)
        return
    if "Редактировать" in t:
        await editor_start(message, state)
        return
    if "Ещё видео" in t:
        await video_start(message, state)
        return
    if "Обработать" in t:
        await process_start(message, state)
        return
    if "дизайн" in t.lower():
        await blogger_start(message, state)
        return
    if "креатив" in t.lower():
        await creative_start(message, state)
        return
    await create_photo_start(message, state)


@router.message(F.text == "✅ Завершить")
async def finish_flow(message: Message, state: FSMContext):
    """Явно закрыть сценарий и вернуть в общее меню."""
    await state.clear()
    await message.answer("🎨 Творчество", reply_markup=photo_kb(message.from_user.id))


@router.callback_query(F.data.startswith("flow_again:"))
async def cb_flow_again(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    kind = (cb.data.split(":", 1)[1] if cb.data else "").strip().lower()
    if kind == "upscale":
        await upscale_photo_start(cb.message, state, user_id=cb.from_user.id)
        return
    if kind == "edit":
        await editor_start(cb.message, state, user_id=cb.from_user.id)
        return
    if kind == "video":
        await video_start(cb.message, state, user_id=cb.from_user.id)
        return
    if kind == "process":
        await process_start(cb.message, state, user_id=cb.from_user.id)
        return
    if kind == "blogger":
        await blogger_start(cb.message, state, user_id=cb.from_user.id)
        return
    if kind == "creative":
        await creative_start(cb.message, state, user_id=cb.from_user.id)
        return
    await create_photo_start(cb.message, state, user_id=cb.from_user.id)


@router.callback_query(F.data == "flow_finish")
async def cb_flow_finish(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer("🎨 Творчество", reply_markup=photo_kb(cb.from_user.id))


# Backward-compat: старые callback_data из прошлых сообщений
@router.callback_query(F.data == "img_create_again")
async def cb_legacy_create_again(cb: CallbackQuery, state: FSMContext):
    cb.data = "flow_again:create"
    await cb_flow_again(cb, state)


@router.callback_query(F.data == "img_finish")
async def cb_legacy_finish(cb: CallbackQuery, state: FSMContext):
    cb.data = "flow_finish"
    await cb_flow_finish(cb, state)


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
    
    tokens = await get_available_tokens_web(message.from_user.id)
    model = await get_user_model_settings(message.from_user.id, 'create')
    
    if tokens < model['price']:
        await message.answer("❌ Недостаточно токенов!")
        await state.clear()
        return
    
    prompt_ru = message.text
    prompt_en = await _to_english(prompt_ru)
    prompt = (
        f"{prompt_en}\n\n"
        "High quality. No text, no watermark, no logo. Natural details."
    )
    
    status = await show_status(bot, message.chat.id, "generate")
    try:
        image_data = await _vsegpt_images_generate(
            model_id=model["model"],
            prompt=prompt,
            image_bytes=None
        )
        
        photo = BufferedInputFile(image_data, filename="created.png")
        
        # Используем единую систему токенов (поддержка подписок)
        await use_tokens_smart_web(message.from_user.id, model['price'], bot_name='images')
        new_balance = await get_available_tokens_web(message.from_user.id)
        
        await message.answer_photo(
            photo,
            caption=f"✅ <b>Готово!</b>\n\n💰 Списано: {_fmt_tokens(model['price'])} токенов\n💳 Остаток: {_fmt_tokens(new_balance)} токенов",
            reply_markup=_done_inline_kb("create"),
            parse_mode="HTML"
        )
        await message.answer(
            "✨ <b>Готово!</b> Что делаем дальше?",
            reply_markup=_flow_done_kb("create"),
            parse_mode="HTML"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
    finally:
        if status:
            await status.stop()
        await state.clear()


# === UPSCALE 4K ===
@router.message(ImageStates.waiting_upscale_photo, F.photo)
async def process_upscale(message: Message, state: FSMContext):
    """Улучшить фото до 4K"""
    tokens = await get_available_tokens_web(message.from_user.id)
    model = await get_user_model_settings(message.from_user.id, 'upscale')
    
    if tokens < model['price']:
        await message.answer("❌ Недостаточно токенов!")
        await state.clear()
        return
    
    photo = message.photo[-1]
    
    status = await show_status(bot, message.chat.id, "generate")
    try:
        file = await bot.get_file(photo.file_id)
        photo_data = await bot.download_file(file.file_path)
        image_bytes_raw = photo_data.read()

        jpeg_bytes = _convert_to_jpeg(image_bytes_raw)

        data = await state.get_data()
        size_key = (data.get("upscale_size") or "auto").strip()

        size_hint = ""
        if size_key == "1:1":
            size_hint = "Keep a square framing (1:1) if you need to crop."
        elif size_key == "16:9":
            size_hint = "Keep a wide framing (16:9) if you need to crop."
        elif size_key == "9:16":
            size_hint = "Keep a vertical framing (9:16) if you need to crop."

        # Upscale prompt: улучшить качество, но НЕ менять лицо/похожесть
        prompt = (
            "Upscale and enhance this image. Improve sharpness, clarity, details, and overall quality. "
            "Preserve identity, face, age, and main features. Do not change the person's likeness. "
            "No text, no watermark. "
            f"{size_hint}"
        )

        image_data = await _vsegpt_images_generate(
            model_id=model["model"],
            prompt=prompt,
            image_bytes=jpeg_bytes
        )
        
        photo_result = BufferedInputFile(image_data, filename="upscaled.png")
        
        # Списываем токены
        await use_tokens_smart_web(message.from_user.id, model['price'], bot_name='images')
        new_balance = await get_available_tokens_web(message.from_user.id)
        
        await message.answer_photo(
            photo_result,
            caption=f"✅ <b>Готово!</b>\n\n💰 Списано: {_fmt_tokens(model['price'])} токенов\n💳 Остаток: {_fmt_tokens(new_balance)} токенов",
            reply_markup=_done_inline_kb("upscale"),
            parse_mode="HTML"
        )
        await message.answer(
            "✨ <b>Готово!</b> Что делаем дальше?",
            reply_markup=_flow_done_kb("upscale"),
            parse_mode="HTML"
        )
        
    except Exception as e:
        error_msg = str(e)[:300]
        print(f"❌ [Upscale Error] {error_msg}")
        traceback.print_exc()
        await message.answer(f"❌ Ошибка улучшения фото:\n<code>{error_msg}</code>", parse_mode="HTML")
    finally:
        if status:
            await status.stop()
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
        "   Например: <code>добавь улыбку</code>\n"
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
    tokens = await get_available_tokens_web(user_id)
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
    
    status = await show_status(bot, message.chat.id, "generate")
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        photo_data = await bot.download_file(file.file_path)
        image_bytes_raw = photo_data.read()

        jpeg_bytes = _convert_to_jpeg(image_bytes_raw)

        # Переводим запрос пользователя на EN (лучше управляемость/стабильность)
        cmd_en = await _to_english(edit_command)
        english_prompt = (
            f"{cmd_en}\n\n"
            "Important: preserve identity, face, age, skin tone, and main facial features. "
            "Make only the requested changes. Do not change the person's likeness. "
            "No text, no watermark."
        )

        img_bytes = await _vsegpt_images_generate(
            model_id=model["model"],
            prompt=english_prompt,
            image_bytes=jpeg_bytes
        )

        result_photo = BufferedInputFile(img_bytes, filename="edited.png")

        await use_tokens_smart_web(user_id, model['price'], bot_name='images')
        new_balance = await get_available_tokens_web(user_id)

        await message.answer_photo(
            result_photo,
            caption=(
                f"✅ <b>Готово!</b>\n\n"
                f"📝 Команда: <i>{edit_command}</i>\n"
                f"💰 Списано: {_fmt_tokens(model['price'])} токенов\n"
                f"💳 Остаток: {_fmt_tokens(new_balance)} токенов"
            ),
            reply_markup=_done_inline_kb("edit"),
            parse_mode="HTML"
        )
        await message.answer(
            "✨ <b>Готово!</b> Что делаем дальше?",
            reply_markup=_flow_done_kb("edit"),
            parse_mode="HTML"
        )
                    
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        traceback.print_exc()
        await message.answer(
            f"❌ <b>Ошибка редактирования</b>\n\n<code>{str(e)[:150]}</code>",
            parse_mode="HTML"
        )
    finally:
        if status:
            await status.stop()
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
