"""
Утилиты для работы с диалогами
"""
from database.db import (
    create_conversation, 
    save_conversation_message,
    get_conversation
)
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# Текущие активные диалоги пользователей {user_id: conversation_id}
active_conversations = {}


async def start_conversation(user_id: int, bot: str) -> int:
    """Начать новый диалог"""
    conv_id = await create_conversation(user_id, bot)
    active_conversations[user_id] = conv_id
    return conv_id


async def save_message(user_id: int, role: str, content: str, bot: str, model: str = None):
    """Сохранить сообщение в диалог"""
    # Получаем или создаем диалог
    if user_id not in active_conversations:
        conv_id = await start_conversation(user_id, bot)
    else:
        conv_id = active_conversations[user_id]
        # Проверяем, существует ли диалог
        conv = await get_conversation(conv_id)
        if not conv:
            conv_id = await start_conversation(user_id, bot)
    
    # Сохраняем сообщение
    await save_conversation_message(conv_id, role, content, model)
    return conv_id


def get_chat_button(conv_id: int, response_length: int) -> InlineKeyboardMarkup:
    """
    Создать кнопку для просмотра диалога через Telegram Mini App
    
    Args:
        conv_id: ID диалога
        response_length: Длина ответа в символах
    
    Returns:
        InlineKeyboardMarkup с кнопкой для просмотра через WebApp
    """
    # Определяем текст кнопки в зависимости от длины ответа
    if response_length < 3000:
        button_text = "📜 Посмотреть весь диалог"
    else:
        button_text = "📜 Читать полностью"
    
    # Создаем кнопку с WebApp (открывается внутри Telegram)
    url = f"https://soul-bot.ru/chat/{conv_id}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, web_app=WebAppInfo(url=url))]
    ])
    
    return keyboard


def should_show_preview(content: str, max_length: int = 3000) -> tuple[bool, str]:
    """
    Проверить, нужно ли показывать превью вместо полного текста
    
    Args:
        content: Текст сообщения
        max_length: Максимальная длина для полного показа
    
    Returns:
        Tuple: (нужно_превью, текст_для_показа)
    """
    if len(content) <= max_length:
        return False, content
    
    # Показываем первые 800 символов + троеточие
    preview = content[:800].rstrip() + "...\n\n📖 Продолжение доступно по кнопке ниже"
    return True, preview


def clean_response(content: str) -> str:
    """
    Очистить ответ от служебных строк
    
    Args:
        content: Исходный текст
    
    Returns:
        Очищенный текст без "Модель: #Claude" и подобных строк
    """
    import re
    
    # Удаляем строки типа "Модель: #Claude"
    content = re.sub(r'Модель:\s*#\w+\s*', '', content)
    content = re.sub(r'Model:\s*#\w+\s*', '', content)
    
    return content.strip()


async def end_conversation(user_id: int):
    """Завершить текущий диалог пользователя"""
    if user_id in active_conversations:
        del active_conversations[user_id]
