import aiohttp
import re
from typing import Optional


async def create_telegraph_page(title: str, content: str, author: str = "Душа AI") -> Optional[str]:
    """Создаёт страницу на Telegraph и возвращает URL"""
    
    # Конвертируем текст в Telegraph формат (Node)
    # Разбиваем по абзацам и форматируем
    paragraphs = content.split('\n\n')
    nodes = []
    
    for p in paragraphs:
        if not p.strip():
            continue
        
        # Обрабатываем заголовки
        if p.startswith('###'):
            nodes.append({"tag": "h4", "children": [p.replace('###', '').strip()]})
        elif p.startswith('##'):
            nodes.append({"tag": "h3", "children": [p.replace('##', '').strip()]})
        elif p.startswith('#'):
            nodes.append({"tag": "h3", "children": [p.replace('#', '').strip()]})
        # Обрабатываем списки
        elif p.strip().startswith('•') or p.strip().startswith('-') or p.strip().startswith('▸'):
            items = p.strip().split('\n')
            for item in items:
                clean = re.sub(r'^[•\-▸]\s*', '', item.strip())
                if clean:
                    nodes.append({"tag": "p", "children": ["• " + clean]})
        # Обрабатываем код
        elif '```' in p:
            code = p.replace('```', '').strip()
            nodes.append({"tag": "pre", "children": [code]})
        else:
            # Обычный параграф - обрабатываем жирный текст
            text = p.strip()
            # Заменяем **текст** на жирный
            if '**' in text:
                parts = []
                segments = re.split(r'\*\*(.+?)\*\*', text)
                for i, seg in enumerate(segments):
                    if i % 2 == 1:  # Нечётные - жирный текст
                        parts.append({"tag": "strong", "children": [seg]})
                    elif seg:
                        parts.append(seg)
                nodes.append({"tag": "p", "children": parts if parts else [text]})
            else:
                nodes.append({"tag": "p", "children": [text]})
    
    if not nodes:
        nodes = [{"tag": "p", "children": [content]}]
    
    try:
        async with aiohttp.ClientSession() as session:
            # Создаём аккаунт (или используем существующий)
            acc_data = {
                "short_name": author,
                "author_name": author
            }
            async with session.post(
                "https://api.telegra.ph/createAccount",
                json=acc_data
            ) as resp:
                acc_result = await resp.json()
                if not acc_result.get('ok'):
                    return None
                access_token = acc_result['result']['access_token']
            
            # Создаём страницу
            page_data = {
                "access_token": access_token,
                "title": title[:256],  # Лимит Telegraph
                "author_name": author,
                "content": nodes
            }
            async with session.post(
                "https://api.telegra.ph/createPage",
                json=page_data
            ) as resp:
                page_result = await resp.json()
                if page_result.get('ok'):
                    return page_result['result']['url']
                return None
                
    except Exception as e:
        print(f"Telegraph error: {e}")
        return None


def make_preview(text: str, max_len: int = 800) -> str:
    """Создаёт превью текста"""
    if len(text) <= max_len:
        return text
    
    # Ищем конец предложения до лимита
    cut = text[:max_len]
    last_dot = max(cut.rfind('.'), cut.rfind('!'), cut.rfind('?'))
    
    if last_dot > max_len // 2:
        return text[:last_dot + 1]
    
    # Иначе режем по пробелу
    last_space = cut.rfind(' ')
    if last_space > 0:
        return text[:last_space] + "..."
    
    return cut + "..."
