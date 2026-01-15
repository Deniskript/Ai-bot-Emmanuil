# 📸 ЛОГИКА ОБРАБОТКИ ФОТОГРАФИЙ ДЛЯ ТАРО И ГАДАНИЙ

**Полный путь от загрузки до результата**

---

## 🔄 ОБЩАЯ СХЕМА

```
[Пользователь] → [WebApp Frontend] → [Flask Backend] → [AI Vision API] → [PostgreSQL] → [Результат]
```

---

## 📱 ШАГИ ОБРАБОТКИ

### 1️⃣ FRONTEND: Загрузка фото (JavaScript)

#### Таро: `templates/magic_tarot.html` (строки 485-523)
```javascript
async function analyzePhoto(event) {
    const btn = event.target;
    const file = document.getElementById('photo-input').files[0];  // Получить файл
    
    if (!file) {
        showToast('❌ Загрузите фото', 'error');
        return;
    }
    
    setButtonLoading(btn, true);
    showProcessing('Анализирую фото...');  // Анимация
    
    // FileReader - стандартный JavaScript API для чтения файлов
    const reader = new FileReader();
    reader.onload = async () => {
        const base64 = reader.result;  // "data:image/jpeg;base64,/9j/4AAQ..."
        
        // Отправка на backend
        const res = await fetch('/magic/tarot/photo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                user_id: userId, 
                image: base64  // Полная Data URI с base64
            })
        });
        
        const data = await res.json();
        
        if (data.success) {
            setResult(data.text);  // Показать результат
            showToast('✅ Анализ завершён', 'success');
        } else {
            showToast(`❌ Ошибка: ${data.error}`, 'error');
        }
    };
    
    // Запустить чтение файла как Data URL (base64)
    reader.readAsDataURL(file);
}
```

#### Гадания: `templates/magic_divination.html` (строки 403-442)
```javascript
async function analyzePhoto(event) {
    const btn = event.target;
    const file = document.getElementById('photo-input').files[0];
    const divType = document.getElementById('divination-type').value;  // palm, face, coffee
    
    if (!file) {
        showToast('❌ Загрузите фото', 'error');
        return;
    }
    
    setButtonLoading(btn, true);
    showProcessing('Анализирую фото...');
    
    const reader = new FileReader();
    reader.onload = async () => {
        const base64 = reader.result;
        
        const res = await fetch('/magic/divination/photo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                user_id: userId, 
                type: divType,      // ← РАЗНИЦА: передаётся тип гадания
                image: base64 
            })
        });
        
        const data = await res.json();
        
        if (data.success) {
            setResult(data.text);
            showToast('✅ Анализ завершён', 'success');
        }
    };
    
    reader.readAsDataURL(file);
}
```

**Ключевые моменты:**
- `FileReader.readAsDataURL()` - конвертирует файл в base64 Data URI
- Формат: `"data:image/jpeg;base64,/9j/4AAQSkZJRgABA..."`
- Отправляется как JSON в теле POST запроса

---

### 2️⃣ BACKEND: Приём и валидация (Flask)

#### Таро endpoint: `web_app.py` (строки 938-959)
```python
@app.route('/magic/tarot/photo', methods=['POST'])
def magic_tarot_photo():
    """Анализ фото расклада"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        image = data.get('image')  # Data URI base64
        
        if not user_id or not image:
            return jsonify({'success': False, 'error': 'user_id and image required'}), 400

        # Отправить на AI Vision API
        text = run_async(analyze_image_with_prompt(image, TAROT_PHOTO_PROMPT))
        
        # Сохранить в БД
        ensure_pool_initialized()
        run_async(postgres_db.save_magic_tarot_log(
            user_id=int(user_id),
            spread_type="photo",
            question=None,
            image_used=True,
            result_text=text
        ))
        
        return jsonify({'success': True, 'text': text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

#### Гадания endpoint: `web_app.py` (строки 962-987)
```python
@app.route('/magic/divination/photo', methods=['POST'])
def magic_divination_photo():
    """Анализ фото для гаданий"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        image = data.get('image')
        dtype = data.get('type', 'palm')  # palm, face, coffee
        
        if not user_id or not image:
            return jsonify({'success': False, 'error': 'user_id and image required'}), 400

        # Выбор промпта в зависимости от типа гадания
        prompt_map = {
            "palm": PALM_PROMPT,     # Хиромантия
            "face": FACE_PROMPT,     # Физиогномика
            "coffee": COFFEE_PROMPT  # Кофейная гуща
        }
        prompt = prompt_map.get(dtype, PALM_PROMPT)
        
        # Отправить на AI Vision API
        text = run_async(analyze_image_with_prompt(image, prompt))
        
        # Сохранить в БД
        ensure_pool_initialized()
        run_async(postgres_db.save_magic_divination_log(
            user_id=int(user_id),
            divination_type=dtype,
            question=None,
            image_used=True,
            result_text=text
        ))
        
        return jsonify({'success': True, 'text': text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Ключевые моменты:**
- Валидация: проверка наличия `user_id` и `image`
- Выбор промпта в зависимости от типа
- Асинхронный вызов AI API через `run_async()`
- Сохранение результата в PostgreSQL

---

### 3️⃣ AI VISION API: Обработка изображения

#### Файл: `utils/magic_vision.py`

```python
async def analyze_image_with_prompt(image_base64: str, prompt: str) -> str:
    """Анализ изображения: OpenRouter Vision -> VseGPT fallback."""
    if not image_base64:
        raise ValueError("image_base64 is required")
    
    try:
        # Попытка 1: OpenRouter Vision (основной)
        return await _openrouter_vision(image_base64, prompt)
    except Exception:
        # Попытка 2: VseGPT fallback (если OpenRouter не работает)
        return await _vsegpt_vision(image_base64, prompt)
```

#### Способ 1: OpenRouter Vision (строки 15-25)
```python
async def _openrouter_vision(image_base64: str, prompt: str) -> str:
    # Убрать префикс "data:image/jpeg;base64," если есть
    image_clean = _strip_data_url(image_base64)
    
    # Вызов OpenRouter API через utils/openrouter.py
    text, tokens = await openrouter_ask(
        [{"role": "user", "content": prompt}],
        model="openai/gpt-4o-mini",  # Модель с поддержкой Vision
        image_base64=image_clean,    # Чистый base64 без префикса
        max_tokens=1200
    )
    
    if tokens == 0 and isinstance(text, str) and text.startswith("Ошибка"):
        raise Exception(text)
    
    return text
```

#### Способ 2: VseGPT Vision (строки 28-62)
```python
async def _vsegpt_vision(image_base64: str, prompt: str) -> str:
    if not VSEGPT_API_KEY:
        raise Exception("VSEGPT_API_KEY not set")
    
    # Формат OpenAI-compatible
    content = [
        {"type": "text", "text": prompt},
        {
            "type": "image_url",
            "image_url": {
                "url": image_base64,  # Data URI полностью
                "detail": "high"
            }
        }
    ]
    
    headers = {
        "Authorization": f"Bearer {VSEGPT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o",  # VseGPT использует GPT-4o
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 1200,
        "temperature": 0.8
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{VSEGPT_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=180)  # 3 минуты
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise Exception(f"VseGPT Error {resp.status}: {error}")
            
            result = await resp.json()
            return result["choices"][0]["message"]["content"].strip()
```

#### Вспомогательная функция: `_strip_data_url` (строки 9-12)
```python
def _strip_data_url(image_base64: str) -> str:
    """Убрать префикс data:image/... из base64"""
    if image_base64.startswith("data:image"):
        return image_base64.split(",", 1)[-1]  # Взять только base64 часть
    return image_base64
```

**Ключевые моменты:**
- Два способа обработки: OpenRouter (основной) + VseGPT (fallback)
- OpenRouter использует `gpt-4o-mini` (дешевле)
- VseGPT использует `gpt-4o` (дороже, но надёжнее)
- Таймаут 180 секунд (3 минуты)
- Убирается префикс `data:image/...;base64,` для OpenRouter

---

## 🎯 ПРОМПТЫ ДЛЯ AI

### Файл: `prompts/magic_prompts.py`

#### 1. Таро фото (строки 18-22)
```python
TAROT_PHOTO_PROMPT = (
    "Ты эксперт Таро. На фото расклад карт. "
    "Опиши каждую карту, её значение и общий смысл расклада. "
    "Будь проницательным и конкретным."
)
```

#### 2. Хиромантия (строки 24-30)
```python
PALM_PROMPT = (
    "Ты хиромант с многолетним опытом. "
    "Внимательно изучи ладонь на фото: линии жизни, ума, сердца, судьбы. "
    "Опиши характер человека, его судьбу, здоровье, любовь, карьеру. "
    "Дай предсказания и советы."
)
```

#### 3. Физиогномика (строки 32-37)
```python
FACE_PROMPT = (
    "Ты физиогномист. "
    "Изучи черты лица на фото: форму лица, глаз, носа, губ. "
    "Опиши характер, темперамент, жизненный путь человека. "
    "Дай рекомендации."
)
```

#### 4. Кофейная гуща (строки 39-45)
```python
COFFEE_PROMPT = (
    "Ты мастер гадания на кофейной гуще. "
    "Изучи узоры в чашке: символы, фигуры, линии. "
    "Расскажи о будущем: любви, работе, здоровье. "
    "Будь загадочным и точным."
)
```

---

## 💾 СОХРАНЕНИЕ В БАЗУ ДАННЫХ

### Таро лог
```python
# database/postgres_db.py
async def save_magic_tarot_log(
    user_id: int,
    spread_type: str,        # "photo"
    question: str = None,
    image_used: bool = False,  # True для фото
    result_text: str = ""
) -> None:
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO magic_tarot_logs
            (user_id, spread_type, question, image_used, result_text)
            VALUES ($1, $2, $3, $4, $5)
            """,
            int(user_id), spread_type, question, bool(image_used), result_text
        )
```

### Гадания лог
```python
# database/postgres_db.py
async def save_magic_divination_log(
    user_id: int,
    divination_type: str,    # "palm", "face", "coffee"
    question: str = None,
    image_used: bool = False,  # True для фото
    result_text: str = ""
) -> None:
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO magic_divination_logs
            (user_id, divination_type, question, image_used, result_text)
            VALUES ($1, $2, $3, $4, $5)
            """,
            int(user_id), divination_type, question, bool(image_used), result_text
        )
```

---

## 🔄 ПОЛНЫЙ ПУТЬ ДАННЫХ

### Таро
```
[Фото] 
  ↓ FileReader.readAsDataURL()
[Base64 Data URI: "data:image/jpeg;base64,/9j/..."]
  ↓ POST /magic/tarot/photo
[Flask: magic_tarot_photo()]
  ↓ analyze_image_with_prompt(image, TAROT_PHOTO_PROMPT)
[utils/magic_vision.py]
  ↓ _openrouter_vision() или _vsegpt_vision()
[OpenRouter API: gpt-4o-mini] или [VseGPT API: gpt-4o]
  ↓ Анализ изображения + промпт
[Текстовый результат]
  ↓ save_magic_tarot_log()
[PostgreSQL: magic_tarot_logs]
  ↓ return jsonify({'success': True, 'text': text})
[Frontend: setResult(data.text)]
  ↓ Отображение результата пользователю
```

### Гадания (аналогично, но с выбором промпта)
```
[Фото]
  ↓ FileReader.readAsDataURL()
[Base64 Data URI]
  ↓ POST /magic/divination/photo + type="palm"|"face"|"coffee"
[Flask: magic_divination_photo()]
  ↓ Выбор промпта: PALM_PROMPT | FACE_PROMPT | COFFEE_PROMPT
  ↓ analyze_image_with_prompt(image, prompt)
[OpenRouter/VseGPT API]
  ↓ Анализ
[Результат]
  ↓ save_magic_divination_log()
[PostgreSQL: magic_divination_logs]
  ↓ JSON response
[Frontend: Отображение]
```

---

## ⚙️ КОНФИГУРАЦИЯ

### Необходимые переменные в `.env`:
```bash
# OpenRouter (основной)
OPENROUTER_API_KEY=sk-or-v1-...

# VseGPT (fallback)
VSEGPT_API_KEY=vst-...
VSEGPT_BASE_URL=https://api.vsegpt.ru/v1

# Или ProxyAPI для OpenAI
OPENAI_API_KEY=sk-...
```

---

## 🐛 ОБРАБОТКА ОШИБОК

### Frontend
```javascript
try {
    const res = await fetch('/magic/tarot/photo', {...});
    const data = await res.json();
    
    if (data.success) {
        setResult(data.text);
        showToast('✅ Анализ завершён', 'success');
    } else {
        showToast(`❌ Ошибка: ${data.error}`, 'error');
    }
} catch (e) {
    console.error('Photo analysis error:', e);
    showToast('❌ Ошибка сети', 'error');
}
```

### Backend
```python
try:
    # ... обработка ...
    return jsonify({'success': True, 'text': text})
except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
```

### AI API (cascade fallback)
```python
try:
    return await _openrouter_vision(image, prompt)  # Попытка 1
except Exception:
    return await _vsegpt_vision(image, prompt)      # Попытка 2
```

---

## 📊 ФОРМАТЫ ДАННЫХ

### Request (Frontend → Backend)
```json
{
  "user_id": 123,
  "type": "palm",  // только для гаданий
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA..."
}
```

### Response (Backend → Frontend)
```json
{
  "success": true,
  "text": "🖐️ Анализ ладони:\n\nЛиния жизни: четкая и длинная..."
}
```

### Ошибка
```json
{
  "success": false,
  "error": "VseGPT Error 400: Invalid image data."
}
```

---

## 🎯 КЛЮЧЕВЫЕ ОСОБЕННОСТИ

1. **FileReader API** - стандартный JavaScript для чтения файлов
2. **Base64 Data URI** - универсальный формат передачи изображений
3. **Cascade Fallback** - OpenRouter → VseGPT для надёжности
4. **Разные модели** - gpt-4o-mini (дешевле) vs gpt-4o (надёжнее)
5. **Разные промпты** - специализированные для каждого типа гадания
6. **Логирование** - все запросы сохраняются в PostgreSQL
7. **Асинхронность** - `async/await` для производительности
8. **Таймауты** - 180 секунд на обработку изображения
9. **Обработка ошибок** - на каждом уровне (Frontend/Backend/API)

---

## 🔍 ОТЛАДКА

### Проверить что фото загружается:
```javascript
console.log('File:', file);
console.log('Base64 length:', base64.length);
```

### Проверить что backend получает:
```python
print(f"Image length: {len(image)}")
print(f"Image starts with: {image[:50]}")
```

### Проверить API вызов:
```python
print(f"Prompt: {prompt[:100]}")
print(f"Model: openai/gpt-4o-mini")
```

---

**Дата документации:** 2026-01-15  
**Статус:** ✅ Полностью работает
