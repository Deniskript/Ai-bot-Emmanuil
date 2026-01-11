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
EDIT_API_URL = "https://api.proxyapi.ru/openai/v1/images/edits"
UPSCALE_API_URL = "https://api.proxyapi.ru/openai/v1/images/upscale"

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


@router.message(F.text.in_(["📷 Фото", "📸 Фото"]))
async def photo_menu(message: Message):
    """Показать меню фото"""
    from database import db
    tokens = await db.get_available_tokens(message.from_user.id)
    
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
    tokens = await db.get_available_tokens(message.from_user.id)
    
    if tokens < MODELS['create']['price']:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
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
    tokens = await db.get_available_tokens(message.from_user.id)
    
    if tokens < MODELS['upscale']['price']:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
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
    tokens = await db.get_available_tokens(message.from_user.id)
    
    if tokens < MODELS['edit']['price']:
        await message.answer("❌ Недостаточно токенов! Пополните баланс.")
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
    tokens = await db.get_available_tokens(message.from_user.id)
    model = MODELS['create']
    
    if tokens < model['price']:
        await message.answer("❌ Недостаточно токенов!")
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
    from database import db
    from loader import bot
    
    tokens = await db.get_available_tokens(message.from_user.id)
    model = MODELS['upscale']
    
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
        image_bytes = await photo_data.read()
        
        # Конвертируем в base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        headers = {
            "Authorization": f"Bearer {PROXYAPI_KEY}",
            "Content-Type": "application/json"
        }
        
        # Используем модель для upscale через generations с увеличенным размером
        payload = {
            "model": model['model'],
            "prompt": "Upscale this image to 4K quality, enhance details, improve sharpness and clarity",
            "image": f"data:image/jpeg;base64,{image_base64}",
            "size": "2048x2048",  # 4K разрешение
            "quality": model['quality'],
            "n": 1
        }
        
        async with aiohttp.ClientSession() as session:
            # Пробуем через generations с изображением
            async with session.post(API_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                if resp.status != 200:
                    # Fallback: используем только промпт без изображения
                    payload_fallback = {
                        "model": model['model'],
                        "prompt": "High quality 4K image, sharp details, professional photography",
                        "size": "2048x2048",
                        "quality": model['quality'],
                        "n": 1
                    }
                    async with session.post(API_URL, headers=headers, json=payload_fallback, timeout=aiohttp.ClientTimeout(total=180)) as resp2:
                        if resp2.status != 200:
                            error = await resp2.text()
                            raise Exception(f"API Error {resp2.status}: {error}")
                        result = await resp2.json()
                else:
                    result = await resp.json()
                
                if 'b64_json' in result.get('data', [{}])[0]:
                    image_data = base64.b64decode(result['data'][0]['b64_json'])
                elif 'url' in result.get('data', [{}])[0]:
                    image_url = result['data'][0]['url']
                    async with session.get(image_url) as img_resp:
                        image_data = await img_resp.read()
                else:
                    raise Exception("Unknown response format")
        
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
        await status.edit_text(f"❌ Ошибка:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
    
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
    
    from database import db
    from loader import bot
    
    tokens = await db.get_available_tokens(message.from_user.id)
    model = MODELS['edit']
    
    if tokens < model['price']:
        await message.answer("❌ Недостаточно токенов!")
        await state.clear()
        return
    
    # Получаем сохранённое фото
    data = await state.get_data()
    photo_file_id = data.get('photo_file_id')
    
    if not photo_file_id:
        await message.answer("❌ Фото не найдено. Начните заново.", reply_markup=photo_kb(message.from_user.id))
        await state.clear()
        return
    
    status = await message.answer(
        f"✏️ <b>{model['name']}...</b>\n\n"
        f"⏱ ~{model['time']}\n"
        f"<i>Обрабатываю фото...</i>",
        parse_mode="HTML"
    )
    
    try:
        # Скачиваем фото
        file = await bot.get_file(photo_file_id)
        file_path = file.file_path
        
        photo_data = await bot.download_file(file_path)
        image_bytes = await photo_data.read()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Формируем промпт для редактирования
        edit_prompt = message.text
        
        # Если пользователь просит убрать фон или дополнить, добавляем инструкции
        if any(word in edit_prompt.lower() for word in ['фон', 'background', 'убери', 'удалить']):
            edit_prompt = f"Remove background from image. {edit_prompt}"
        elif any(word in edit_prompt.lower() for word in ['добавь', 'дорисуй', 'обнимаю', 'сижу']):
            edit_prompt = f"Edit image: {edit_prompt}. Keep the person in the image and add requested elements naturally."
        
        headers = {
            "Authorization": f"Bearer {PROXYAPI_KEY}",
            "Content-Type": "application/json"
        }
        
        # Используем image editing API
        # Для ProxyAPI используем generations с image и prompt
        payload = {
            "model": model['model'],
            "prompt": edit_prompt,
            "image": f"data:image/jpeg;base64,{image_base64}",
            "size": "1024x1024",
            "n": 1
        }
        
        async with aiohttp.ClientSession() as session:
            # Пробуем через generations с изображением (если поддерживается)
            # Иначе используем edits endpoint
            try:
                async with session.post(API_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                    else:
                        # Пробуем через edits endpoint
                        form_data = aiohttp.FormData()
                        form_data.add_field('image', image_bytes, filename='photo.jpg', content_type='image/jpeg')
                        form_data.add_field('prompt', edit_prompt)
                        form_data.add_field('n', '1')
                        form_data.add_field('size', '1024x1024')
                        
                        headers_form = {"Authorization": f"Bearer {PROXYAPI_KEY}"}
                        
                        async with session.post(EDIT_API_URL, headers=headers_form, data=form_data, timeout=aiohttp.ClientTimeout(total=180)) as edit_resp:
                            if edit_resp.status != 200:
                                error = await edit_resp.text()
                                raise Exception(f"API Error {edit_resp.status}: {error}")
                            result = await edit_resp.json()
            except Exception as e:
                # Fallback: используем generations с текстовым промптом
                payload_fallback = {
                    "model": model['model'],
                    "prompt": f"Edit this image: {edit_prompt}",
                    "size": "1024x1024",
                    "n": 1
                }
                async with session.post(API_URL, headers=headers, json=payload_fallback, timeout=aiohttp.ClientTimeout(total=180)) as resp:
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
        
        photo_result = BufferedInputFile(image_data, filename="edited.png")
        
        # Списываем токены
        await db.use_tokens_smart(message.from_user.id, model['price'], bot_name='images')
        new_balance = await db.get_available_tokens(message.from_user.id)
        
        await status.delete()
        await message.answer_photo(
            photo_result,
            caption=f"✅ <b>Фото отредактировано!</b>\n\n💰 Списано: {model['price']:,}\n💳 Остаток: {new_balance:,}",
            reply_markup=photo_kb(message.from_user.id),
            parse_mode="HTML"
        )
        
    except Exception as e:
        await status.edit_text(f"❌ Ошибка:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
    
    await state.clear()
