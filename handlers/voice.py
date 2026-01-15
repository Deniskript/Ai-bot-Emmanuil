from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards import reply, inline
from utils.openrouter import ask
from utils.tokens import calculate_tokens
from utils.memory import update_memory, build_memory_context
from utils.voice import download_voice, transcribe_voice, text_to_speech
from utils.antiflood import ai_flood
from prompts.voice_prompt import VOICE_EMOTIONAL_PROMPT
from utils.status_manager import show_status
from config import MIN_TOKENS
from loader import bot
import asyncio
import os


router = Router()


class VoiceSt(StatesGroup):
    """Состояния голосового режима"""
    choose_gender = State()  # Выбор голоса
    chat = State()  # Активный голосовой чат


# Мапинг голосов
VOICE_MAP = {
    "male": "onyx",      # Мужской голос
    "female": "shimmer"  # Женский голос (мягкий, тёплый)
}


# ========== ВХОД В ГОЛОСОВОЙ РЕЖИМ ==========

@router.message(F.text == "🎤 Голос")
async def voice_mode_enter(msg: Message, state: FSMContext):
    """Вход в голосовой режим из выбора характера"""
    # Проверяем есть ли уже сохранённый голос
    voice_gender = await db.get_voice_gender(msg.from_user.id, 'voice')
    
    if voice_gender:
        # Голос уже выбран, сразу в чат
        await state.set_state(VoiceSt.chat)
        gender_name = "Мужской" if voice_gender == "male" else "Женский"
        await msg.answer(
            f"🎤 <b>Голосовой режим активирован!</b>\n\n"
            f"🔊 Голос: {gender_name}\n\n"
            f"💬 Отправь голосовое сообщение или напиши текст — я отвечу голосом!",
            reply_markup=reply.voice_chat_kb()
        )
    else:
        # Первый вход - выбор голоса
        await state.set_state(VoiceSt.choose_gender)
        await msg.answer(
            "🎤 <b>Голосовой режим</b>\n\n"
            "Я буду отвечать тебе голосовыми сообщениями!\n\n"
            "👉 Выбери голос для общения:",
            reply_markup=inline.voice_gender_kb()
        )


# ========== ВЫБОР ГОЛОСА ==========

@router.callback_query(F.data.startswith("voice:gender:"))
async def voice_gender_selected(cb: CallbackQuery, state: FSMContext):
    """Обработка выбора голоса"""
    gender = cb.data.split(":")[2]  # male или female
    
    # Сохраняем выбор в БД
    await db.set_voice_gender(cb.from_user.id, gender, 'voice')
    
    # Переходим в режим чата
    await state.set_state(VoiceSt.chat)
    
    gender_name = "Мужской" if gender == "male" else "Женский"
    await cb.message.edit_text(
        f"✅ <b>Голос выбран: {gender_name}</b>\n\n"
        f"🎤 Голосовой режим активирован!\n\n"
        f"💬 Отправь голосовое сообщение или напиши текст — я отвечу голосом!"
    )
    
    await cb.message.answer(
        "🎧 <b>Готов слушать!</b>",
        reply_markup=reply.voice_chat_kb()
    )


# ========== УПРАВЛЕНИЕ РЕЖИМОМ ==========

@router.message(VoiceSt.chat, F.text == "🛑 Завершить")
async def voice_stop(msg: Message, state: FSMContext):
    """Выход из голосового режима"""
    await state.clear()
    await msg.answer(
        "👋 Голосовой режим завершён!\n\n"
        "Возвращайся когда захочешь поговорить! 🎤",
        reply_markup=reply.dialog_char_kb()
    )


@router.message(VoiceSt.chat, F.text == "🗑 Очистить")
async def voice_clear(msg: Message):
    """Очистка истории"""
    await db.clear_msgs(msg.from_user.id, 'voice')
    await msg.answer("🗑 История очищена! Продолжаем:")


@router.message(VoiceSt.chat, F.text == "🔄 Сменить голос")
async def voice_change_gender(msg: Message, state: FSMContext):
    """Смена голоса"""
    await state.set_state(VoiceSt.choose_gender)
    current_gender = await db.get_voice_gender(msg.from_user.id, 'voice')
    current_name = "Мужской" if current_gender == "male" else "Женский"
    
    await msg.answer(
        f"🔊 Текущий голос: {current_name}\n\n"
        f"Выбери новый голос:",
        reply_markup=inline.voice_gender_kb()
    )


# ========== ОБРАБОТКА СООБЩЕНИЙ ==========

async def process_voice_message(msg: Message, state: FSMContext, text: str):
    """
    Главная функция обработки сообщения в голосовом режиме
    1. Проверки (антифлуд, токены)
    2. Получение ответа от AI
    3. Озвучка через TTS
    4. Отправка голосового сообщения
    """
    user_id = msg.from_user.id
    
    # Антифлуд
    allowed, error_msg = await ai_flood.check(user_id)
    if not allowed:
        await msg.answer(error_msg)
        return
    
    # Проверка токенов
    remaining = await db.get_available_tokens(user_id)
    if remaining < MIN_TOKENS:
        await msg.answer(
            "❌ Токены закончились!\n\n"
            "💎 Пополните в разделе 💎 Подписка",
            reply_markup=reply.main_kb(user_id)
        )
        return
    
    status = await show_status(bot, msg.chat.id, "voice")
    try:
        # Получаем голос пользователя
        voice_gender = await db.get_voice_gender(user_id, 'voice')
        if not voice_gender:
            voice_gender = "female"  # default
            await db.set_voice_gender(user_id, voice_gender, 'voice')
        
        # Модель AI
        model = await db.get_user_model(user_id)
        
        # Память
        mem = await db.get_memory(user_id, 'voice')
        memory_context = build_memory_context(mem)
        
        # История (последние 20 сообщений)
        hist = await db.get_msgs(user_id, 'voice', 20)
        
        # Системный промпт с эмоциональностью
        system_prompt = f"""{VOICE_EMOTIONAL_PROMPT}
{memory_context}

ВАЖНО: НЕ начинай ответ с приветствия если пользователь не здоровается. Отвечай по существу."""
        
        # Формируем сообщения для API
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(hist)
        messages.append({"role": "user", "content": text})
        
        # Запрос к AI
        resp, tokens_used = await ask(messages, model)
        
        if not resp:
            await msg.answer("❌ Не удалось получить ответ")
            return
        
        # Очищаем ответ от эмодзи и markdown
        resp_clean = resp.replace("**", "").replace("*", "")
        # Удаляем эмодзи (упрощённо)
        import re
        resp_clean = re.sub(r'[^\w\s,.!?;:—\-()«»"\']+', '', resp_clean, flags=re.UNICODE)
        
        # Списываем токены
        await db.use_tokens_smart(user_id, tokens_used, 'voice')
        await db.increment_requests(user_id)
        
        # Сохраняем в историю
        await db.add_msg(user_id, 'voice', 'user', text)
        await db.add_msg(user_id, 'voice', 'assistant', resp_clean)
        
        # Обновляем память в фоне
        asyncio.create_task(update_memory(user_id, 'voice', text, resp_clean))
        
        # Преобразуем в речь
        voice_tts = VOICE_MAP.get(voice_gender, "onyx")
        audio_path = await text_to_speech(resp_clean, voice=voice_tts)
        
        if not audio_path:
            await msg.answer("❌ Ошибка озвучки")
            # Отправляем текстом на всякий случай
            await msg.answer(f"📝 {resp_clean[:500]}")
            return
        
        # Отправляем голосовое сообщение
        voice_file = FSInputFile(audio_path)
        await msg.answer_voice(voice_file)
        
        # Удаляем временный файл
        try:
            os.remove(audio_path)
        except:
            pass
            
    except Exception as e:
        print(f"Voice processing error: {e}")
        import traceback
        traceback.print_exc()
        await msg.answer(f"❌ Ошибка: {str(e)[:100]}")
    finally:
        if status:
            await status.stop()


# ========== ОБРАБОТЧИКИ ВХОДЯЩИХ СООБЩЕНИЙ ==========

@router.message(VoiceSt.chat, F.voice)
async def voice_chat_voice(msg: Message, state: FSMContext):
    """Обработка голосового сообщения от пользователя"""
    if msg.text in ["🛑 Завершить", "🗑 Очистить", "🔄 Сменить голос"]:
        return
    
    status = await show_status(bot, msg.chat.id, "voice")
    try:
        # Скачиваем и распознаём голос
        file_path = await download_voice(bot, msg.voice.file_id)
        if not file_path:
            await msg.answer("❌ Не удалось скачать голосовое")
            return
        
        text = await transcribe_voice(file_path)
        if not text:
            await msg.answer("❌ Не удалось распознать речь")
            return
        await status.stop()
        # Показываем что распознали
        await msg.answer(f"📝 Ты сказал:\n<i>{text}</i>")
        
        # Обрабатываем как текст
        await process_voice_message(msg, state, text)
        
    except Exception as e:
        print(f"Voice recognition error: {e}")
        await msg.answer(f"❌ Ошибка: {str(e)[:100]}")
    finally:
        if status:
            await status.stop()


@router.message(VoiceSt.chat, F.text)
async def voice_chat_text(msg: Message, state: FSMContext):
    """Обработка текстового сообщения (бот отвечает голосом)"""
    if msg.text in ["🛑 Завершить", "🗑 Очистить", "🔄 Сменить голос"]:
        return
    
    await process_voice_message(msg, state, msg.text)
