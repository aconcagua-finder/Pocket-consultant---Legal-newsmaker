# NEWSMAKER - Техническая документация для AI-ассистентов

## 🎯 Обзор проекта
NEWSMAKER - полностью автоматизированный сервис для сбора и публикации российских юридических новостей в Telegram. Система работает ежедневно, собирая 7 законодательных новостей утром через Perplexity Deep Research, генерируя 4-панельные комиксы с помощью OpenAI, и публикуя их равномерно в течение дня в Telegram канале.

## ⚡ Текущее состояние (август 2025)
- **Версия**: 2.3.1 (24-часовой формат времени)
- **Статус**: Production-ready
- **Покрытие типами**: 90%
- **Валидация**: 95% покрытие
- **Безопасность**: Централизованная обработка ошибок, блокировки файлов, атомарные операции
- **Новое в 2.1.2**: Расширенные параметры Perplexity и OpenAI, динамический веб-интерфейс
- **Новое**: Модуль error_handler.py для комплексной обработки исключений

## 🚀 Новая архитектура (2025)

### Основной принцип
**Разделение сбора и публикации:**
- **8:30 утра** - сбор 7 новостей + генерация всех изображений
- **09:05 - 21:07** - публикация по расписанию из готовых файлов

### Расписание публикаций (7 времён)
```
09:05 - Приоритет 1 (критическая важность)
11:03 - Приоритет 2 (очень важная)
13:07 - Приоритет 3 (важная)
15:09 - Приоритет 4 (средняя)
17:05 - Приоритет 5 (умеренная)
19:02 - Приоритет 6 (дополнительная)
21:07 - Приоритет 7 (низкая)
```

### Преимущества
✅ **Скорость:** Публикация за 6 секунд вместо 60-120  
✅ **Контроль:** Все тексты и изображения доступны до публикации  
✅ **Экономия:** Quality "high" для лучшего качества (GPT-Image-1)  
✅ **Равномерность:** Новости растянуты на весь день  
✅ **Типизация:** TypedDict для всех структур данных  
✅ **Безопасность:** Валидация, блокировки, атомарные операции  

## 🏗 Архитектура системы

### Основные компоненты

#### Точка входа
1. **main.py** - CLI интерфейс и управление режимами
   - Обработка аргументов командной строки
   - Управление режимами работы
   - Инициализация логирования

#### Бизнес-логика
2. **news_collector.py** - ежедневный сбор новостей
   - Perplexity Deep Research (8192 токена)
   - Сбор РОВНО 7 новостей с приоритизацией
   - Генерация ВСЕХ изображений сразу

3. **news_publisher.py** - публикация из файлов
   - Чтение готовых новостей и изображений
   - Мгновенная публикация
   - Антидубликатор

4. **news_scheduler.py** - планировщик
   - Управление расписанием
   - Интеграция компонентов
   - Восстановление после ошибок

#### API клиенты
5. **perplexity_client.py** - работа с Perplexity API
   - Поддержка search_recency_filter (hour/day/week/month)
   - Поддержка search_depth (low/medium/high)
   - Фильтры по датам (after/before)
   - Расширенные web_search_options
   - Автоматическая корректировка max_tokens

6. **openai_client.py** - генерация 4-панельных комиксов
   - Поддержка GPT-Image-1 (до 4096x4096)
   - Корректные quality опции для каждой модели
   - Автоматическая установка response_format
   - Индикаторы цен (от $0.02 до $0.19)

7. **telegram_client.py** - публикация в Telegram

#### Инфраструктура (НОВОЕ)
8. **types_models.py** 🆕 - TypedDict модели
   - NewsItem, NewsFileData, TelegramMessage
   - Enums для статусов и приоритетов
   - Функции валидации типов

9. **validation.py** 🆕 - комплексная валидация
   - Валидация новостей и контента
   - Проверка API ответов
   - Валидация файлов и конфигурации
   - Извлечение и проверка дат из контента

10. **timezone_utils.py** 🆕 - работа с МСК
    - Корректная поддержка Europe/Moscow
    - Функции now_msk(), yesterday_msk()
    - Преобразование между timezone

11. **file_utils.py** 🆕 - безопасные файловые операции
    - FileLock для блокировок
    - Атомарная запись через временные файлы
    - safe_json_read/write
    - Резервное копирование

12. **run_with_validation.py** 🆕 - запуск с проверками
    - Полная валидация перед запуском
    - Проверка timezone
    - Тестирование файловой системы

13. **error_handler.py** 🆕 - централизованная обработка ошибок
    - Кастомные исключения для разных типов ошибок
    - Декораторы для безопасного выполнения
    - Контекстные менеджеры для обработки ошибок
    - Логирование и сохранение критических ошибок
    - Retry логика с exponential backoff

#### Конфигурация
13. **config.py** - основная конфигурация
14. **config_template.py** 🆕 - шаблон для новых установок
15. **prompts.py** - AI промпты

#### Интерфейс и визуализация
16. **tooltips.css/js** 🆕 - интерактивные подсказки
    - Glassmorphism дизайн подсказок с blur-эффектом
    - TooltipSystem класс для управления
    - Адаптивное позиционирование относительно viewport
    - 4 типа подсказок с цветовым кодированием (info, success, warning, error)
    - Поддержка accessibility (high contrast, reduced motion)

#### Утилиты
17. **logger_setup.py** - унифицированное логирование (включает modern функционал)
18. **error_handler.py** - централизованная обработка ошибок и retry логика
19. **utils/show_full_prompt.py** - отладка промптов

## 👥 Система профилей

### Основные возможности
- **Множественные профили** - сохранение разных конфигураций
- **Дефолтный профиль** - "Pocket Consultant" всегда доступен
- **Быстрое переключение** - между профилями через веб-интерфейс
- **Экспорт/импорт** - резервное копирование настроек

### Файловая структура
```
profiles/
├── Pocket Consultant.json    # Дефолтный профиль
├── Мой тестовый.json        # Пример пользовательского
└── Production.json          # Пример боевого
```

### Управление через API
```python
# Пример программного управления
from web_config_app import ConfigManager

cm = ConfigManager()
cm.load_profile("Мой тестовый")
cm.save_profile("Новый профиль")
```

## 🌐 Расширенные параметры API (НОВОЕ в 2.1.2)

### Perplexity API
```python
# Пример использования в news_collector.py
perplexity_config = {
    "model": "sonar-deep-research",
    "temperature": 0.7,
    "top_p": 0.9,
    "presence_penalty": 0.1,
    "frequency_penalty": 0.1,
    "max_tokens": 8192,
    "search_depth": "high",  # Глубокий поиск
    "search_recency_filter": "day",  # Новости за последний день
    "search_after_date_filter": "2025-08-01",  # После даты
    "search_before_date_filter": None,  # До даты
    "web_search_options": {
        "include_domains": ["pravo.gov.ru", "consultant.ru"],
        "exclude_domains": [],
        "return_citations": True,
        "return_related_questions": False
    }
}
```

### OpenAI API
```python
# Пример конфигурации для разных моделей
openai_configs = {
    "gpt-image-1": {
        "size": "2048x2048",  # до 4096x4096
        "quality": "high",  # low/medium/high
        "response_format": "bytes",  # автоматически
        "price": "$0.19"  # для high quality
    },
    "dall-e-3": {
        "size": "1792x1024",  # максимум для этой модели
        "quality": "hd",  # standard/hd
        "price": "$0.08"  # для hd quality
    },
    "dall-e-2": {
        "size": "1024x1024",  # максимум
        "price": "$0.02"  # фиксированная цена
    }
}
```

### Веб-интерфейс (НОВОЕ)
- **Динамические поля** - автоматически меняются при выборе модели
- **Tooltips** - подсказки для каждого параметра
- **Индикаторы лимитов** - отображение максимальных токенов
- **Индикаторы цен** - стоимость генерации изображений
- **Валидация на лету** - проверка корректности параметров

## 📊 Структуры данных

### NewsItem (TypedDict)
```python
{
    "id": str,                    # Уникальный ID новости
    "priority": int,              # Приоритет 1-7
    "title": str,                 # Заголовок
    "content": str,              # Полный текст с эмодзи
    "sources": List[str],        # Список URL источников
    "scheduled_time": str,       # Время публикации HH:MM
    "collected_at": str,         # ISO datetime сбора
    "published": bool,           # Статус публикации
    "publication_attempts": int,  # Попытки публикации
    "image_path": str,           # Путь к изображению
    "image_generated": bool,     # Сгенерировано ли изображение
    "image_size": int           # Размер файла в байтах
}
```

### NewsFileData (TypedDict)
```python
{
    "date": str,                # Дата сбора YYYY-MM-DD
    "collected_at": str,        # ISO datetime
    "total_news": int,          # Всего новостей (7)
    "news": List[NewsItem]     # Список новостей
}
```

## 🔄 Workflow

### Ежедневный цикл

#### 8:30 - Утренний сбор
1. Запрос к Perplexity Deep Research
2. Парсинг и валидация 7 новостей
3. Генерация 7 изображений подряд (~20 мин)
4. Сохранение в `data/daily_news_YYYY-MM-DD.json`
5. Изображения в `data/images/YYYY-MM-DD/`

#### 09:05-21:07 - Публикации
1. Чтение файла новостей
2. Проверка расписания
3. Загрузка готового изображения
4. Публикация в Telegram (6 сек)
5. Обновление статуса в файле

## 🛠 CLI команды

### Основные команды
```bash
python main.py --collect          # Ручной сбор новостей
python main.py --publish-next     # Публикация следующей
python main.py --force-publish N  # Принудительная публикация N
python main.py --test-publish-all # Тест всех публикаций
python main.py --status           # Статус системы
python main.py --start           # Запуск планировщика
python main.py --test            # Тестирование
```

### Отладка с валидацией
```bash
python run_with_validation.py    # Запуск с полной проверкой
```

## 🔒 Безопасность и надежность

### Реализованные механизмы
1. **Типизация** - TypedDict для всех структур
2. **Валидация** - проверка всех входных данных
3. **Блокировки** - FileLock для параллельного доступа
4. **Атомарность** - временные файлы для записи
5. **Timezone** - корректная работа с МСК
6. **Антидубликатор** - проверка повторов
7. **Retry логика** - повторные попытки при ошибках
8. **Graceful fallback** - обработка ошибок

## 📁 Файловая структура

```
NEWSMAKER/
├── data/
│   ├── daily_news_YYYY-MM-DD.json    # Новости за день
│   └── images/
│       └── YYYY-MM-DD/
│           ├── news_*_1.png          # Приоритет 1-7
│           └── ...
├── logs/
│   ├── newsmaker.log                 # Основной лог
│   ├── errors.log                   # Только ошибки
│   └── message_history.json         # История публикаций
├── tests/
│   ├── html/                        # HTML тестовые файлы
│   ├── unit/                        # Unit тесты
│   └── integration/                 # Интеграционные тесты
├── docs/
│   ├── archive/                     # Архивные документы и отчеты
│   └── technical/                   # Техническая документация
├── static/
│   ├── css/
│   │   └── tooltips.css             # Стили подсказок
│   └── js/
│       └── tooltips.js              # Логика подсказок
├── utils/
│   └── show_full_prompt.py          # Отладочные утилиты
└── [основные модули]
```

## 🔧 Конфигурация

### Ключевые настройки (config.py)
```python
# Расписание
COLLECTION_TIME = "08:30"
PUBLICATION_SCHEDULE = ["09:05", "11:03", "13:07", ...]

# Perplexity API
PERPLEXITY_MODEL = "sonar-deep-research"
PERPLEXITY_MAX_TOKENS = 8192
PERPLEXITY_TEMPERATURE = 0.7
PERPLEXITY_TOP_P = 0.9
PERPLEXITY_SEARCH_DEPTH = "high"  # low/medium/high
PERPLEXITY_SEARCH_RECENCY = "day"  # hour/day/week/month
PERPLEXITY_SEARCH_AFTER_DATE = None  # YYYY-MM-DD
PERPLEXITY_SEARCH_BEFORE_DATE = None  # YYYY-MM-DD

# OpenAI API
OPENAI_MODEL = "gpt-image-1"  # dall-e-2, dall-e-3, gpt-image-1
OPENAI_IMAGE_QUALITY = "high"  # standard/high для dall-e-3, low/medium/high для gpt-image-1
OPENAI_IMAGE_SIZE = "1536x1024"  # до 4096x4096 для gpt-image-1

# Система
REQUEST_TIMEOUT = 60
MAX_RETRIES = 3
MIN_CONTENT_LENGTH = 100
MAX_CONTENT_LENGTH = 4000
```

## 📝 Промпты

### Сбор новостей (Perplexity)
- Функция: `get_perplexity_daily_collection_prompt()`
- Собирает РОВНО 7 новостей
- Приоритизация от критических до дополнительных
- Ироничный стиль "Карманного Консультанта"

### Генерация комиксов (OpenAI)
- Функция: `get_openai_comic_prompt()`
- Поддерживаемые модели:
  - **GPT-Image-1** (апрель 2025, до 4096x4096)
    - Качество: low ($0.02), medium ($0.07), high ($0.19)
    - Размеры: 256x256 до 4096x4096
  - **DALL-E 3** (до 1792x1024)
    - Качество: standard ($0.04), hd ($0.08)
    - Размеры: 1024x1024, 1024x1792, 1792x1024
  - **DALL-E 2** (до 1024x1024)
    - Цена: $0.02 за изображение
- 4-панельный формат без текста
- Визуальная история: обнаружение → реакция → понимание → адаптация

## 🧪 Тестирование

### Модульные тесты
```python
# В каждом модуле есть тестовые функции
python -c "from validation import test_validation_functions; test_validation_functions()"
python -c "from timezone_utils import test_timezone_functions; test_timezone_functions()"
python -c "from file_utils import test_file_operations; test_file_operations()"
```

### Интеграционные тесты
```bash
python run_with_validation.py  # Полная проверка системы
python main.py --test          # Быстрый тест компонентов
```

## 📊 Мониторинг

### Логирование
- **newsmaker.log** - все события с ротацией
- **errors.log** - только критические ошибки
- **message_history.json** - история для антидубликатора

### Метрики
- Сбор новостей: ~2-3 минуты
- Генерация 7 изображений: ~20 минут
- Публикация: ~6 секунд
- RAM: < 100 MB
- Логи: ~10 MB/месяц

## ⚠️ Важные моменты для разработки

### При добавлении функций
1. Используй TypedDict для новых структур
2. Добавь валидацию в validation.py
3. Используй timezone_utils для времени
4. Применяй file_utils для работы с файлами
5. Логируй через loguru

### При модификации
1. НЕ изменяй формат daily_news файлов
2. НЕ меняй структуру NewsItem без миграции
3. НЕ используй datetime.now() без timezone
4. НЕ пиши в файлы напрямую - используй file_utils
5. НЕ забывай про валидацию входных данных

### Частые проблемы
| Проблема | Решение |
|----------|---------|
| Import conflicts | Используй алиасы как в main.py |
| File locks | Используй FileLock из file_utils |
| Timezone issues | Всегда используй timezone_utils |
| Type errors | Добавь типы в types_models.py |
| Validation fails | Обнови validation.py |

## 🔄 Миграция и совместимость

### Обратная совместимость
- Legacy режим через --run сохранен
- main.py использует DirectNewsScheduler напрямую
- Старые тесты сохранены

### Миграция данных
- Файлы новостей совместимы
- Изображения в том же формате
- Логи продолжают работать

## 🚀 Быстрый старт для разработчика

```bash
# 1. Клонирование
git clone <repo>
cd newsmaker

# 2. Окружение
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Зависимости
pip install -r requirements.txt

# 4. Конфигурация
cp config_template.py config.py
cp env_example.txt .env
# Отредактируй .env

# 5. Валидация
python run_with_validation.py

# 6. Запуск
python main.py --test  # Тест
python main.py --start  # Продакшн
```

## 📚 Дополнительная документация

- **README.md** - общее описание проекта
- **ARCHITECTURE.md** - детальная архитектура
- **IMPROVEMENTS.md** - история улучшений
- **SETUP_NEW_BOT.md** - настройка Telegram бота

---

💡 **Подсказка для AI**: При работе с кодом всегда используй новые модули (types_models, validation, timezone_utils, file_utils) вместо прямой работы с данными. Это обеспечит безопасность и корректность.