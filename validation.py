"""
Модуль валидации данных для NEWSMAKER

Обеспечивает проверку корректности входных данных,
валидацию API ответов и проверку целостности файлов.
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from loguru import logger

import config
from types_models import (
    NewsItem, NewsFileData, TelegramMessage,
    validate_news_item, NewsPriority
)


# ========================================================================
# ВАЛИДАЦИЯ НОВОСТЕЙ
# ========================================================================

def validate_news_content(content: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует содержимое новости
    
    Args:
        content: Текст новости
        
    Returns:
        Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
    """
    # Проверка длины
    if not content:
        return False, "Контент пустой"
    
    if len(content) < config.MIN_CONTENT_LENGTH:
        return False, f"Контент слишком короткий (минимум {config.MIN_CONTENT_LENGTH} символов)"
    
    if len(content) > config.MAX_CONTENT_LENGTH:
        return False, f"Контент слишком длинный (максимум {config.MAX_CONTENT_LENGTH} символов)"
    
    # Проверка на наличие обязательных элементов
    if '📜' not in content and 'КОММЕНТАРИЙ' not in content:
        return False, "Отсутствует структура новости (заголовок и комментарий)"
    
    return True, None


def validate_news_sources(sources: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Валидирует источники новости
    
    Args:
        sources: Список URL источников
        
    Returns:
        Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
    """
    if not sources:
        return False, "Нет источников"
    
    url_pattern = re.compile(
        r'^https?://'  # http:// или https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # домен
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # или IP
        r'(?::\d+)?'  # опциональный порт
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    for source in sources:
        if not url_pattern.match(source):
            return False, f"Некорректный URL источника: {source}"
    
    return True, None


def validate_news_priority(priority: int) -> Tuple[bool, Optional[str]]:
    """
    Валидирует приоритет новости
    
    Args:
        priority: Приоритет (1-24)
        
    Returns:
        Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
    """
    if not isinstance(priority, int):
        return False, "Приоритет должен быть числом"
    
    # Поддерживаем до 24 публикаций в день
    max_priority = config.PUBLICATIONS_PER_DAY if hasattr(config, 'PUBLICATIONS_PER_DAY') else 7
    
    if priority < 1 or priority > max_priority:
        return False, f"Приоритет должен быть от 1 до {max_priority}, получен {priority}"
    
    return True, None


def validate_news_item_full(news: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Полная валидация элемента новости
    
    Args:
        news: Словарь с данными новости
        
    Returns:
        Tuple[bool, List[str]]: (валидность, список ошибок)
    """
    errors = []
    
    # Проверка структуры
    if not validate_news_item(news):
        errors.append("Некорректная структура новости")
    
    # Проверка контента
    if 'content' in news:
        valid, error = validate_news_content(news['content'])
        if not valid:
            errors.append(f"Контент: {error}")
        
        # Проверка актуальности даты
        is_fresh, date_reason = is_content_fresh(news['content'])
        if not is_fresh:
            errors.append(f"Актуальность: {date_reason}")
    
    # Проверка источников
    if 'sources' in news:
        valid, error = validate_news_sources(news['sources'])
        if not valid:
            errors.append(f"Источники: {error}")
    
    # Проверка приоритета
    if 'priority' in news:
        valid, error = validate_news_priority(news['priority'])
        if not valid:
            errors.append(f"Приоритет: {error}")
    
    # Проверка времени публикации
    if 'scheduled_time' in news:
        if not validate_time_format(news['scheduled_time']):
            errors.append(f"Неверный формат времени: {news['scheduled_time']}")
    
    return len(errors) == 0, errors


# ========================================================================
# ВАЛИДАЦИЯ ВРЕМЕНИ И ДАТ
# ========================================================================

def extract_date_from_content(content: str) -> Optional[datetime]:
    """
    Извлекает дату из контента новости
    
    Args:
        content: Текст новости
        
    Returns:
        datetime или None если дата не найдена
    """
    # Паттерны для поиска дат
    patterns = [
        r'(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})',
        r'с\s+(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)',
        r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
        r'(\d{4})-(\d{1,2})-(\d{1,2})'
    ]
    
    months = {
        'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
        'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
        'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
    }
    
    for pattern in patterns:
        matches = re.findall(pattern, content.lower())
        for match in matches:
            try:
                if len(match) == 3:
                    if match[1] in months:
                        # Формат: "день месяц год"
                        day, month_name, year = match
                        month = months[month_name]
                        return datetime(int(year), month, int(day))
                    else:
                        # Формат: "день.месяц.год" или "год-месяц-день"
                        if '.' in content:
                            day, month, year = match
                            return datetime(int(year), int(month), int(day))
                        else:
                            year, month, day = match
                            return datetime(int(year), int(month), int(day))
            except (ValueError, KeyError):
                continue
                
    return None


def is_content_fresh(content: str, max_age_days: int = 3) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, свежий ли контент новости
    
    Args:
        content: Текст новости
        max_age_days: Максимальный возраст в днях
        
    Returns:
        (is_fresh, reason) - свежая ли новость и причина
    """
    extracted_date = extract_date_from_content(content)
    
    if not extracted_date:
        return False, "Не удалось извлечь дату из контента"
    
    now = datetime.now()
    age = (now - extracted_date).days
    
    if age < 0:
        return True, f"Будущая дата (вступает в силу {extracted_date.strftime('%d.%m.%Y')})"
    elif age <= max_age_days:
        return True, f"Свежая новость ({age} дн. назад, {extracted_date.strftime('%d.%m.%Y')})"
    else:
        return False, f"Устаревшая новость ({age} дн. назад, {extracted_date.strftime('%d.%m.%Y')})"


def get_date_feedback_for_next_prompt(content: str) -> str:
    """
    Генерирует обратную связь для следующего запроса к Perplexity
    
    Args:
        content: Текст предыдущей новости
        
    Returns:
        Текст с рекомендациями для улучшения поиска
    """
    is_fresh, reason = is_content_fresh(content)
    
    if not is_fresh:
        return f"""
ПРОБЛЕМА С ПРЕДЫДУЩИМ РЕЗУЛЬТАТОМ: {reason}

ТРЕБОВАНИЯ ДЛЯ НОВОГО ПОИСКА:
- Ищи ТОЛЬКО новости за последние 2-3 дня
- Проверяй дату публикации в источнике
- Если нет свежих новостей - лучше написать про изменения, которые вступают в силу в ближайшие 2 недели
- ОБЯЗАТЕЛЬНО укажи точную дату в тексте
        """
    else:
        return "Предыдущий поиск был успешным по актуальности дат."

def validate_time_format(time_str: str) -> bool:
    """
    Проверяет формат времени HH:MM
    
    Args:
        time_str: Строка времени
        
    Returns:
        bool: True если формат корректный
    """
    pattern = re.compile(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$')
    return bool(pattern.match(time_str))


def validate_date_format(date_str: str) -> bool:
    """
    Проверяет формат даты YYYY-MM-DD
    
    Args:
        date_str: Строка даты
        
    Returns:
        bool: True если формат корректный
    """
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_datetime_iso(datetime_str: str) -> bool:
    """
    Проверяет ISO формат datetime
    
    Args:
        datetime_str: Строка datetime
        
    Returns:
        bool: True если формат корректный
    """
    try:
        datetime.fromisoformat(datetime_str)
        return True
    except (ValueError, TypeError):
        return False


# ========================================================================
# ВАЛИДАЦИЯ API ОТВЕТОВ
# ========================================================================

def validate_perplexity_response(response: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Валидирует ответ от Perplexity API
    
    Args:
        response: Ответ API
        
    Returns:
        Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
    """
    if not response:
        return False, "Пустой ответ"
    
    if 'choices' not in response:
        return False, "Отсутствует поле 'choices'"
    
    if not response['choices']:
        return False, "Пустой список 'choices'"
    
    if 'message' not in response['choices'][0]:
        return False, "Отсутствует 'message' в первом элементе"
    
    if 'content' not in response['choices'][0]['message']:
        return False, "Отсутствует 'content' в сообщении"
    
    content = response['choices'][0]['message']['content']
    if not content or not isinstance(content, str):
        return False, "Контент пустой или не является строкой"
    
    return True, None


def validate_openai_image_response(response: Any) -> Tuple[bool, Optional[str]]:
    """
    Валидирует ответ от OpenAI Image API
    
    Args:
        response: Ответ API
        
    Returns:
        Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
    """
    if not response:
        return False, "Пустой ответ"
    
    if not hasattr(response, 'data'):
        return False, "Отсутствует поле 'data'"
    
    if not response.data:
        return False, "Пустой список изображений"
    
    first_image = response.data[0]
    
    # Проверяем наличие URL или base64
    has_url = hasattr(first_image, 'url') and first_image.url
    has_b64 = hasattr(first_image, 'b64_json') and first_image.b64_json
    
    if not has_url and not has_b64:
        return False, "Отсутствует URL и base64 данные"
    
    return True, None


# ========================================================================
# ВАЛИДАЦИЯ ФАЙЛОВ
# ========================================================================

def validate_json_file(filepath: Path) -> Tuple[bool, Optional[str]]:
    """
    Проверяет корректность JSON файла
    
    Args:
        filepath: Путь к файлу
        
    Returns:
        Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
    """
    if not filepath.exists():
        return False, "Файл не существует"
    
    if not filepath.is_file():
        return False, "Путь не является файлом"
    
    if filepath.suffix != '.json':
        return False, "Файл не имеет расширение .json"
    
    try:
        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            json.load(f)
        return True, None
    except json.JSONDecodeError as e:
        return False, f"Ошибка парсинга JSON: {e}"
    except Exception as e:
        return False, f"Ошибка чтения файла: {e}"


def validate_news_file(filepath: Path) -> Tuple[bool, List[str]]:
    """
    Валидирует файл с новостями
    
    Args:
        filepath: Путь к файлу новостей
        
    Returns:
        Tuple[bool, List[str]]: (валидность, список ошибок)
    """
    errors = []
    
    # Проверка файла
    valid, error = validate_json_file(filepath)
    if not valid:
        errors.append(error)
        return False, errors
    
    # Загрузка и проверка структуры
    try:
        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Проверка основных полей
        required_fields = ['date', 'collected_at', 'total_news', 'news']
        for field in required_fields:
            if field not in data:
                errors.append(f"Отсутствует обязательное поле '{field}'")
        
        if errors:
            return False, errors
        
        # Проверка даты
        if not validate_date_format(data['date']):
            errors.append(f"Неверный формат даты: {data['date']}")
        
        # Проверка времени сбора
        if not validate_datetime_iso(data['collected_at']):
            errors.append(f"Неверный формат времени сбора: {data['collected_at']}")
        
        # Проверка новостей
        if not isinstance(data['news'], list):
            errors.append("Поле 'news' должно быть списком")
        else:
            # Проверяем каждую новость
            for i, news in enumerate(data['news']):
                news_valid, news_errors = validate_news_item_full(news)
                if not news_valid:
                    errors.append(f"Новость {i+1}: {'; '.join(news_errors)}")
        
        # Проверка соответствия количества
        if len(data['news']) != data['total_news']:
            errors.append(f"Несоответствие количества: указано {data['total_news']}, найдено {len(data['news'])}")
        
    except Exception as e:
        errors.append(f"Ошибка при обработке файла: {e}")
    
    return len(errors) == 0, errors


def validate_image_file(filepath: Path) -> Tuple[bool, Optional[str]]:
    """
    Проверяет корректность файла изображения
    
    Args:
        filepath: Путь к изображению
        
    Returns:
        Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
    """
    if not filepath.exists():
        return False, "Файл не существует"
    
    if not filepath.is_file():
        return False, "Путь не является файлом"
    
    # Проверка расширения
    valid_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    if filepath.suffix.lower() not in valid_extensions:
        return False, f"Неподдерживаемое расширение: {filepath.suffix}"
    
    # Проверка размера
    file_size = filepath.stat().st_size
    max_size = 10 * 1024 * 1024  # 10MB
    if file_size > max_size:
        return False, f"Файл слишком большой: {file_size} байт (максимум {max_size})"
    
    if file_size == 0:
        return False, "Файл пустой"
    
    return True, None


# ========================================================================
# ВАЛИДАЦИЯ ПАРАМЕТРОВ РАСПИСАНИЯ
# ========================================================================

def validate_timezone(tz_name: str) -> Tuple[bool, Optional[str]]:
    """
    Валидирует название часового пояса
    
    Args:
        tz_name: Название часового пояса (например, "Europe/Moscow")
        
    Returns:
        Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
    """
    try:
        from timezone_utils import get_timezone
        get_timezone(tz_name)
        return True, None
    except Exception as e:
        return False, f"Некорректный часовой пояс: {tz_name}"


def validate_publications_count(count: int) -> Tuple[bool, Optional[str]]:
    """
    Валидирует количество публикаций в день
    
    Args:
        count: Количество публикаций
        
    Returns:
        Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
    """
    if not isinstance(count, int):
        return False, "Количество публикаций должно быть числом"
    
    if count < 1:
        return False, "Количество публикаций должно быть минимум 1"
    
    if count > 24:
        return False, "Количество публикаций не может превышать 24"
    
    return True, None


def validate_publication_schedule(schedule: List[str], count: int) -> Tuple[bool, Optional[str]]:
    """
    Валидирует расписание публикаций
    
    Args:
        schedule: Список времён публикации
        count: Ожидаемое количество публикаций
        
    Returns:
        Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
    """
    if len(schedule) < count:
        return False, f"Недостаточно времён в расписании: {len(schedule)} из {count}"
    
    # Проверяем формат времени
    time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')
    for time_str in schedule[:count]:
        if not time_pattern.match(time_str):
            return False, f"Некорректный формат времени: {time_str}"
    
    # Проверяем уникальность времён
    unique_times = set(schedule[:count])
    if len(unique_times) != count:
        return False, "В расписании есть дублирующиеся времена"
    
    return True, None


# ========================================================================
# ВАЛИДАЦИЯ КОНФИГУРАЦИИ
# ========================================================================

def validate_api_keys() -> Tuple[bool, List[str]]:
    """
    Проверяет наличие и корректность API ключей
    
    Returns:
        Tuple[bool, List[str]]: (все ключи валидны, список проблем)
    """
    issues = []
    
    # Perplexity API
    if not config.PERPLEXITY_API_KEY:
        issues.append("PERPLEXITY_API_KEY не установлен")
    elif not config.PERPLEXITY_API_KEY.startswith('pplx-'):
        issues.append("PERPLEXITY_API_KEY имеет неверный формат")
    
    # OpenAI API
    if not config.OPENAI_API_KEY:
        issues.append("OPENAI_API_KEY не установлен")
    elif not config.OPENAI_API_KEY.startswith('sk-'):
        issues.append("OPENAI_API_KEY имеет неверный формат")
    
    # Telegram
    if not config.TELEGRAM_BOT_TOKEN:
        issues.append("TELEGRAM_BOT_TOKEN не установлен")
    elif ':' not in config.TELEGRAM_BOT_TOKEN:
        issues.append("TELEGRAM_BOT_TOKEN имеет неверный формат")
    
    if not config.TELEGRAM_CHANNEL_ID:
        issues.append("TELEGRAM_CHANNEL_ID не установлен")
    elif not config.TELEGRAM_CHANNEL_ID.startswith(('@', '-')):
        issues.append("TELEGRAM_CHANNEL_ID должен начинаться с @ или -")
    
    return len(issues) == 0, issues


def validate_schedule() -> Tuple[bool, List[str]]:
    """
    Проверяет корректность расписания
    
    Returns:
        Tuple[bool, List[str]]: (расписание валидно, список проблем)
    """
    issues = []
    
    # Проверка времени сбора
    if not validate_time_format(config.COLLECTION_TIME):
        issues.append(f"Неверный формат времени сбора: {config.COLLECTION_TIME}")
    
    # Проверка расписания публикаций
    if len(config.PUBLICATION_SCHEDULE) != config.MAX_NEWS_PER_DAY:
        issues.append(
            f"Несоответствие расписания: {len(config.PUBLICATION_SCHEDULE)} времён "
            f"для {config.MAX_NEWS_PER_DAY} новостей"
        )
    
    for i, time_str in enumerate(config.PUBLICATION_SCHEDULE, 1):
        if not validate_time_format(time_str):
            issues.append(f"Неверный формат времени публикации {i}: {time_str}")
    
    return len(issues) == 0, issues


# ========================================================================
# ГЛАВНАЯ ФУНКЦИЯ ВАЛИДАЦИИ
# ========================================================================

def run_full_validation() -> bool:
    """
    Запускает полную валидацию системы
    
    Returns:
        bool: True если всё валидно
    """
    logger.info("🔍 Запуск полной валидации системы...")
    all_valid = True
    
    # Валидация API ключей
    logger.info("Проверка API ключей...")
    valid, issues = validate_api_keys()
    if not valid:
        all_valid = False
        for issue in issues:
            logger.error(f"  ❌ {issue}")
    else:
        logger.info("  ✅ API ключи корректны")
    
    # Валидация расписания
    logger.info("Проверка расписания...")
    valid, issues = validate_schedule()
    if not valid:
        all_valid = False
        for issue in issues:
            logger.error(f"  ❌ {issue}")
    else:
        logger.info("  ✅ Расписание корректно")
    
    # Проверка директорий
    logger.info("Проверка директорий...")
    for dir_path in [config.DATA_DIR, config.LOGS_DIR, config.IMAGES_DIR]:
        if not dir_path.exists():
            logger.warning(f"  ⚠️ Директория не существует: {dir_path}")
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"  ✅ Создана директория: {dir_path}")
        else:
            logger.info(f"  ✅ Директория существует: {dir_path}")
    
    # Итог
    if all_valid:
        logger.info("🎉 Валидация пройдена успешно!")
    else:
        logger.warning("⚠️ Обнаружены проблемы при валидации")
    
    return all_valid


# ========================================================================
# ТЕСТЫ
# ========================================================================

def test_validation_functions():
    """Тестирует функции валидации"""
    logger.info("🧪 Тестирование функций валидации...")
    
    # Тест валидации времени
    assert validate_time_format("08:30") == True
    assert validate_time_format("25:00") == False
    assert validate_time_format("8:30") == False
    
    # Тест валидации даты
    assert validate_date_format("2025-01-15") == True
    assert validate_date_format("15-01-2025") == False
    
    # Тест валидации приоритета
    assert validate_news_priority(1)[0] == True
    assert validate_news_priority(7)[0] == True
    assert validate_news_priority(0)[0] == False
    assert validate_news_priority(8)[0] == False
    
    # Тест извлечения даты из контента
    test_content = "С 1 июля 2025 года вступает в силу новый закон"
    extracted = extract_date_from_content(test_content)
    assert extracted is not None
    assert extracted.month == 7
    
    logger.info("✅ Тесты валидации пройдены")


if __name__ == "__main__":
    test_validation_functions()
    run_full_validation()