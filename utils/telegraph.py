import asyncio
from telegraph import Telegraph

# Создаём аккаунт Telegraph
tg = Telegraph()
try:
    tg.create_account(short_name="AIBot", author_name="AI Assistant")
except:
    pass

async def create_telegraph_page(title: str, content: str) -> str:
    """Создание страницы в Telegraph для длинных ответов"""
    try:
        # Форматируем текст в HTML
        paragraphs = content.split('\n\n')
        html_parts = []
        
        for p in paragraphs:
            p = p.strip()
            if p:
                # Заменяем одинарные переносы на <br>
                p = p.replace('\n', '<br>')
                html_parts.append(f"<p>{p}</p>")
        
        html_content = ''.join(html_parts) if html_parts else f"<p>{content}</p>"
        
        # Создаём страницу в отдельном потоке
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: tg.create_page(
                title=title,
                html_content=html_content,
                author_name="AI Assistant"
            )
        )
        
        return f"https://telegra.ph/{response['path']}"
    except Exception as e:
        print(f"Telegraph error: {e}")
        return "https://telegra.ph/"
