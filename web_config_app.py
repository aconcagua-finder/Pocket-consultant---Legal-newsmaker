#!/usr/bin/env python3
"""
Web интерфейс для управления настройками NEWSMAKER

Позволяет редактировать все параметры системы через удобный веб-интерфейс.
"""

import json
import os
import copy
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, send_file, session
from flask_cors import CORS
from typing import Dict, Any, List, Optional
from loguru import logger
import hashlib
import secrets
import shutil

# Импортируем модуль аутентификации
from auth_middleware import requires_auth, requires_admin, sanitize_input

# Импортируем модули проекта
from timezone_utils import (
    now_msk, 
    get_all_timezones_with_offset,
    format_schedule_preview,
    to_user_timezone,
    from_user_timezone,
    parse_time_string,
    get_timezone,
    POPULAR_TIMEZONES
)
from file_utils import safe_json_write, safe_json_read

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = secrets.token_hex(32)  # Генерируем случайный секретный ключ
CORS(app)

# Путь к файлу конфигурации
CONFIG_FILE = Path("config_web.json")
DEFAULT_CONFIG_FILE = Path("config_defaults.json")
PROMPTS_FILE = Path("prompts_custom.json")
ENV_FILE = Path(".env")
PROFILES_DIR = Path("profiles")

# Создаем папку для профилей если её нет
PROFILES_DIR.mkdir(exist_ok=True)

# Дефолтная конфигурация
DEFAULT_CONFIG = {
    "api_models": {
        "perplexity": {
            "model": "sonar-deep-research",
            "available_models": [
                "sonar",
                "sonar-pro", 
                "sonar-reasoning",
                "sonar-reasoning-pro",
                "sonar-deep-research"
            ],
            "max_tokens": 8192,
            "max_tokens_limits": {  # Лимиты токенов для каждой модели
                "sonar": 4096,
                "sonar-pro": 8192,
                "sonar-reasoning": 8192,
                "sonar-reasoning-pro": 12000,
                "sonar-deep-research": 16384
            },
            "temperature": 0.7,
            "top_p": 0.9,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "timeout": 300,
            "search_domain_filter": [],  # Список доменов для фильтрации поиска
            "return_citations": True,
            "return_related_questions": False,
            "search_recency_filter": None,  # Фильтр свежести: month, week, day, hour
            "search_depth": "high",  # Глубина поиска: low, medium, high
            "search_after_date_filter": None,  # Формат: MM/DD/YYYY
            "search_before_date_filter": None,  # Формат: MM/DD/YYYY
            "web_search_options": {  # Расширенные опции поиска
                "search_context_size": "high",  # low, medium, high
                "enable_deep_search": True
            },
            "descriptions": {  # Описания параметров для UI
                "model": "Модель для обработки запросов. Deep Research проводит глубокий анализ до 100+ источников",
                "max_tokens": "Максимальная длина ответа в токенах (зависит от модели)",
                "temperature": "Креативность ответов (0-1). Меньше = точнее, больше = креативнее",
                "top_p": "Альтернативный контроль креативности (0-1)",
                "presence_penalty": "Штраф за повторение тем (-2 до 2)",
                "frequency_penalty": "Штраф за повторение слов (-2 до 2)",
                "search_recency_filter": "Фильтр свежести контента (hour/day/week/month)",
                "search_depth": "Глубина поиска информации (low/medium/high)",
                "search_domain_filter": "Включить или исключить домены (пример: github.com, -quora.com)",
                "search_after_date_filter": "Искать контент после даты (MM/DD/YYYY)",
                "search_before_date_filter": "Искать контент до даты (MM/DD/YYYY)"
            }
        },
        "openai": {
            "model": "gpt-image-1",  # По умолчанию GPT-Image-1
            "available_models": [
                "dall-e-2",
                "dall-e-3",
                "gpt-image-1"  # Новая модель с поддержкой до 4096x4096
            ],
            "image_quality": "high",  # Дефолт для GPT-Image-1
            "quality_options": {
                "dall-e-2": ["standard"],
                "dall-e-3": ["standard", "hd"],
                "gpt-image-1": ["low", "medium", "high"]
            },
            "image_style": "vivid",
            "style_options": {
                "dall-e-2": [],  # Нет опций стиля
                "dall-e-3": ["vivid", "natural"],
                "gpt-image-1": []  # Нет опций стиля
            },
            "image_size": "1024x1024",
            "size_options": {
                "dall-e-2": ["256x256", "512x512", "1024x1024"],
                "dall-e-3": ["1024x1024", "1024x1792", "1792x1024"],
                "gpt-image-1": ["1024x1024", "1024x1536", "1536x1024", "2048x2048", "4096x4096"]
            },
            "response_format": "url",  # url или b64_json
            "response_format_options": {
                "dall-e-2": ["url", "b64_json"],
                "dall-e-3": ["url", "b64_json"],
                "gpt-image-1": ["b64_json"]  # GPT-Image-1 всегда возвращает base64
            },
            "moderation": "auto",  # auto или low (только для gpt-image-1)
            "n_images": 1,  # Количество изображений
            "n_images_limits": {
                "dall-e-2": 10,  # DALL-E 2 поддерживает до 10 изображений
                "dall-e-3": 1,   # DALL-E 3 только 1 изображение
                "gpt-image-1": 1  # GPT-Image-1 только 1 изображение
            },
            "timeout": 120,
            "pricing": {  # Цены за изображение
                "dall-e-2": {
                    "256x256": 0.016,
                    "512x512": 0.018,
                    "1024x1024": 0.020
                },
                "dall-e-3": {
                    "standard": {"1024x1024": 0.040, "1024x1792": 0.080, "1792x1024": 0.080},
                    "hd": {"1024x1024": 0.080, "1024x1792": 0.120, "1792x1024": 0.120}
                },
                "gpt-image-1": {
                    "low": 0.01,     # Низкое качество - $0.01
                    "medium": 0.04,  # Среднее качество - $0.04
                    "high": 0.17     # Высокое качество - $0.17
                }
            },
            "descriptions": {  # Описания параметров для UI
                "model": "Модель генерации изображений. GPT-Image-1 - новейшая с поддержкой до 4096x4096",
                "image_quality": "Качество изображения (влияет на цену и детализацию)",
                "image_style": "Стиль изображения: vivid (яркий) или natural (естественный)",
                "image_size": "Размер изображения в пикселях",
                "response_format": "Формат ответа: URL или base64 данные",
                "moderation": "Уровень модерации контента (только для gpt-image-1)",
                "n_images": "Количество изображений для генерации"
            }
        }
    },
    "schedule": {
        "collection_time": "08:30",
        "publications_per_day": 7,  # Количество публикаций в день (1-24)
        "user_timezone": "Europe/Moscow",  # Часовой пояс пользователя
        "publication_times": [
            "09:05",
            "11:03", 
            "13:07",
            "15:09",
            "17:05",
            "19:02",
            "21:07",
            "",  # Слоты 8-24 для расширения
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            ""
        ],
        "auto_distribute": False,  # Автоматическое распределение времён
        "timezone": "Europe/Moscow"  # Legacy для совместимости
    },
    "content": {
        "max_news_per_day": 24,  # Увеличено до 24
        "min_content_length": 50,
        "max_content_length": 1500,
        "similarity_threshold": 0.7,
        "news_priorities": [
            "КРИТИЧЕСКИ ВАЖНО",
            "ОЧЕНЬ ВАЖНО",
            "ВАЖНО",
            "СРЕДНЯЯ ВАЖНОСТЬ",
            "УМЕРЕННАЯ ВАЖНОСТЬ",
            "ДОПОЛНИТЕЛЬНАЯ",
            "НИЗКАЯ ВАЖНОСТЬ"
        ],
        "generate_images": True,  # Флаг для генерации изображений
        "publish_without_images": False  # Публиковать без изображений если генерация не удалась
    },
    "telegram": {
        "max_message_length": 4096,
        "max_caption_length": 1024,
        "parse_mode": "HTML"
    },
    "storage": {
        "max_news_files": 30,
        "max_history_items": 15,
        "max_history_days": 7,
        "data_dir": "data",
        "logs_dir": "logs"
    },
    "retry": {
        "max_retries": 3,
        "retry_delay": 60,
        "exponential_backoff": True
    },
    "monitoring": {
        "log_level": "INFO",
        "debug_mode": False,
        "test_mode": False
    }
}

# Дефолтные промпты
DEFAULT_PROMPTS = {
    "perplexity_system": "Ты опытный юрист-практик, специализирующийся на актуальных изменениях законодательства. Отвечай кратко, по существу, с конкретными фактами и цифрами.",
    "perplexity_collection": """Проведи глубокий анализ и собери ВСЕ значимые изменения в российском законодательстве за ВЧЕРА.

🎯 ЗАДАЧА: Найди РОВНО 7 самых важных законодательных новостей за вчерашний день и ранжируй их по приоритету.

ТРЕБОВАНИЯ К КАЖДОЙ НОВОСТИ:
- Конкретные цифры: суммы, проценты, сроки, даты
- Указание кого именно затрагивает изменение
- Практический эффект для граждан/бизнеса
- Точная дата вступления в силу или принятия
- Минимум 2-3 надежных источника

СТИЛЬ:
- Юридический с легкой иронией
- Живой язык, как будто пишет опытный практик
- 1-2 эмодзи на новость (умеренно!)
- Каждая новость 100-150 слов""",
    "openai_comic": """Create a 4-panel comic strip about Russian legal news:
    
STYLE: Realistic style, photographic quality

4-PANEL LAYOUT:
Panel 1: Setup - Character discovers the legal change
Panel 2: Reaction - Character processes the information
Panel 3: Understanding - Character realizes the implications
Panel 4: Resolution - Character adapts to new reality"""
}


class ConfigManager:
    """Менеджер конфигурации с поддержкой истории изменений и профилей"""
    
    def __init__(self):
        self.current_profile = "Pocket Consultant"  # Дефолтный профиль
        self.profiles = self.load_profiles()
        self.config = self.load_config()
        self.prompts = self.load_prompts()
        self.api_keys = self.load_api_keys()
        self.history = []
        self.max_history = 10
        
        # Создаем дефолтный профиль если его нет
        if self.current_profile not in self.profiles:
            self.save_profile(self.current_profile)
    
    def load_profiles(self) -> Dict[str, Dict]:
        """Загружает список всех профилей"""
        profiles = {}
        
        # Сканируем папку профилей
        for profile_file in PROFILES_DIR.glob("*.json"):
            try:
                profile_name = profile_file.stem  # Имя файла без расширения
                profile_data = safe_json_read(profile_file)
                if profile_data:
                    profiles[profile_name] = profile_data
            except Exception as e:
                logger.error(f"Ошибка загрузки профиля {profile_file}: {e}")
        
        # Если нет профилей, создаем дефолтный
        if not profiles:
            profiles["Pocket Consultant"] = {
                "config": copy.deepcopy(DEFAULT_CONFIG),
                "prompts": copy.deepcopy(DEFAULT_PROMPTS),
                "created_at": now_msk().isoformat(),
                "updated_at": now_msk().isoformat()
            }
        
        return profiles
    
    def save_profile(self, profile_name: str) -> bool:
        """Сохраняет текущие настройки в профиль"""
        try:
            profile_path = PROFILES_DIR / f"{profile_name}.json"
            profile_data = {
                "config": self.config,
                "prompts": self.prompts,
                "created_at": self.profiles.get(profile_name, {}).get("created_at", now_msk().isoformat()),
                "updated_at": now_msk().isoformat()
            }
            
            if safe_json_write(profile_path, profile_data):
                self.profiles[profile_name] = profile_data
                logger.info(f"Профиль '{profile_name}' успешно сохранен")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка сохранения профиля: {e}")
            return False
    
    def migrate_profile_config(self, config: dict) -> dict:
        """Мигрирует старую структуру конфигурации профиля на новую"""
        try:
            # Миграция настроек расписания
            if "schedule" in config:
                schedule = config["schedule"]
                
                # Добавляем user_timezone если его нет
                if "user_timezone" not in schedule:
                    # Берём из старого поля timezone или ставим МСК
                    schedule["user_timezone"] = schedule.get("timezone", "Europe/Moscow")
                    logger.info(f"Добавлено поле user_timezone: {schedule['user_timezone']}")
                
                # Добавляем publications_per_day если его нет
                if "publications_per_day" not in schedule:
                    # Определяем по количеству времён публикации
                    pub_times = schedule.get("publication_times", [])
                    schedule["publications_per_day"] = len(pub_times) if pub_times else 7
                    logger.info(f"Добавлено поле publications_per_day: {schedule['publications_per_day']}")
                
                # Добавляем auto_distribute если его нет
                if "auto_distribute" not in schedule:
                    schedule["auto_distribute"] = False
                    logger.info("Добавлено поле auto_distribute: False")
                
                # Убеждаемся что есть поле timezone для совместимости
                if "timezone" not in schedule:
                    schedule["timezone"] = schedule.get("user_timezone", "Europe/Moscow")
            
            return config
        except Exception as e:
            logger.error(f"Ошибка миграции конфигурации: {e}")
            return config
    
    def load_profile(self, profile_name: str) -> bool:
        """Загружает настройки из профиля"""
        try:
            if profile_name not in self.profiles:
                logger.error(f"Профиль '{profile_name}' не найден")
                return False
            
            profile_data = self.profiles[profile_name]
            loaded_config = profile_data.get("config", DEFAULT_CONFIG)
            
            # Мигрируем конфигурацию если нужно
            migrated_config = self.migrate_profile_config(copy.deepcopy(loaded_config))
            
            self.config = migrated_config
            self.prompts = copy.deepcopy(profile_data.get("prompts", DEFAULT_PROMPTS))
            self.current_profile = profile_name
            
            # Если конфигурация была мигрирована, сохраняем обратно в профиль
            if migrated_config != loaded_config:
                logger.info(f"Профиль '{profile_name}' был мигрирован на новую структуру")
                self.save_profile(profile_name)
            
            # Сохраняем как текущую конфигурацию
            self.save_config()
            self.save_prompts()
            
            logger.info(f"Профиль '{profile_name}' успешно загружен")
            return True
        except Exception as e:
            logger.error(f"Ошибка загрузки профиля: {e}")
            return False
    
    def delete_profile(self, profile_name: str) -> bool:
        """Удаляет профиль"""
        try:
            if profile_name == "Pocket Consultant":
                logger.warning("Нельзя удалить дефолтный профиль")
                return False
            
            profile_path = PROFILES_DIR / f"{profile_name}.json"
            if profile_path.exists():
                profile_path.unlink()
                del self.profiles[profile_name]
                
                # Если удаляем текущий профиль, переключаемся на дефолтный
                if self.current_profile == profile_name:
                    self.load_profile("Pocket Consultant")
                
                logger.info(f"Профиль '{profile_name}' удален")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка удаления профиля: {e}")
            return False
    
    def duplicate_profile(self, source_name: str, new_name: str) -> bool:
        """Дублирует профиль с новым именем"""
        try:
            if source_name not in self.profiles:
                logger.error(f"Исходный профиль '{source_name}' не найден")
                return False
            
            if new_name in self.profiles:
                logger.error(f"Профиль '{new_name}' уже существует")
                return False
            
            # Копируем данные профиля
            source_data = copy.deepcopy(self.profiles[source_name])
            source_data["created_at"] = now_msk().isoformat()
            source_data["updated_at"] = now_msk().isoformat()
            
            # Сохраняем новый профиль
            profile_path = PROFILES_DIR / f"{new_name}.json"
            if safe_json_write(profile_path, source_data):
                self.profiles[new_name] = source_data
                logger.info(f"Профиль '{new_name}' создан как копия '{source_name}'")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка дублирования профиля: {e}")
            return False
        
    def load_config(self) -> Dict:
        """Загружает конфигурацию из файла или создает дефолтную"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Мержим с дефолтами для новых полей
                    return self._merge_configs(DEFAULT_CONFIG, config)
            except Exception as e:
                logger.error(f"Ошибка загрузки конфигурации: {e}")
                return copy.deepcopy(DEFAULT_CONFIG)
        else:
            # Сохраняем дефолтную конфигурацию
            self.save_defaults()
            # Пытаемся загрузить из дефолтного профиля
            if "Pocket Consultant" in self.profiles:
                return copy.deepcopy(self.profiles["Pocket Consultant"].get("config", DEFAULT_CONFIG))
            return copy.deepcopy(DEFAULT_CONFIG)
    
    def load_prompts(self) -> Dict:
        """Загружает кастомные промпты"""
        if PROMPTS_FILE.exists():
            try:
                with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки промптов: {e}")
                return copy.deepcopy(DEFAULT_PROMPTS)
        return copy.deepcopy(DEFAULT_PROMPTS)
    
    def load_api_keys(self) -> Dict:
        """Загружает API ключи из .env файла"""
        keys = {}
        if ENV_FILE.exists():
            try:
                with open(ENV_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if key in ['PERPLEXITY_API_KEY', 'OPENAI_API_KEY', 
                                      'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHANNEL_ID']:
                                keys[key] = value
            except Exception as e:
                logger.error(f"Ошибка загрузки .env: {e}")
        
        # Если .env файла нет или ключи не загружены, используем пустые значения
        if not keys:
            keys = {
                'PERPLEXITY_API_KEY': '',
                'OPENAI_API_KEY': '',
                'TELEGRAM_BOT_TOKEN': '',
                'TELEGRAM_CHANNEL_ID': ''
            }
        
        return keys
    
    def save_api_keys(self, api_keys: Dict) -> bool:
        """Сохраняет API ключи в .env файл"""
        try:
            # Читаем существующий .env файл
            env_content = []
            existing_keys = set()
            
            if ENV_FILE.exists():
                with open(ENV_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line_stripped = line.strip()
                        if line_stripped and '=' in line_stripped:
                            key = line_stripped.split('=', 1)[0].strip()
                            if key in ['PERPLEXITY_API_KEY', 'OPENAI_API_KEY', 
                                      'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHANNEL_ID']:
                                existing_keys.add(key)
                                # Пропускаем старое значение, добавим новое позже
                                continue
                        env_content.append(line)
            
            # Добавляем новые/обновленные ключи
            key_mapping = {
                'perplexity': 'PERPLEXITY_API_KEY',
                'openai': 'OPENAI_API_KEY',
                'telegram_bot': 'TELEGRAM_BOT_TOKEN',
                'telegram_channel': 'TELEGRAM_CHANNEL_ID'
            }
            
            for short_key, env_key in key_mapping.items():
                if short_key in api_keys and api_keys[short_key]:
                    env_content.append(f'{env_key}="{api_keys[short_key]}"\n')
            
            # Записываем обратно в файл
            with open(ENV_FILE, 'w', encoding='utf-8') as f:
                f.writelines(env_content)
            
            # Обновляем локальное хранилище
            self.api_keys = self.load_api_keys()
            
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения API ключей: {e}")
            return False
    
    def _merge_configs(self, default: Dict, custom: Dict) -> Dict:
        """Мержит кастомную конфигурацию с дефолтной"""
        result = copy.deepcopy(default)
        
        def merge_dicts(d1, d2):
            for key, value in d2.items():
                if key in d1:
                    if isinstance(d1[key], dict) and isinstance(value, dict):
                        merge_dicts(d1[key], value)
                    else:
                        d1[key] = value
                else:
                    d1[key] = value
        
        merge_dicts(result, custom)
        return result
    
    def save_config(self) -> bool:
        """Сохраняет текущую конфигурацию"""
        try:
            # Добавляем в историю
            self.add_to_history()
            
            # Используем безопасную запись через file_utils
            result = safe_json_write(CONFIG_FILE, self.config)
            if not result:
                return False
            
            # Обновляем конфигурационные файлы Python
            self._update_python_configs()
            
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
            return False
    
    def save_prompts(self) -> bool:
        """Сохраняет кастомные промпты"""
        try:
            with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.prompts, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения промптов: {e}")
            return False
    
    def save_defaults(self):
        """Сохраняет дефолтную конфигурацию"""
        with open(DEFAULT_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    
    def reset_to_defaults(self, section: str = None) -> bool:
        """Сбрасывает настройки к дефолтным"""
        try:
            if section:
                # Сбрасываем только указанную секцию
                if section in DEFAULT_CONFIG:
                    self.config[section] = copy.deepcopy(DEFAULT_CONFIG[section])
                elif section == "prompts":
                    self.prompts = copy.deepcopy(DEFAULT_PROMPTS)
                    self.save_prompts()
            else:
                # Полный сброс
                self.config = copy.deepcopy(DEFAULT_CONFIG)
                self.prompts = copy.deepcopy(DEFAULT_PROMPTS)
                self.save_prompts()
            
            return self.save_config()
        except Exception as e:
            logger.error(f"Ошибка сброса настроек: {e}")
            return False
    
    def add_to_history(self):
        """Добавляет текущее состояние в историю"""
        snapshot = {
            "timestamp": now_msk().isoformat(),
            "config": copy.deepcopy(self.config),
            "prompts": copy.deepcopy(self.prompts)
        }
        
        # Генерируем хеш для дедупликации
        config_hash = hashlib.md5(
            json.dumps(snapshot["config"], sort_keys=True).encode()
        ).hexdigest()
        
        # Проверяем, что конфигурация изменилась
        if not self.history or self.history[-1].get("hash") != config_hash:
            snapshot["hash"] = config_hash
            self.history.append(snapshot)
            
            # Ограничиваем размер истории
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history:]
    
    def restore_from_history(self, index: int) -> bool:
        """Восстанавливает конфигурацию из истории"""
        try:
            if 0 <= index < len(self.history):
                snapshot = self.history[index]
                self.config = copy.deepcopy(snapshot["config"])
                self.prompts = copy.deepcopy(snapshot["prompts"])
                self.save_prompts()
                return self.save_config()
            return False
        except Exception as e:
            logger.error(f"Ошибка восстановления из истории: {e}")
            return False
    
    def _update_python_configs(self):
        """Обновляет Python файлы конфигурации на основе JSON"""
        try:
            # Создаем временный файл с обновленными настройками
            config_updates = []
            
            # API настройки Perplexity
            if "api_models" in self.config and "perplexity" in self.config["api_models"]:
                perplexity = self.config["api_models"]["perplexity"]
                config_updates.append(f'PERPLEXITY_MODEL = "{perplexity.get("model", "sonar-deep-research")}"')
                config_updates.append(f'PERPLEXITY_MAX_TOKENS = {perplexity.get("max_tokens", 8192)}')
                config_updates.append(f'PERPLEXITY_TEMPERATURE = {perplexity.get("temperature", 0.7)}')
                config_updates.append(f'PERPLEXITY_TOP_P = {perplexity.get("top_p", 0.9)}')
                config_updates.append(f'PERPLEXITY_SEARCH_DEPTH = "{perplexity.get("search_depth", "high")}"')
                if perplexity.get("search_recency_filter"):
                    config_updates.append(f'PERPLEXITY_SEARCH_RECENCY = "{perplexity["search_recency_filter"]}"')
            
            # API настройки OpenAI
            if "api_models" in self.config and "openai" in self.config["api_models"]:
                openai = self.config["api_models"]["openai"]
                config_updates.append(f'OPENAI_IMAGE_MODEL = "{openai.get("model", "gpt-image-1")}"')
                config_updates.append(f'OPENAI_IMAGE_QUALITY = "{openai.get("image_quality", "standard")}"')
                if openai.get("image_style"):  # Не все модели имеют стиль
                    config_updates.append(f'OPENAI_IMAGE_STYLE = "{openai["image_style"]}"')
                config_updates.append(f'OPENAI_IMAGE_SIZE = "{openai.get("image_size", "1024x1024")}"')
            
            # Расписание
            if "schedule" in self.config:
                schedule = self.config["schedule"]
                config_updates.append(f'COLLECTION_TIME = "{schedule.get("collection_time", "08:30")}"')
                config_updates.append(f'USER_TIMEZONE = "{schedule.get("user_timezone", "Europe/Moscow")}"')
                config_updates.append(f'PUBLICATIONS_PER_DAY = {schedule.get("publications_per_day", 7)}')
                config_updates.append(f'PUBLICATION_SCHEDULE = {json.dumps(schedule.get("publication_times", []))}')
            
            # Лимиты контента
            if "content" in self.config:
                content = self.config["content"]
                config_updates.append(f'MAX_NEWS_PER_DAY = {content.get("max_news_per_day", 7)}')
                config_updates.append(f'MIN_CONTENT_LENGTH = {content.get("min_content_length", 50)}')
                config_updates.append(f'MAX_CONTENT_LENGTH = {content.get("max_content_length", 1500)}')
                config_updates.append(f'CONTENT_SIMILARITY_THRESHOLD = {content.get("similarity_threshold", 0.7)}')
            
            # Telegram настройки
            if "telegram" in self.config:
                telegram = self.config["telegram"]
                config_updates.append(f'TELEGRAM_MAX_MESSAGE_LENGTH = {telegram.get("max_message_length", 4096)}')
                config_updates.append(f'TELEGRAM_MAX_CAPTION_LENGTH = {telegram.get("max_caption_length", 1024)}')
            
            # Записываем обновления в файл
            updates_file = Path("config_updates.py")
            safe_json_write(updates_file, None)  # Создаем блокировку
            with open(updates_file, 'w', encoding='utf-8') as f:
                f.write("# Автоматически сгенерированные обновления конфигурации\n")
                f.write("# Этот файл обновляется автоматически из веб-интерфейса\n")
                f.write("# НЕ редактируйте его вручную!\n\n")
                f.write("# Сгенерировано: " + str(now_msk()) + "\n\n")
                for update in config_updates:
                    f.write(f"{update}\n")
            
            logger.info("Создан файл config_updates.py с обновлениями")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления Python конфигурации: {e}")
            logger.exception("Детали ошибки:")
            return False
    
    def validate_config(self) -> Dict[str, List[str]]:
        """Валидация конфигурации"""
        errors = []
        warnings = []
        
        # Проверяем API ключи
        if not self.api_keys.get('PERPLEXITY_API_KEY'):
            warnings.append("API ключ Perplexity не настроен")
        
        if not self.api_keys.get('OPENAI_API_KEY'):
            warnings.append("API ключ OpenAI не настроен")
        
        if not self.api_keys.get('TELEGRAM_BOT_TOKEN'):
            warnings.append("Telegram Bot Token не настроен")
        
        if not self.api_keys.get('TELEGRAM_CHANNEL_ID'):
            warnings.append("Telegram Channel ID не настроен")
        
        # Проверяем модели
        perplexity_model = self.config["api_models"]["perplexity"]["model"]
        if perplexity_model not in self.config["api_models"]["perplexity"]["available_models"]:
            warnings.append(f"Модель Perplexity '{perplexity_model}' не в списке доступных")
        
        openai_model = self.config["api_models"]["openai"]["model"]
        if openai_model not in self.config["api_models"]["openai"]["available_models"]:
            warnings.append(f"Модель OpenAI '{openai_model}' не в списке доступных")
        
        # Проверяем расписание
        schedule = self.config["schedule"]["publication_times"]
        # Фильтруем только непустые времена для проверки
        active_times = [t for t in schedule if t and t.strip()]
        
        # Проверяем время
        for time_str in active_times:
            try:
                datetime.strptime(time_str, "%H:%M")
            except ValueError:
                errors.append(f"Неверный формат времени: {time_str}")
        
        # Проверяем лимиты
        if self.config["content"]["min_content_length"] >= self.config["content"]["max_content_length"]:
            errors.append("min_content_length должен быть меньше max_content_length")
        
        return {"errors": errors, "warnings": warnings}


# Создаем глобальный менеджер конфигурации
config_manager = ConfigManager()


@app.route('/')
@requires_auth
def index():
    """Главная страница с формами настроек"""
    validation = config_manager.validate_config()
    
    # Определяем, какой шаблон использовать
    template_name = 'config_modern.html'  # Используем новый современный шаблон
    
    # Проверяем существование шаблона
    template_path = Path('templates') / template_name
    if not template_path.exists():
        template_name = 'config_new.html'  # Fallback на старый шаблон
    
    return render_template(template_name, 
                         config=config_manager.config,
                         prompts=config_manager.prompts,
                         profiles=list(config_manager.profiles.keys()),
                         current_profile=config_manager.current_profile,
                         validation=validation)


@app.route('/api/config', methods=['GET'])
@requires_auth
def get_config():
    """API endpoint для получения текущей конфигурации"""
    # Маскируем API ключи для безопасности
    masked_keys = {}
    for key, value in config_manager.api_keys.items():
        if value:
            # Показываем только первые и последние 4 символа
            if len(value) > 8:
                masked_keys[key] = value[:4] + '*' * (len(value) - 8) + value[-4:]
            else:
                masked_keys[key] = '*' * len(value)
        else:
            masked_keys[key] = ''
    
    return jsonify({
        "config": config_manager.config,
        "prompts": config_manager.prompts,
        "api_keys": masked_keys,
        "profiles": list(config_manager.profiles.keys()),
        "current_profile": config_manager.current_profile,
        "validation": config_manager.validate_config()
    })


@app.route('/api/config', methods=['POST'])
@requires_admin
def update_config():
    """API endpoint для обновления конфигурации"""
    try:
        data = request.json
        
        # Обновляем конфигурацию, сохраняя служебные поля
        if 'config' in data:
            # Сохраняем служебные поля которые не должны меняться из UI
            preserved_fields = {}
            if 'api_models' in config_manager.config:
                if 'perplexity' in config_manager.config['api_models']:
                    preserved_fields['perplexity_available_models'] = config_manager.config['api_models']['perplexity'].get('available_models', [])
                    preserved_fields['perplexity_max_tokens_limits'] = config_manager.config['api_models']['perplexity'].get('max_tokens_limits', {})
                    preserved_fields['perplexity_descriptions'] = config_manager.config['api_models']['perplexity'].get('descriptions', {})
                if 'openai' in config_manager.config['api_models']:
                    preserved_fields['openai_available_models'] = config_manager.config['api_models']['openai'].get('available_models', [])
                    preserved_fields['openai_model_configs'] = config_manager.config['api_models']['openai'].get('model_configs', {})
                    preserved_fields['openai_descriptions'] = config_manager.config['api_models']['openai'].get('descriptions', {})
            
            # Обновляем конфигурацию
            config_manager.config = data['config']
            
            # Восстанавливаем служебные поля
            if preserved_fields:
                if 'api_models' in config_manager.config:
                    if 'perplexity' in config_manager.config['api_models']:
                        config_manager.config['api_models']['perplexity']['available_models'] = preserved_fields.get('perplexity_available_models', [])
                        config_manager.config['api_models']['perplexity']['max_tokens_limits'] = preserved_fields.get('perplexity_max_tokens_limits', {})
                        config_manager.config['api_models']['perplexity']['descriptions'] = preserved_fields.get('perplexity_descriptions', {})
                    if 'openai' in config_manager.config['api_models']:
                        config_manager.config['api_models']['openai']['available_models'] = preserved_fields.get('openai_available_models', [])
                        config_manager.config['api_models']['openai']['model_configs'] = preserved_fields.get('openai_model_configs', {})
                        config_manager.config['api_models']['openai']['descriptions'] = preserved_fields.get('openai_descriptions', {})
        
        if 'prompts' in data:
            config_manager.prompts = data['prompts']
            config_manager.save_prompts()
        
        # Обновляем API ключи если они предоставлены
        if 'api_keys' in data:
            # Сохраняем только непустые и не маскированные ключи
            # Используем правильный маппинг ключей
            clean_keys = {}
            for key, value in data['api_keys'].items():
                if value and '*' not in value:  # Не сохраняем маскированные ключи
                    # Преобразуем ключи к нужному формату для save_api_keys
                    if key == 'PERPLEXITY_API_KEY':
                        clean_keys['perplexity'] = value
                    elif key == 'OPENAI_API_KEY':
                        clean_keys['openai'] = value
                    elif key == 'TELEGRAM_BOT_TOKEN':
                        clean_keys['telegram_bot'] = value
                    elif key == 'TELEGRAM_CHANNEL_ID':
                        clean_keys['telegram_channel'] = value
            
            if clean_keys:
                config_manager.save_api_keys(clean_keys)
        
        # Сохраняем конфигурацию
        if config_manager.save_config():
            return jsonify({
                "success": True,
                "message": "Конфигурация успешно сохранена",
                "validation": config_manager.validate_config()
            })
        else:
            return jsonify({
                "success": False,
                "message": "Ошибка при сохранении конфигурации"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400


@app.route('/api/reset', methods=['POST'])
@requires_admin
def reset_config():
    """API endpoint для сброса к дефолтным настройкам"""
    try:
        section = request.json.get('section')
        
        if config_manager.reset_to_defaults(section):
            return jsonify({
                "success": True,
                "message": f"Настройки {'секции ' + section if section else 'полностью'} сброшены к дефолтным",
                "config": config_manager.config,
                "prompts": config_manager.prompts
            })
        else:
            return jsonify({
                "success": False,
                "message": "Ошибка при сбросе настроек"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400


@app.route('/api/history', methods=['GET'])
def get_history():
    """API endpoint для получения истории изменений"""
    return jsonify({
        "history": config_manager.history,
        "current_index": len(config_manager.history) - 1
    })


@app.route('/api/restore', methods=['POST'])
def restore_from_history():
    """API endpoint для восстановления из истории"""
    try:
        index = request.json.get('index', -1)
        
        if config_manager.restore_from_history(index):
            return jsonify({
                "success": True,
                "message": "Конфигурация восстановлена из истории",
                "config": config_manager.config,
                "prompts": config_manager.prompts
            })
        else:
            return jsonify({
                "success": False,
                "message": "Ошибка при восстановлении из истории"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400


@app.route('/api/export', methods=['GET'])
def export_config():
    """Экспорт конфигурации в JSON"""
    return jsonify({
        "config": config_manager.config,
        "prompts": config_manager.prompts,
        "timestamp": now_msk().isoformat()
    })


@app.route('/api/import', methods=['POST'])
def import_config():
    """Импорт конфигурации из JSON"""
    try:
        data = request.json
        
        if 'config' in data:
            config_manager.config = data['config']
        
        if 'prompts' in data:
            config_manager.prompts = data['prompts']
            config_manager.save_prompts()
        
        if config_manager.save_config():
            return jsonify({
                "success": True,
                "message": "Конфигурация успешно импортирована"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Ошибка при импорте конфигурации"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400


# API для работы с профилями
@app.route('/api/profiles', methods=['GET'])
def get_profiles():
    """Получить список всех профилей"""
    profiles_info = []
    for name, data in config_manager.profiles.items():
        profiles_info.append({
            "name": name,
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "is_current": name == config_manager.current_profile
        })
    return jsonify(profiles_info)


@app.route('/api/profiles/load', methods=['POST'])
def load_profile():
    """Загрузить профиль"""
    try:
        profile_name = request.json.get('profile_name')
        if not profile_name:
            return jsonify({"success": False, "message": "Не указано имя профиля"}), 400
        
        if config_manager.load_profile(profile_name):
            return jsonify({
                "success": True,
                "message": f"Профиль '{profile_name}' загружен",
                "config": config_manager.config,
                "prompts": config_manager.prompts
            })
        else:
            return jsonify({
                "success": False,
                "message": f"Не удалось загрузить профиль '{profile_name}'"
            }), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/profiles/save', methods=['POST'])
@requires_admin
def save_profile():
    """Сохранить текущие настройки в профиль"""
    try:
        profile_name = request.json.get('profile_name', config_manager.current_profile)
        
        if config_manager.save_profile(profile_name):
            return jsonify({
                "success": True,
                "message": f"Профиль '{profile_name}' сохранен"
            })
        else:
            return jsonify({
                "success": False,
                "message": f"Не удалось сохранить профиль '{profile_name}'"
            }), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/profiles/create', methods=['POST'])
def create_profile():
    """Создать новый профиль"""
    try:
        profile_name = request.json.get('profile_name')
        if not profile_name:
            return jsonify({"success": False, "message": "Не указано имя профиля"}), 400
        
        if profile_name in config_manager.profiles:
            return jsonify({"success": False, "message": "Профиль с таким именем уже существует"}), 400
        
        # Сохраняем текущие настройки как новый профиль
        if config_manager.save_profile(profile_name):
            config_manager.current_profile = profile_name
            return jsonify({
                "success": True,
                "message": f"Профиль '{profile_name}' создан"
            })
        else:
            return jsonify({
                "success": False,
                "message": f"Не удалось создать профиль '{profile_name}'"
            }), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/profiles/delete', methods=['POST'])
@requires_admin
def delete_profile():
    """Удалить профиль"""
    try:
        profile_name = request.json.get('profile_name')
        if not profile_name:
            return jsonify({"success": False, "message": "Не указано имя профиля"}), 400
        
        if config_manager.delete_profile(profile_name):
            return jsonify({
                "success": True,
                "message": f"Профиль '{profile_name}' удален"
            })
        else:
            return jsonify({
                "success": False,
                "message": f"Не удалось удалить профиль '{profile_name}'"
            }), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/profiles/duplicate', methods=['POST'])
def duplicate_profile():
    """Дублировать профиль"""
    try:
        source_name = request.json.get('source_name')
        new_name = request.json.get('new_name')
        
        if not source_name or not new_name:
            return jsonify({"success": False, "message": "Не указаны имена профилей"}), 400
        
        if config_manager.duplicate_profile(source_name, new_name):
            return jsonify({
                "success": True,
                "message": f"Профиль '{new_name}' создан как копия '{source_name}'"
            })
        else:
            return jsonify({
                "success": False,
                "message": f"Не удалось дублировать профиль"
            }), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/timezones', methods=['GET'])
def get_timezones():
    """API endpoint для получения списка часовых поясов"""
    try:
        timezones = get_all_timezones_with_offset()
        return jsonify({
            "success": True,
            "timezones": [
                {
                    "value": tz[0],
                    "label": f"{tz[1]} ({tz[2]})",
                    "offset": tz[2]
                }
                for tz in timezones
            ],
            "current": config_manager.config["schedule"].get("user_timezone", "Europe/Moscow")
        })
    except Exception as e:
        logger.error(f"Ошибка получения часовых поясов: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/schedule/preview', methods=['POST'])
def preview_schedule():
    """API endpoint для предпросмотра расписания в разных часовых поясах"""
    try:
        data = request.json
        schedule = data.get('schedule', [])
        user_tz = data.get('user_timezone', 'Europe/Moscow')
        
        preview = format_schedule_preview(schedule, user_tz)
        
        return jsonify({
            "success": True,
            "preview": preview,
            "user_timezone": user_tz
        })
    except Exception as e:
        logger.error(f"Ошибка предпросмотра расписания: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/schedule/auto-distribute', methods=['POST'])
def auto_distribute_schedule():
    """API endpoint для автоматического распределения времён публикации"""
    try:
        data = request.json
        publications_count = min(24, max(1, data.get('publications_count', 7)))  # Ограничиваем от 1 до 24
        start_time = data.get('start_time', '09:00')
        end_time = data.get('end_time', '21:00')
        
        # Парсим время начала и конца
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        
        # Вычисляем общее количество минут
        total_minutes = (end_hour * 60 + end_min) - (start_hour * 60 + start_min)
        
        # Распределяем равномерно
        if publications_count <= 1:
            schedule = [start_time]
        else:
            interval = total_minutes // (publications_count - 1)
            schedule = []
            for i in range(publications_count):
                minutes = (start_hour * 60 + start_min) + (interval * i)
                hour = minutes // 60
                minute = minutes % 60
                schedule.append(f"{hour:02d}:{minute:02d}")
        
        return jsonify({
            "success": True,
            "schedule": schedule[:publications_count]
        })
    except Exception as e:
        logger.error(f"Ошибка автоматического распределения: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/schedule/convert', methods=['POST'])
def convert_schedule_timezone():
    """API endpoint для конвертации расписания между часовыми поясами"""
    try:
        data = request.json
        # Поддерживаем оба варианта названия параметра для совместимости
        times = data.get('times') or data.get('schedule', [])
        from_tz = data.get('from_timezone', 'Europe/Moscow')
        to_tz = data.get('to_timezone', 'Europe/Moscow')
        
        if from_tz == to_tz:
            return jsonify({
                "success": True,
                "converted_times": times,
                "schedule": times  # Для обратной совместимости
            })
        
        # Конвертируем каждое время
        converted = []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for time_str in times:
            try:
                # Парсим время в исходном часовом поясе
                dt = parse_time_string(time_str, today, from_tz)
                # Конвертируем в целевой часовой пояс
                converted_dt = dt.astimezone(get_timezone(to_tz))
                converted.append(converted_dt.strftime("%H:%M"))
            except Exception as e:
                logger.warning(f"Не удалось конвертировать время '{time_str}': {e}")
                converted.append(time_str)  # Оставляем как есть при ошибке
        
        return jsonify({
            "success": True,
            "converted_times": converted,
            "schedule": converted  # Для обратной совместимости
        })
    except Exception as e:
        logger.error(f"Ошибка конвертации расписания: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def main():
    """Запуск веб-сервера"""
    logger.info("🚀 Запуск веб-интерфейса конфигурации...")
    logger.info("📍 Откройте http://localhost:5000 в браузере")
    
    # Проверяем и создаем необходимые директории
    Path("templates").mkdir(exist_ok=True)
    Path("static").mkdir(exist_ok=True)
    
    # Запускаем сервер
    app.run(debug=True, host='0.0.0.0', port=5000)


if __name__ == "__main__":
    main()