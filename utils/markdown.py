"""
Утилиты для конвертации Markdown в HTML для Telegram
"""
import re


def md_to_html(text: str) -> str:
    """
    Конвертирует Markdown в HTML для Telegram
    
    Поддерживает:
    - **жирный** → <b>жирный</b>
    - *курсив* → <i>курсив</i>
    - `код` → <code>код</code>
    - ~~зачёркнутый~~ → <s>зачёркнутый</s>
    - __подчёркнутый__ → <u>подчёркнутый</u>
    """
    
    # Сохраняем уже существующие HTML теги
    # (чтобы не конвертировать дважды)
    
    # **жирный** → <b>жирный</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    
    # *курсив* → <i>курсив</i> (только если не часть **)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    
    # `код` → <code>код</code>
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    
    # ~~зачёркнутый~~ → <s>зачёркнутый</s>
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)
    
    # __подчёркнутый__ → <u>подчёркнутый</u>
    text = re.sub(r'__(.+?)__', r'<u>\1</u>', text)
    
    return text


def clean_html_for_telegram(text: str) -> str:
    """
    Очищает HTML для Telegram
    Удаляет неподдерживаемые теги и форматирование
    """
    # Удаляем неподдерживаемые теги
    text = re.sub(r'<(?!/?(?:b|strong|i|em|u|ins|s|strike|del|code|pre|a)\b)[^>]+>', '', text)
    
    # Заменяем <strong> на <b>
    text = text.replace('<strong>', '<b>').replace('</strong>', '</b>')
    
    # Заменяем <em> на <i>
    text = text.replace('<em>', '<i>').replace('</em>', '</i>')
    
    # Заменяем <ins> на <u>
    text = text.replace('<ins>', '<u>').replace('</ins>', '</u>')
    
    # Заменяем <strike> и <del> на <s>
    text = text.replace('<strike>', '<s>').replace('</strike>', '</s>')
    text = text.replace('<del>', '<s>').replace('</del>', '</s>')
    
    return text
