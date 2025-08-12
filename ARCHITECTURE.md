# NEWSMAKER - Архитектура системы

## 📐 Архитектурные принципы

### Основные принципы
1. **Разделение ответственности** - каждый модуль решает одну задачу
2. **Типобезопасность** - использование TypedDict для всех структур
3. **Отказоустойчивость** - graceful degradation и retry логика
4. **Модульность** - слабая связанность компонентов
5. **Безопасность** - валидация всех входных данных

### Архитектурный паттерн
**Pipeline Architecture** с элементами **Event-Driven Design**

```
[Сбор] → [Обработка] → [Генерация] → [Хранение] → [Публикация]
   ↓          ↓             ↓            ↓             ↓
[Logger] [Validator]   [Retry]      [FileLock]   [Antidupe]
```

## 🏛 Слои архитектуры

### 1. Presentation Layer (Представление)
```
├── main.py                 # CLI интерфейс
├── run_with_validation.py  # Валидированный запуск
└── utils/
    └── show_full_prompt.py # Отладочные утилиты
```

**Ответственность:**
- Обработка CLI аргументов
- Валидация входных параметров
- Маршрутизация команд
- Отображение результатов

### 2. Business Logic Layer (Бизнес-логика)
```
├── news_collector.py      # Сбор новостей
├── news_publisher.py      # Публикация
└── news_scheduler.py      # Планировщик
```

**Ответственность:**
- Оркестрация процессов
- Применение бизнес-правил
- Управление workflow
- Обработка расписания

### 3. Service Layer (Сервисы)
```
├── perplexity_client.py   # Perplexity API
├── openai_client.py       # OpenAI API
├── telegram_client.py     # Telegram API
└── prompts.py            # Промпт-инжиниринг
```

**Ответственность:**
- Интеграция с внешними API
- Абстракция протоколов
- Обработка ответов
- Управление сессиями

### 4. Infrastructure Layer (Инфраструктура)
```
├── types_models.py        # Типы данных
├── validation.py         # Валидация
├── timezone_utils.py     # Часовые пояса
├── file_utils.py        # Файловые операции
├── error_handler.py     # Обработка ошибок и retry
├── logger_setup.py      # Унифицированное логирование
└── config.py           # Конфигурация
```

**Ответственность:**
- Типизация данных
- Валидация и верификация
- Низкоуровневые операции
- Кросс-функциональные сервисы

## 🔄 Потоки данных

### Основной поток (Daily Flow)
```mermaid
graph LR
    A[08:30 Trigger] --> B[News Collector]
    B --> C[Perplexity API]
    C --> D[Parse & Validate]
    D --> E[Generate Images]
    E --> F[Save to Files]
    F --> G[Schedule Publications]
    G --> H[09:05-21:07 Publish]
```

### Поток сбора новостей
```python
1. news_collector.collect_daily_news()
   ├── perplexity_client.get_legal_updates()
   │   └── API запрос с промптом для 7 новостей
   ├── parse_collection_response()
   │   ├── Извлечение 7 новостей
   │   └── Валидация каждой новости
   ├── generate_images_for_news()
   │   └── openai_client.generate_comic()
   └── save_daily_news()
       └── file_utils.safe_json_write()
```

### Поток публикации
```python
1. news_publisher.publish_next_scheduled()
   ├── load_daily_news()
   │   └── file_utils.safe_json_read()
   ├── find_next_to_publish()
   │   └── Проверка расписания
   ├── telegram_client.send_legal_update()
   │   ├── Антидубликатор
   │   └── Отправка в канал
   └── update_publication_status()
       └── file_utils.safe_json_write()
```

## 📊 Модели данных

### NewsItem
```python
class NewsItem(TypedDict):
    id: str                    # Уникальный идентификатор
    priority: int              # 1-7 (критичность)
    title: str                 # Заголовок новости
    content: str              # Полный текст
    sources: List[str]        # URL источников
    scheduled_time: str       # HH:MM публикации
    collected_at: str         # ISO datetime сбора
    published: bool           # Статус публикации
    publication_attempts: int  # Счетчик попыток
    image_path: str           # Путь к изображению
    image_generated: bool     # Флаг генерации
    image_size: int           # Размер в байтах
```

### NewsFileData
```python
class NewsFileData(TypedDict):
    date: str                 # YYYY-MM-DD
    collected_at: str        # ISO datetime
    total_news: int          # Количество (7)
    news: List[NewsItem]     # Массив новостей
```

## 🔐 Безопасность

### Security Layer (Обновлено в v2.3.4)

#### Модули безопасности
```
security/
├── auth_middleware.py      # HTTP аутентификация и сессии
│   ├── AuthManager        # Управление пользователями
│   ├── check_auth()       # Проверка учетных данных
│   ├── rate_limiting()    # Защита от брутфорса
│   └── @requires_auth     # Декоратор защиты роутов
├── csrf_protection.py      # CSRF защита (АКТИВНА в v2.3.4)
│   ├── CSRFProtection     # Менеджер токенов
│   ├── generate_token()   # HMAC подписи
│   ├── validate_token()   # Проверка валидности
│   └── @csrf_protect      # Декоратор для POST/PUT/DELETE
├── encryption_utils.py     # Шифрование данных
│   ├── EncryptionManager  # AES-256 через Fernet
│   ├── encrypt_string()   # Шифрование строк
│   ├── SecureConfig       # Защищенное хранилище
│   └── migrate_env_to_encrypted()  # Миграция ключей
└── cache_manager.py        # Безопасное кеширование
    └── JSON-only          # Удален pickle (RCE защита)
```

### Уровни защиты

#### 1. Аутентификация и авторизация
- HTTP Basic + Session auth
- Rate limiting (5 попыток, блокировка 5 мин)
- Роли пользователей (admin/user)
- Автоматическая генерация паролей

#### 2. Защита от атак
- CSRF токены для всех изменений (АКТИВНО с v2.3.4)
- Path Traversal защита через validate_profile_name()
- Code Injection защита через safe_python_string()
- Валидация конфигурации через validate_config_value()
- Санитизация входных данных
- Безопасная сериализация (JSON only)
- Маскирование API ключей в логах

#### 3. Шифрование
- AES-256 для API ключей
- Secure storage с правами 0600
- Ротация ключей шифрования
- Миграция из plaintext

#### 4. Типизация (Compile-time)
- TypedDict для всех структур
- Type hints для функций
- Enums для констант

#### 5. Валидация (Runtime)
- Входные параметры
- API ответы
- Файловые данные
- Конфигурация

#### 6. Изоляция (Process)
- Блокировки файлов
- Атомарные операции
- Временные файлы

#### 7. Мониторинг (Observability)
- Детальное логирование
- Метрики операций
- История публикаций
- Аудит входов в систему

### Защита от сбоев

```python
# Retry механизм
@retry(max_attempts=3, delay=30)
def api_call():
    ...

# Graceful degradation
try:
    image = generate_image()
except Exception:
    image = None  # Публикуем без изображения

# File locking
with FileLock(filepath):
    data = read_file()
    write_file(data)
```

## 🎯 Паттерны проектирования

### 1. Repository Pattern
```python
# file_utils.py - абстракция хранилища
def safe_json_read(filepath) -> Any
def safe_json_write(filepath, data) -> bool
```

### 2. Factory Pattern
```python
# prompts.py - фабрика промптов
def get_perplexity_daily_collection_prompt()
def get_openai_comic_prompt(context, style)
```

### 3. Strategy Pattern
```python
# main.py - прямое использование планировщика
from news_scheduler import NewsmakerScheduler as DirectNewsScheduler
scheduler = DirectNewsScheduler()
```

### 4. Decorator Pattern
```python
# validation.py - декораторы валидации
@validate_input
def process_news(news_data):
    ...
```

## 🚦 Жизненный цикл

### Инициализация
1. Загрузка конфигурации
2. Валидация окружения
3. Создание директорий
4. Инициализация логов

### Ежедневный цикл
1. **08:30** - Триггер сбора
2. **08:31** - Запрос к Perplexity
3. **08:33** - Парсинг и валидация
4. **08:35** - Начало генерации изображений
5. **08:55** - Сохранение данных
6. **09:05-21:07** - Публикации по расписанию

### Завершение
1. Финализация логов
2. Очистка временных файлов
3. Сохранение статистики

## 📈 Масштабирование

### Горизонтальное
- Несколько инстансов для разных каналов
- Распределенные блокировки через Redis
- Очередь задач через RabbitMQ

### Вертикальное
- Увеличение MAX_NEWS_PER_DAY
- Параллельная генерация изображений
- Кеширование API ответов

## 🔍 Диагностика

### Точки мониторинга
```python
# Метрики сбора
- collection_duration
- news_parsed_count
- validation_errors

# Метрики генерации
- image_generation_time
- image_size_bytes
- generation_failures

# Метрики публикации  
- publication_latency
- delivery_success_rate
- duplicate_detections
```

### Healthcheck endpoints
```python
def check_api_connectivity():
    perplexity: bool
    openai: bool
    telegram: bool

def check_file_system():
    data_dir_writable: bool
    logs_dir_writable: bool
    lock_mechanism: bool

def check_schedule():
    next_collection: datetime
    next_publication: datetime
    pending_news: int
```

## 🛠 Расширяемость

### Добавление нового источника
1. Создать `new_source_client.py`
2. Реализовать интерфейс `BaseNewsClient`
3. Добавить в `news_collector.py`
4. Обновить `validation.py`

### Добавление нового формата
1. Расширить `types_models.py`
2. Добавить парсер в `news_collector.py`
3. Обновить валидацию
4. Адаптировать промпты

### Добавление нового канала публикации
1. Создать `new_channel_client.py`
2. Реализовать интерфейс `BasePublisher`
3. Добавить в `news_publisher.py`
4. Настроить в `config.py`

## 🔄 Миграции

### Версия 1.0 → 2.0
```python
# Изменения структуры
- news_count: 1-6 → 7 (фиксировано)
- schedule: "каждые 3 часа" → 7 времён
- generation: runtime → предварительная
- quality: "high" → "medium"

# Обратная совместимость
- scheduler.py обертка
- Legacy CLI команды
- Старый формат файлов
```

### Будущие версии
- Поддержка множественных каналов
- A/B тестирование контента
- ML-оптимизация времени публикации
- Автоматическая модерация

## 📚 Зависимости

### Критические
```
requests         # HTTP клиент
python-telegram-bot  # Telegram API
loguru          # Логирование
python-dotenv   # Окружение
```

### Важные
```
openai          # Генерация изображений
schedule        # Планировщик
typing-extensions  # Типизация
```

### Опциональные
```
redis           # Распределенные блокировки
prometheus      # Метрики
sentry          # Мониторинг ошибок
```

## 🎓 Best Practices

### DO ✅
- Используй TypedDict для новых структур
- Валидируй все входные данные
- Логируй важные операции
- Обрабатывай ошибки gracefully
- Пиши модульные тесты

### DON'T ❌
- Не используй datetime.now() без timezone
- Не пиши в файлы напрямую
- Не игнорируй валидацию
- Не меняй структуру без миграции
- Не коммить секреты

## 🔮 Roadmap

### Q1 2025
- [x] Типизация кода
- [x] Валидация данных
- [x] Безопасные файловые операции
- [ ] Unit тесты 80% покрытие

### Q2 2025
- [ ] Распределенная архитектура
- [ ] GraphQL API
- [ ] Веб-интерфейс мониторинга
- [ ] Docker контейнеризация

### Q3 2025
- [ ] ML-оптимизация
- [ ] Multi-channel поддержка
- [ ] Автомодерация контента
- [ ] Analytics dashboard

---

📝 **Версия документа**: 2.0.0  
📅 **Обновлено**: Январь 2025  
👤 **Автор**: AI-архитектор Claude