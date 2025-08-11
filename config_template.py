"""
Шаблон конфигурации для NEWSMAKER

ИНСТРУКЦИЯ:
1. Скопируйте этот файл и назовите его config.py
2. Заполните все необходимые значения
3. НИКОГДА не коммитьте config.py с реальными ключами!
"""

import os
from pathlib import Path
from typing import Optional
import sys

# ==================================================
# API КЛЮЧИ
# ==================================================

# Perplexity API
PERPLEXITY_API_KEY = "pplx-YOUR_PERPLEXITY_API_KEY_HERE"

# OpenAI API
OPENAI_API_KEY = "sk-YOUR_OPENAI_API_KEY_HERE"

# Telegram
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN:YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHANNEL_ID = "@your_channel_or_chat_id"

# ==================================================
# НАСТРОЙКИ РАСПИСАНИЯ
# ==================================================

# Время ежедневного сбора новостей (формат HH:MM)
COLLECTION_TIME = "08:30"

# Расписание публикаций (7 времён для 7 новостей)
PUBLICATION_SCHEDULE = [
    "09:05",  # Приоритет 1 (критически важная)
    "11:05",  # Приоритет 2 (очень важная)
    "13:05",  # Приоритет 3 (важная)
    "15:10",  # Приоритет 4 (средняя важность)
    "17:05",  # Приоритет 5 (умеренная важность)
    "19:00",  # Приоритет 6 (дополнительная)
    "21:05"   # Приоритет 7 (низкая важность)
]

# Максимальное количество новостей в день
MAX_NEWS_PER_DAY = 7

# ==================================================
# НАСТРОЙКИ API
# ==================================================

# Perplexity
PERPLEXITY_MODEL = "sonar-deep-research"
PERPLEXITY_MAX_TOKENS = 8192
PERPLEXITY_TEMPERATURE = 0.7

# OpenAI
OPENAI_IMAGE_MODEL = "gpt-image-1"
OPENAI_IMAGE_SIZE = "1536x1024"
OPENAI_IMAGE_QUALITY = "medium"  # medium для экономии, high для качества

# ==================================================
# ПУТИ И ДИРЕКТОРИИ
# ==================================================

# Базовая директория проекта
BASE_DIR = Path(__file__).parent

# Директории данных
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
IMAGES_DIR = DATA_DIR / "images"

# ==================================================
# НАСТРОЙКИ СИСТЕМЫ
# ==================================================

# Таймауты
REQUEST_TIMEOUT = 60
IMAGE_GENERATION_TIMEOUT = 120

# Повторные попытки
MAX_RETRIES = 3
RETRY_DELAY = 30

# Логирование
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_ROTATION = "1 week"
LOG_RETENTION = "1 month"

# Валидация контента
MIN_CONTENT_LENGTH = 100
MAX_CONTENT_LENGTH = 4000

# ==================================================
# РЕЖИМЫ РАБОТЫ
# ==================================================

# Режим отладки
DEBUG = False

# Тестовый режим (не отправляет в Telegram)
TEST_MODE = False

# ==================================================
# АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ДИРЕКТОРИЙ
# ==================================================

# Создаём необходимые директории при импорте
for directory in [DATA_DIR, LOGS_DIR, IMAGES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ==================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==================================================

def get_env_var(key: str, default: Optional[str] = None, required: bool = False) -> str:
    """
    Безопасное получение переменной окружения
    
    Args:
        key: Имя переменной
        default: Значение по умолчанию
        required: Обязательная ли переменная
        
    Returns:
        str: Значение переменной
    """
    value = os.getenv(key, default)
    
    if required and not value:
        print(f"❌ ОШИБКА: Обязательная переменная окружения {key} не установлена!")
        print(f"💡 Подсказка: Создайте файл .env и добавьте: {key}=your_value")
        sys.exit(1)
    
    return value or ""

# ==================================================
# ЗАГРУЗКА ИЗ ОКРУЖЕНИЯ (если есть .env)
# ==================================================

# Пытаемся загрузить из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()
    
    # Переопределяем значения из окружения если они есть
    PERPLEXITY_API_KEY = get_env_var("PERPLEXITY_API_KEY", PERPLEXITY_API_KEY)
    OPENAI_API_KEY = get_env_var("OPENAI_API_KEY", OPENAI_API_KEY)
    TELEGRAM_BOT_TOKEN = get_env_var("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    TELEGRAM_CHANNEL_ID = get_env_var("TELEGRAM_CHANNEL_ID", TELEGRAM_CHANNEL_ID)
    
except ImportError:
    pass  # dotenv не установлен - используем значения из файла

# ==================================================
# ВАЛИДАЦИЯ ПРИ ИМПОРТЕ
# ==================================================

def validate_config():
    """Проверяет корректность конфигурации"""
    errors = []
    
    # Проверка API ключей
    if not PERPLEXITY_API_KEY or "YOUR_" in PERPLEXITY_API_KEY:
        errors.append("PERPLEXITY_API_KEY не настроен")
    
    if not OPENAI_API_KEY or "YOUR_" in OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY не настроен")
    
    if not TELEGRAM_BOT_TOKEN or "YOUR_" in TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN не настроен")
    
    if not TELEGRAM_CHANNEL_ID or "your_" in TELEGRAM_CHANNEL_ID:
        errors.append("TELEGRAM_CHANNEL_ID не настроен")
    
    return errors

# Проверяем конфигурацию при импорте
config_errors = validate_config()
if config_errors and not TEST_MODE:
    print("⚠️ ПРЕДУПРЕЖДЕНИЕ: Обнаружены проблемы с конфигурацией:")
    for error in config_errors:
        print(f"  - {error}")
    print("\n💡 Подсказка: Скопируйте config_template.py в config.py и заполните значения")