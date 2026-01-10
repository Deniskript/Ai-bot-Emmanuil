from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards.reply import photo_kb, bots_menu_kb
import aiohttp
import base64
import os

router = Router()

PROXYAPI_KEY = os.getenv("OPENAI_API_KEY", "")
API_URL = "https://api.proxyapi.ru/openai/v1/images/generations"

# Цены с маржой x3
MODELS = {
    "create": {"name": "📷 Создание", "model": "gpt-image-1-mini", "quality": "medium", "price": 8000, "time": "20-40 сек"},
    "upscale": {"name": "🎨 4K Upscale", "model": "gpt-image-1.5", "quality": "hd", "price": 33000, "time": "40-60 сек"},
    "edit": {"name": "✏️ Редактор", "model": "gpt-image-1.5", "quality": "medium", "price": 15000, "time": "30-50 сек"}
}

class ImageStates(StatesGroup):
    waiting_create_prompt = State()
    waiting_upscale_photo = State()
    waiting_edit_photo = State()
    waiting_edit_command = State()


@router.message(F.text == "📷 Фото")
async def photo_menu(message: Message):
    """Показать меню фото"""
    from database import db
    user = await db.get_user(message.from_user.id)
    tokens = user.get('tokens', 0) if user else 0
    
    await message.answer(
        f"📷 <b>Генерация изображений</b>\n\n"
        f"💰 Баланс: <b>{tokens:,}</b> токенов\n\n"
        f"📷 <b>Создать</b> — создать фото по тексту (8K)\n"
        f"🎨 <b>4K Фото</b> — улучшить ваше фото до 4K (33K)\n"
        f"✏️ <b>Редактор</b> — изменить фото по команде (15K)\n"
        f"⚙️ <b>Настройки</b> — параметры на сайте",
        reply_markup=photo_kb(message.from_user.id),
        parse_mode="HTML"
    )


@router.message(F.text == "📷 Создать")
async def create_photo_start(message: Message, state: FSMContext):
    """Начать создание фото"""
    from database import db
    user = await db.get_user(message.from_user.id)
    tokens = user.get('tokens', 0) if user else 0
    
    if tokens < 0:
        await message.answer("❌ У вас отрицательный баланс! Пополните токены.")
        return
    
    await state.set_state(ImageStates.waiting_create_prompt)
    
    # Кнопка отмены
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True)
    
    await message.answer(
        "📷 <b>Создание фото</b>\n\n"
        "Опишите что хотите увидеть:\n\n"
        f"<i>Пример: Космический кот в скафандре на Марсе, digital art</i>\n\n"
        f"💰 Стоимость: 8,000 токенов",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )


@router.message(F.text == "🎨 4K Фото")
async def upscale_photo_start(message: Message, state: FSMContext):
    """Начать upscale фото"""
    from database import db
    user = await db.get_user(message.from_user.id)
    tokens = user.get('tokens', 0) if user else 0
    
    if tokens < 0:
        await message.answer("❌ У вас отрицательный баланс! Пополните токены.")
        return
    
    await state.set_state(ImageStates.waiting_upscale_photo)
    
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True)
    
    await message.answer(
        "🎨 <b>Улучшение фото до 4K</b>\n\n"
        "Отправьте фото которое хотите улучшить\n\n"
        f"💰 Стоимость: 33,000 токенов",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )


@router.message(F.text == "✏️ Редактор")
async def editor_start(message: Message, state: FSMContext):
    """Начать редактирование"""
    from database import db
    user = await db.get_user(message.from_user.id)
    tokens = user.get('tokens', 0) if user else 0
    
    if tokens < 0:
        await message.answer("❌ У вас отрицательный баланс! Пополните токены.")
        return
    
    await state.set_state(ImageStates.waiting_edit_photo)
    
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Отменить")]], resize_keyboard=True)
    
    await message.answer(
        "✏️ <b>Редактор изображений</b>\n\n"
        "Отправьте фото для редактирования\n\n"
        f"💰 Стоимость: 15,000 токенов\n\n"
        f"<i>Примеры команд:\n"
        f"• Сделай фон ночью\n"
        f"• Добавь море\n"
        f"• Сделай меня с обезьяной</i>",
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
    from keyboards.reply import bots_menu_kb
    await message.answer("🫧 Soul AI", reply_markup=bots_menu_kb())


# === СОЗДАНИЕ ФОТО ПО ТЕКСТУ ===
@router.message(ImageStates.waiting_create_prompt)
async def process_create(message: Message, state: FSMContext):
    """Создать фото по тексту"""
    if not message.text:
        return
    
    from database import db
    user = await db.get_user(message.from_user.id)
    tokens = user.get('tokens', 0) if user else 0
    
    if tokens < 0:
        await message.answer("❌ Отрицательный баланс!")
        await state.clear()
        return
    
    model = MODELS['create']
    prompt = message.text
    
    status = await message.answer(
        f"🎨 <b>{model['name']}...</b>\n\n"
        f"⏱ ~{model['time']}\n"
        f"<i>Подождите...</i>",
        parse_mode="HTML"
    )
    
    try:
        headers = {"Authorization": f"Bearer {PROXYAPI_KEY}", "Content-Type": "application/json"}
        payload = {"model": model['model'], "prompt": prompt, "size": "1024x1024", "n": 1}
        
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
        
        await db.subtract_tokens(message.from_user.id, model['price'])
        new_balance = tokens - model['price']
        
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
    await message.answer("🚧 Функция upscale в разработке! Скоро будет доступна.", reply_markup=photo_kb(message.from_user.id))
    await state.clear()


# === РЕДАКТОР ===
@router.message(ImageStates.waiting_edit_photo, F.photo)
async def photo_for_edit(message: Message, state: FSMContext):
    """Получено фото для редактирования"""
    photo = message.photo[-1]
    await state.update_data(photo_file_id=photo.file_id)
    await state.set_state(ImageStates.waiting_edit_command)
    
    await message.answer(
        "✏️ Фото получено!\n\n"
        "Теперь напишите команду:\n\n"
        "<i>• Сделай фон ночью\n"
        "• Добавь море на фон\n"
        "• Добавь как я обнимаю обезьяну</i>",
        parse_mode="HTML"
    )


@router.message(ImageStates.waiting_edit_command)
async def process_edit(message: Message, state: FSMContext):
    """Редактировать фото по команде"""
    if not message.text:
        return
    
    await message.answer("🚧 Функция редактора в разработке! Скоро будет доступна.", reply_markup=photo_kb(message.from_user.id))
    await state.clear()
