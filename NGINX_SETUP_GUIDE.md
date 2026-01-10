# Nginx Setup Guide for soul-bot.ru

## ✅ Что уже сделано

### 1. Git Repository
- ✅ Проект сохранен в Git
- ✅ Все изменения закоммичены
- ✅ Код запушен на GitHub: https://github.com/Deniskript/Ai-bot-Emmanuil.git

### 2. Nginx Configuration
- ✅ Nginx установлен (версия 1.24.0)
- ✅ Certbot установлен (версия 2.9.0)
- ✅ Создана директория `/var/www/soul-bot/`
- ✅ Создана тестовая страница `index.html` с текстом "Soul Bot - Coming Soon"
- ✅ Создан конфиг `/etc/nginx/sites-available/soul-bot.ru`
- ✅ Сайт включен (symlink в sites-enabled)
- ✅ Nginx запущен и работает

---

## ⚠️ Требуется: Настройка DNS

Для получения SSL сертификата необходимо **настроить DNS записи** для домена soul-bot.ru.

### Шаги настройки DNS:

1. Зайдите в панель управления вашего регистратора домена (где куплен soul-bot.ru)

2. Добавьте следующие DNS записи:

```
Тип    Имя             Значение          TTL
----------------------------------------------------
A      @               147.45.100.46     3600
A      www             147.45.100.46     3600
```

**Где:**
- `@` — это корневой домен (soul-bot.ru)
- `www` — поддомен (www.soul-bot.ru)
- `147.45.100.46` — IP адрес вашего сервера

3. **Подождите 5-30 минут** для распространения DNS записей

4. Проверьте, что DNS работает:

```bash
# Проверка корневого домена
dig soul-bot.ru +short

# Проверка www поддомена
dig www.soul-bot.ru +short

# Оба должны вернуть: 147.45.100.46
```

Или используйте онлайн-сервис: https://dnschecker.org/

---

## 🔒 После настройки DNS: Получение SSL сертификата

После того как DNS записи будут работать, выполните команду для получения SSL:

```bash
certbot --nginx -d soul-bot.ru -d www.soul-bot.ru --non-interactive --agree-tos --redirect --register-unsafely-without-email
```

**Что сделает эта команда:**
- ✅ Получит бесплатный SSL сертификат от Let's Encrypt
- ✅ Автоматически настроит HTTPS в Nginx
- ✅ Настроит редирект с HTTP → HTTPS
- ✅ Перезагрузит Nginx с новой конфигурацией

**Или с указанием email (рекомендуется):**

```bash
certbot --nginx -d soul-bot.ru -d www.soul-bot.ru --email ваш-email@example.com --agree-tos --redirect --non-interactive
```

Email нужен для уведомлений об истечении сертификата.

---

## 📝 Полезные команды

### Проверка конфигурации Nginx
```bash
nginx -t
```

### Перезагрузка Nginx
```bash
systemctl reload nginx
```

### Проверка статуса Nginx
```bash
systemctl status nginx
```

### Просмотр логов
```bash
# Логи доступа
tail -f /var/log/nginx/soul-bot.ru_access.log

# Логи ошибок
tail -f /var/log/nginx/soul-bot.ru_error.log
```

### Обновление SSL сертификата (автоматическое)
Certbot автоматически обновляет сертификаты, но можно проверить:

```bash
# Тестовое обновление
certbot renew --dry-run

# Ручное обновление
certbot renew
```

---

## 📂 Файловая структура

```
/var/www/soul-bot/
└── index.html                          # Главная страница

/etc/nginx/
├── sites-available/
│   └── soul-bot.ru                     # Конфигурация сайта
└── sites-enabled/
    └── soul-bot.ru -> ../sites-available/soul-bot.ru

/var/log/nginx/
├── soul-bot.ru_access.log              # Логи доступа
└── soul-bot.ru_error.log               # Логи ошибок
```

---

## 🚀 После получения SSL

Сайт будет доступен по адресам:
- https://soul-bot.ru (основной)
- https://www.soul-bot.ru (с www)
- http://soul-bot.ru → автоматически перенаправит на HTTPS
- http://www.soul-bot.ru → автоматически перенаправит на HTTPS

Для обновления содержимого сайта просто редактируйте:
```bash
nano /var/www/soul-bot/index.html
```

---

## 🔧 Текущая конфигурация

**Сервер:** 147.45.100.46  
**Домен:** soul-bot.ru  
**Проект:** /root/ai-bot/  
**Web root:** /var/www/soul-bot/  
**Nginx версия:** 1.24.0  
**Certbot версия:** 2.9.0  

---

## ❓ Troubleshooting

### Проблема: "502 Bad Gateway"
- Проверьте, что приложение запущено
- Проверьте логи: `tail -f /var/log/nginx/soul-bot.ru_error.log`

### Проблема: "403 Forbidden"
- Проверьте права на файлы: `chmod 644 /var/www/soul-bot/index.html`
- Проверьте права на директорию: `chmod 755 /var/www/soul-bot/`

### Проблема: Сайт не работает через HTTPS
- Проверьте, что SSL сертификат получен: `certbot certificates`
- Проверьте конфигурацию: `nginx -t`

---

## 📞 Полезные ссылки

- Let's Encrypt: https://letsencrypt.org/
- Certbot документация: https://certbot.eff.org/
- Nginx документация: https://nginx.org/ru/docs/
- DNS Checker: https://dnschecker.org/
