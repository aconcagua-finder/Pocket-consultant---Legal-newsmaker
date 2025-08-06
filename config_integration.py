#!/usr/bin/env python3
"""
Модуль интеграции веб-конфигурации с основной системой

Автоматически применяет настройки из веб-интерфейса к основной конфигурации.
"""

import json
from pathlib import Path
from typing import Dict, Any
from loguru import logger

# Пути к файлам конфигурации
WEB_CONFIG_FILE = Path("config_web.json")
PROMPTS_FILE = Path("prompts_custom.json")


def load_web_config() -> Dict[str, Any]:
    """Загружает конфигурацию из веб-интерфейса"""
    if not WEB_CONFIG_FILE.exists():
        return {}
    
    try:
        with open(WEB_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки веб-конфигурации: {e}")
        return {}


def load_custom_prompts() -> Dict[str, str]:
    """Загружает кастомные промпты"""
    if not PROMPTS_FILE.exists():
        return {}
    
    try:
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки кастомных промптов: {e}")
        return {}


def apply_web_config():
    """Применяет настройки из веб-интерфейса"""
    config = load_web_config()
    
    if not config:
        return {}
    
    # Преобразуем веб-конфигурацию в переменные Python
    applied_config = {}
    
    try:
        # API модели
        if 'api_models' in config:
            if 'perplexity' in config['api_models']:
                perplexity = config['api_models']['perplexity']
                applied_config['PERPLEXITY_MODEL'] = perplexity.get('model', 'sonar-deep-research')
                applied_config['PERPLEXITY_MAX_TOKENS'] = perplexity.get('max_tokens', 8192)
                applied_config['PERPLEXITY_TEMPERATURE'] = perplexity.get('temperature', 0.7)
                applied_config['PERPLEXITY_TOP_P'] = perplexity.get('top_p', 0.9)
                applied_config['PERPLEXITY_TIMEOUT'] = perplexity.get('timeout', 300)
            
            if 'openai' in config['api_models']:
                openai = config['api_models']['openai']
                applied_config['OPENAI_IMAGE_MODEL'] = openai.get('model', 'dall-e-3')
                applied_config['OPENAI_IMAGE_QUALITY'] = openai.get('image_quality', 'standard')
                applied_config['OPENAI_IMAGE_STYLE'] = openai.get('image_style', 'vivid')
                applied_config['OPENAI_IMAGE_SIZE'] = openai.get('image_size', '1024x1024')
                applied_config['OPENAI_IMAGE_TIMEOUT'] = openai.get('timeout', 120)
        
        # Расписание
        if 'schedule' in config:
            schedule = config['schedule']
            applied_config['COLLECTION_TIME'] = schedule.get('collection_time', '08:30')
            applied_config['PUBLICATION_SCHEDULE'] = schedule.get('publication_times', [
                "09:05", "11:03", "13:07", "15:09", "17:05", "19:02", "21:07"
            ])
        
        # Контент
        if 'content' in config:
            content = config['content']
            applied_config['MAX_NEWS_PER_DAY'] = content.get('max_news_per_day', 7)
            applied_config['MIN_CONTENT_LENGTH'] = content.get('min_content_length', 50)
            applied_config['MAX_CONTENT_LENGTH'] = content.get('max_content_length', 1500)
            applied_config['CONTENT_SIMILARITY_THRESHOLD'] = content.get('similarity_threshold', 0.7)
            applied_config['NEWS_PRIORITIES'] = content.get('news_priorities', [])
        
        # Telegram
        if 'telegram' in config:
            telegram = config['telegram']
            applied_config['TELEGRAM_MAX_MESSAGE_LENGTH'] = telegram.get('max_message_length', 4096)
            applied_config['TELEGRAM_MAX_CAPTION_LENGTH'] = telegram.get('max_caption_length', 1024)
        
        # Хранение
        if 'storage' in config:
            storage = config['storage']
            applied_config['MAX_NEWS_FILES'] = storage.get('max_news_files', 30)
            applied_config['MAX_HISTORY_ITEMS'] = storage.get('max_history_items', 15)
            applied_config['MAX_HISTORY_DAYS'] = storage.get('max_history_days', 7)
        
        # Retry
        if 'retry' in config:
            retry = config['retry']
            applied_config['MAX_RETRIES'] = retry.get('max_retries', 3)
            applied_config['RETRY_DELAY'] = retry.get('retry_delay', 60)
        
        # Мониторинг
        if 'monitoring' in config:
            monitoring = config['monitoring']
            applied_config['LOG_LEVEL'] = monitoring.get('log_level', 'INFO')
            applied_config['DEBUG'] = monitoring.get('debug_mode', False)
            applied_config['TEST_MODE'] = monitoring.get('test_mode', False)
        
        logger.info(f"✅ Применено {len(applied_config)} настроек из веб-конфигурации")
        return applied_config
        
    except Exception as e:
        logger.error(f"Ошибка применения веб-конфигурации: {e}")
        return {}


def apply_custom_prompts():
    """Применяет кастомные промпты"""
    prompts = load_custom_prompts()
    
    if not prompts:
        return {}
    
    applied_prompts = {}
    
    try:
        # Преобразуем ключи промптов в переменные
        if 'perplexity_system' in prompts:
            applied_prompts['PERPLEXITY_SYSTEM_PROMPT'] = prompts['perplexity_system']
        
        if 'perplexity_collection' in prompts:
            applied_prompts['PERPLEXITY_COLLECTION_PROMPT'] = prompts['perplexity_collection']
        
        if 'openai_comic' in prompts:
            applied_prompts['OPENAI_COMIC_PROMPT'] = prompts['openai_comic']
        
        logger.info(f"✅ Применено {len(applied_prompts)} кастомных промптов")
        return applied_prompts
        
    except Exception as e:
        logger.error(f"Ошибка применения кастомных промптов: {e}")
        return {}


# Автоматически применяем конфигурацию при импорте
WEB_CONFIG = apply_web_config()
CUSTOM_PROMPTS = apply_custom_prompts()

# Экспортируем все настройки
__all__ = ['WEB_CONFIG', 'CUSTOM_PROMPTS', 'apply_web_config', 'apply_custom_prompts']