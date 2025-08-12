# 🔒 Руководство по безопасности NEWSMAKER

## 📋 Обзор системы безопасности

NEWSMAKER v2.3.3 включает комплексную систему защиты, соответствующую современным стандартам безопасности веб-приложений.

## 🛡️ Реализованные механизмы защиты

### 1. Аутентификация и авторизация

#### HTTP Basic + Session Authentication
- **Файл**: `auth_middleware.py`
- **Дефолтный логин**: admin
- **Пароль**: генерируется автоматически при первом запуске
- **Сессии**: таймаут 1 час с автоматическим продлением при активности

#### Rate Limiting
- Максимум 5 попыток входа с одного IP
- Блокировка на 5 минут при превышении
- Логирование всех попыток с IP адресами

#### Управление пользователями
```python
from auth_middleware import update_user_password
update_user_password('admin', 'новый_безопасный_пароль')
```

### 2. Защита от CSRF атак

#### CSRF токены
- **Файл**: `csrf_protection.py`
- HMAC подписи для всех токенов
- Автоматическая ротация токенов
- Проверка для всех POST/PUT/DELETE запросов

#### Использование в JavaScript
```javascript
// Получение токена из мета-тега
const token = document.querySelector('meta[name="csrf-token"]').content;

// Отправка с токеном
fetch('/api/config', {
    method: 'POST',
    headers: {
        'X-CSRF-Token': token
    }
});
```

### 3. Шифрование данных

#### AES-256 шифрование
- **Файл**: `encryption_utils.py`
- Автоматическая генерация ключей
- Безопасное хранение API ключей
- Поддержка ротации ключей

#### Миграция API ключей
```python
from encryption_utils import migrate_env_to_encrypted
migrate_env_to_encrypted()  # Переносит ключи из .env в зашифрованное хранилище
```

### 4. Безопасная сериализация

#### Защита от RCE
- **Файл**: `cache_manager.py`
- Полный отказ от pickle
- Использование только JSON
- Валидация всех десериализуемых данных

## 🔧 Настройка безопасности

### Первый запуск

1. **Запустите веб-интерфейс**:
```bash
python web_config_app.py
```

2. **Скопируйте пароль из консоли**:
```
================================================
SECURITY WARNING!
Default admin password: <случайный_пароль>
Change it immediately in .auth.json file
================================================
```

3. **Смените дефолтный пароль**:
Отредактируйте `.auth.json` или используйте функцию `update_user_password()`

### Рекомендуемые настройки

#### Linux/Mac
```bash
# Установка прав доступа
chmod 600 .auth.json
chmod 600 .encryption_key
chmod 600 .secure_config.enc
```

#### Windows
- Используйте свойства файла → Безопасность
- Оставьте доступ только для текущего пользователя

### Настройка HTTPS (рекомендуется)

#### Nginx reverse proxy
```nginx
server {
    listen 443 ssl http2;
    server_name newsmaker.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 📊 Соответствие стандартам

### OWASP Top 10 (2021)

| Угроза | Статус | Меры защиты |
|--------|---------|-------------|
| A01: Broken Access Control | ✅ Защищено | Аутентификация, роли, сессии |
| A02: Cryptographic Failures | ✅ Защищено | AES-256, безопасное хранение |
| A03: Injection | ✅ Защищено | Валидация, санитизация, JSON-only |
| A04: Insecure Design | ✅ Защищено | Security by design, типизация |
| A05: Security Misconfiguration | ⚠️ Частично | Требует HTTPS настройки |
| A06: Vulnerable Components | ✅ Защищено | Все зависимости обновлены |
| A07: Authentication Failures | ✅ Защищено | Rate limiting, сессии |
| A08: Software and Data Integrity | ✅ Защищено | Удален pickle, валидация |
| A09: Security Logging | ✅ Защищено | Детальное логирование |
| A10: SSRF | ✅ Защищено | Валидация URL, таймауты |

### PCI DSS совместимость

- ✅ Шифрование чувствительных данных
- ✅ Контроль доступа
- ✅ Регулярные обновления
- ✅ Логирование и мониторинг
- ⚠️ Требуется: сетевая сегментация, регулярный аудит

## 🚨 Реагирование на инциденты

### При подозрении на взлом

1. **Немедленно смените все пароли**:
```python
from auth_middleware import update_user_password
update_user_password('admin', 'новый_сложный_пароль')
```

2. **Ротируйте ключи шифрования**:
```python
from encryption_utils import encryption_manager
encryption_manager.rotate_key()
```

3. **Проверьте логи**:
- `logs/newsmaker.log` - основной лог
- `logs/errors/` - критические ошибки
- `.auth.json` - попытки входа

4. **Смените API ключи**:
- Perplexity API
- OpenAI API
- Telegram Bot Token

### Мониторинг безопасности

#### Что проверять ежедневно:
- Количество неудачных попыток входа
- Новые IP адреса в логах
- Необычная активность API

#### Что проверять еженедельно:
- Обновления зависимостей: `pip list --outdated`
- Размер логов и их ротация
- Права доступа к файлам

## 🔐 Чеклист безопасности

### Обязательные действия
- [ ] Сменить дефолтный пароль admin
- [ ] Настроить права доступа к файлам (chmod 600)
- [ ] Мигрировать API ключи в зашифрованное хранилище
- [ ] Удалить API ключи из .env файла
- [ ] Настроить регулярное резервное копирование

### Рекомендуемые действия
- [ ] Настроить HTTPS через reverse proxy
- [ ] Создать отдельных пользователей для команды
- [ ] Настроить файрвол (разрешить только нужные порты)
- [ ] Включить автоматические обновления безопасности
- [ ] Настроить мониторинг и алерты

### Продвинутые меры
- [ ] Внедрить 2FA (двухфакторную аутентификацию)
- [ ] Настроить SIEM для централизованного мониторинга
- [ ] Провести penetration testing
- [ ] Получить SSL сертификат от доверенного CA
- [ ] Настроить WAF (Web Application Firewall)

## 📞 Контакты для сообщений о безопасности

При обнаружении уязвимостей:
1. НЕ публикуйте информацию публично
2. Отправьте детали на security@newsmaker.example
3. Используйте PGP для шифрования если возможно

## 📚 Дополнительные ресурсы

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Guidelines](https://python.readthedocs.io/en/latest/library/security_warnings.html)
- [Telegram Bot Security](https://core.telegram.org/bots#botfather-commands)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/3.0.x/security/)

---

*Последнее обновление: Август 2025 | Версия 2.3.3*