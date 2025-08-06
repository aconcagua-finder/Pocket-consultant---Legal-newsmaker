#!/usr/bin/env python3
"""
Web интерфейс для управления настройками NEWSMAKER (версия для GitHub)

Позволяет редактировать все параметры системы через удобный веб-интерфейс.
"""

import json
import os
import copy
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_cors import CORS
from typing import Dict, Any, List
from loguru import logger
import hashlib
import secrets

# Импортируем модули проекта
from timezone_utils import now_msk

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # Генерируем случайный секретный ключ
CORS(app)

# Путь к файлу конфигурации
CONFIG_FILE = Path("config_web.json")
DEFAULT_CONFIG_FILE = Path("config_defaults.json")
PROMPTS_FILE = Path("prompts_custom.json")
ENV_FILE = Path(".env")

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
            "temperature": 0.7,
            "top_p": 0.9,
            "timeout": 300
        },
        "openai": {
            "model": "gpt-image-1",  # Самая новая и крутая модель
            "available_models": [
                "dall-e-2",
                "dall-e-3",
                "gpt-image-1"
            ],
            "image_quality": "standard",
            "quality_options": ["standard", "hd"],
            "image_style": "vivid",
            "style_options": ["vivid", "natural"],
            "image_size": "1024x1024",
            "size_options": ["1024x1024", "1024x1792", "1792x1024"],
            "timeout": 120
        }
    },
    "schedule": {
        "collection_time": "08:30",
        "publication_times": [
            "09:05",
            "11:03", 
            "13:07",
            "15:09",
            "17:05",
            "19:02",
            "21:07"
        ],
        "timezone": "Europe/Moscow"
    },
    "content": {
        "max_news_per_day": 7,
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
        ]
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
    """Менеджер конфигурации с поддержкой истории изменений"""
    
    def __init__(self):
        self.config = self.load_config()
        self.prompts = self.load_prompts()
        self.api_keys = self.load_api_keys()
        self.history = []
        self.max_history = 10
        
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
        
        # Для GitHub версии - не показываем реальные ключи
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
            
            # Сохраняем конфигурацию
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
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
            
            # API настройки
            config_updates.append(f'PERPLEXITY_MODEL = "{self.config["api_models"]["perplexity"]["model"]}"')
            config_updates.append(f'PERPLEXITY_MAX_TOKENS = {self.config["api_models"]["perplexity"]["max_tokens"]}')
            config_updates.append(f'OPENAI_IMAGE_MODEL = "{self.config["api_models"]["openai"]["model"]}"')
            config_updates.append(f'OPENAI_IMAGE_QUALITY = "{self.config["api_models"]["openai"]["image_quality"]}"')
            config_updates.append(f'OPENAI_IMAGE_STYLE = "{self.config["api_models"]["openai"]["image_style"]}"')
            config_updates.append(f'OPENAI_IMAGE_SIZE = "{self.config["api_models"]["openai"]["image_size"]}"')
            
            # Расписание
            config_updates.append(f'COLLECTION_TIME = "{self.config["schedule"]["collection_time"]}"')
            config_updates.append(f'PUBLICATION_SCHEDULE = {json.dumps(self.config["schedule"]["publication_times"])}')
            
            # Лимиты
            config_updates.append(f'MAX_NEWS_PER_DAY = {self.config["content"]["max_news_per_day"]}')
            config_updates.append(f'MIN_CONTENT_LENGTH = {self.config["content"]["min_content_length"]}')
            config_updates.append(f'MAX_CONTENT_LENGTH = {self.config["content"]["max_content_length"]}')
            
            # Записываем обновления в файл
            updates_file = Path("config_updates.py")
            with open(updates_file, 'w', encoding='utf-8') as f:
                f.write("# Автоматически сгенерированные обновления конфигурации\n")
                f.write("# Импортируйте этот файл в config.py для применения изменений\n\n")
                for update in config_updates:
                    f.write(f"{update}\n")
            
            logger.info("Создан файл config_updates.py с обновлениями")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления Python конфигурации: {e}")
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
        if len(schedule) != self.config["content"]["max_news_per_day"]:
            warnings.append(f"Количество времён публикации ({len(schedule)}) не совпадает с max_news_per_day ({self.config['content']['max_news_per_day']})")
        
        # Проверяем время
        for time_str in schedule:
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
def index():
    """Главная страница с формами настроек"""
    validation = config_manager.validate_config()
    return render_template('config.html', 
                         config=config_manager.config,
                         prompts=config_manager.prompts,
                         validation=validation)


@app.route('/api/config', methods=['GET'])
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
        "validation": config_manager.validate_config()
    })


@app.route('/api/config', methods=['POST'])
def update_config():
    """API endpoint для обновления конфигурации"""
    try:
        data = request.json
        
        # Обновляем конфигурацию
        if 'config' in data:
            config_manager.config = data['config']
        
        if 'prompts' in data:
            config_manager.prompts = data['prompts']
            config_manager.save_prompts()
        
        # Обновляем API ключи если они предоставлены
        if 'api_keys' in data:
            # Сохраняем только непустые и не маскированные ключи
            clean_keys = {}
            for key, value in data['api_keys'].items():
                if value and '*' not in value:  # Не сохраняем маскированные ключи
                    clean_keys[key] = value
            
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