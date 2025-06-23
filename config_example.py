import os
from dotenv import load_dotenv

load_dotenv()

# API ключи - ЗАПОЛНИТЕ СВОИМИ ДАННЫМИ!
PERPLEXITY_API_KEY = "your_perplexity_api_key_here"
OPENAI_API_KEY = "your_openai_api_key_here"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

# Настройки времени
DAILY_RUN_TIME = "09:00"  # Время ежедневного запуска
HOURLY_INTERVAL = 3  # Интервал в часах между публикациями

# Настройки API
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
REQUEST_TIMEOUT = 60

# Логирование
LOG_LEVEL = "INFO"
LOG_FILE = "newsmaker.log" 