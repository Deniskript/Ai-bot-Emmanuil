import aiohttp
import re
from typing import Optional

# Допустимые HTML теги для Telegram
ALLOWED_TAGS = {'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'code', 'pre', 'a', 'tg-spoiler'}

def clean_html_for_telegram(text: str) -> str:
    """Очищает текст от невалидных HTML-тегов для Telegram"""
    
    # Удаляем все HTML-теги кроме разрешённых
    def replace_tag(match):
        tag = match.group(1).lower().split()[0]  # Берём имя тега без атрибутов
        if tag in ALLOWED_TAGS or tag.startswith('/') and tag[1:] in ALLOWED_TAGS:
            return match.group(0)  # Оставляем разрешённый тег
        return ''  # Удаляем неразрешённый тег
    
    # Ищем все теги
    result = re.sub(r'<(/?\w+)[^>]*>', replace_tag, text)
    
    # Экранируем специальные символы вне тегов
    # (но это сложно, проще удалить все неразрешённые теги)
    
    return result

def escape_html(text: str) -> str:
    """Полностью экранирует HTML"""
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;'))

async def create_telegraph_page(title: str, content: str, author: str = "Soul AI") -> Optional[str]:
    """Создаёт страницу на Telegraph и возвращает URL"""
    
    paragraphs = content.split('\n\n')
    nodes = []
    
    for p in paragraphs:
        if not p.strip():
            continue
        
        # Очищаем от HTML-тегов для Telegraph
        p_clean = re.sub(r'<[^>]+>', '', p)
        
        # Обрабатываем заголовки
        if p_clean.startswith('###'):
            nodes.append({"tag": "h4", "children": [p_clean.replace('###', '').strip()]})
        elif p_clean.startswith('##'):
            nodes.append({"tag": "h3", "children": [p_clean.replace('##', '').strip()]})
        elif p_clean.startswith('#'):
            nodes.append({"tag": "h3", "children": [p_clean.replace('#', '').strip()]})
        # Обрабатываем списки
        elif p_clean.strip().startswith('•') or p_clean.strip().startswith('-') or p_clean.strip().startswith('▸'):
            items = p_clean.strip().split('\n')
            for item in items:
                clean = re.sub(r'^[•\-▸]\s*', '', item.strip())
                if clean:
                    nodes.append({"tag": "p", "children": ["• " + clean]})
        # Обрабатываем код
        elif '```' in p_clean:
            code = p_clean.replace('```', '').strip()
            nodes.append({"tag": "pre", "children": [code]})
        else:
            text = p_clean.strip()
            # Заменяем **текст** на жирный
            if '**' in text:
                parts = []
                segments = re.split(r'\*\*(.+?)\*\*', text)
                for i, seg in enumerate(segments):
                    if i % 2 == 1:
                        parts.append({"tag": "strong", "children": [seg]})
                    elif seg:
                        parts.append(seg)
                nodes.append({"tag": "p", "children": parts if parts else [text]})
            else:
                nodes.append({"tag": "p", "children": [text]})
    
    if not nodes:
        nodes = [{"tag": "p", "children": [content[:4000]]}]
    
    try:
        async with aiohttp.ClientSession() as session:
            acc_data = {"short_name": author, "author_name": author}
            async with session.post("https://api.telegra.ph/createAccount", json=acc_data) as resp:
                acc_result = await resp.json()
                if not acc_result.get('ok'):
                    return None
                access_token = acc_result['result']['access_token']
            
            page_data = {
                "access_token": access_token,
                "title": title[:256],
                "author_name": author,
                "content": nodes
            }
            async with session.post("https://api.telegra.ph/createPage", json=page_data) as resp:
                page_result = await resp.json()
                if page_result.get('ok'):
                    return page_result['result']['url']
                return None
                
    except Exception as e:
        print(f"Telegraph error: {e}")
        return None

def make_preview(text: str, max_len: int = 800) -> str:
    """Создаёт превью текста, очищенное от невалидного HTML"""
    
    # Сначала очищаем от невалидных тегов
    text = clean_html_for_telegram(text)
    
    if len(text) <= max_len:
        return text
    
    cut = text[:max_len]
    last_dot = max(cut.rfind('.'), cut.rfind('!'), cut.rfind('?'))
    
    if last_dot > max_len // 2:
        return text[:last_dot + 1]
    
    last_space = cut.rfind(' ')
    if last_space > 0:
        return text[:last_space] + "..."
    
    return cut + "..."
