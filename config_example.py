import os
from dotenv import load_dotenv

load_dotenv()

# API ключи (берутся из .env файла)
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

# Настройки времени (МСК)
COLLECTION_TIME = "08:30"  # Время ежедневного сбора новостей
PUBLICATION_SCHEDULE = [
    "09:05",  # Публикация новости приоритет 1
    "11:03",  # Публикация новости приоритет 2  
    "13:07",  # Публикация новости приоритет 3
    "15:09",  # Публикация новости приоритет 4
    "17:05",  # Публикация новости приоритет 5
    "19:02",  # Публикация новости приоритет 6
    "21:07"   # Публикация новости приоритет 7
]

# Legacy настройки (для совместимости)
DAILY_RUN_TIME = "09:00"  # Время ежедневного запуска
HOURLY_INTERVAL = 3  # Интервал в часах между публикациями

# Настройки API
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
REQUEST_TIMEOUT = 300  # Увеличиваем для Deep Research (5 минут)

# Настройки файлов данных
DATA_DIR = "data"
NEWS_FILE_PATTERN = "daily_news_{date}.json"  # {date} = YYYY-MM-DD
MAX_NEWS_FILES = 30  # Храним файлы за последние 30 дней

# Логирование
LOG_LEVEL = "INFO"
LOG_FILE = "newsmaker.log"