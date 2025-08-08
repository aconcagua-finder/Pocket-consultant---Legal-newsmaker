"""
Утилиты для работы с часовыми поясами и временем

Обеспечивает корректную работу с московским временем (МСК)
и преобразования между часовыми поясами.
"""

from datetime import datetime, timedelta, timezone, time
from typing import Optional, Union, List, Dict
from zoneinfo import ZoneInfo
from loguru import logger

import config


# ========================================================================
# КОНСТАНТЫ ЧАСОВЫХ ПОЯСОВ
# ========================================================================

# Московское время через ZoneInfo для автоматического учета DST
try:
    MSK = ZoneInfo("Europe/Moscow")
except Exception:
    # Fallback на фиксированное смещение если ZoneInfo недоступен
    MSK = timezone(timedelta(hours=3))
    logger.warning("ZoneInfo недоступен, используется фиксированное смещение UTC+3")

UTC = timezone.utc

# Список популярных часовых поясов для выбора в интерфейсе
POPULAR_TIMEZONES = [
    ("Europe/Moscow", "Москва (МСК)"),
    ("Europe/Kaliningrad", "Калининград"),
    ("Europe/Samara", "Самара"),
    ("Asia/Yekaterinburg", "Екатеринбург"),
    ("Asia/Omsk", "Омск"),
    ("Asia/Krasnoyarsk", "Красноярск"),
    ("Asia/Irkutsk", "Иркутск"),
    ("Asia/Yakutsk", "Якутск"),
    ("Asia/Vladivostok", "Владивосток"),
    ("Asia/Magadan", "Магадан"),
    ("Asia/Kamchatka", "Камчатка"),
    ("Europe/Kiev", "Киев"),
    ("Europe/Minsk", "Минск"),
    ("Asia/Almaty", "Алматы"),
    ("Asia/Tashkent", "Ташкент"),
    ("Asia/Baku", "Баку"),
    ("Asia/Yerevan", "Ереван"),
    ("Asia/Tbilisi", "Тбилиси"),
    ("Europe/Berlin", "Берлин"),
    ("Europe/London", "Лондон"),
    ("Europe/Paris", "Париж"),
    ("America/New_York", "Нью-Йорк"),
    ("America/Los_Angeles", "Лос-Анджелес"),
    ("Asia/Dubai", "Дубай"),
    ("Asia/Tokyo", "Токио"),
    ("Asia/Shanghai", "Шанхай"),
    ("Australia/Sydney", "Сидней")
]


# ========================================================================
# ФУНКЦИИ ПОЛУЧЕНИЯ ВРЕМЕНИ
# ========================================================================

def now_msk() -> datetime:
    """
    Возвращает текущее время в МСК с учетом часового пояса
    
    Returns:
        datetime: Текущее время в МСК
    """
    return datetime.now(MSK)


def now_utc() -> datetime:
    """
    Возвращает текущее время в UTC
    
    Returns:
        datetime: Текущее время в UTC
    """
    return datetime.now(UTC)


def today_msk() -> datetime:
    """
    Возвращает сегодняшнюю дату в МСК (начало дня)
    
    Returns:
        datetime: Сегодня 00:00:00 МСК
    """
    now = now_msk()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def yesterday_msk() -> datetime:
    """
    Возвращает вчерашнюю дату в МСК (начало дня)
    
    Returns:
        datetime: Вчера 00:00:00 МСК
    """
    return today_msk() - timedelta(days=1)


def tomorrow_msk() -> datetime:
    """
    Возвращает завтрашнюю дату в МСК (начало дня)
    
    Returns:
        datetime: Завтра 00:00:00 МСК
    """
    return today_msk() + timedelta(days=1)


# ========================================================================
# ФУНКЦИИ ПРЕОБРАЗОВАНИЯ
# ========================================================================

def get_timezone(tz_name: str) -> Union[ZoneInfo, timezone]:
    """
    Получает объект часового пояса по имени
    
    Args:
        tz_name: Имя часового пояса (например, "Europe/Moscow")
        
    Returns:
        ZoneInfo или timezone объект
    """
    try:
        return ZoneInfo(tz_name)
    except Exception:
        # Если не удалось создать ZoneInfo, пытаемся вернуть МСК по умолчанию
        logger.warning(f"Не удалось создать ZoneInfo для {tz_name}, используется МСК")
        return MSK


def now_in_timezone(tz_name: str) -> datetime:
    """
    Возвращает текущее время в указанном часовом поясе
    
    Args:
        tz_name: Имя часового пояса
        
    Returns:
        datetime: Текущее время в указанном часовом поясе
    """
    tz = get_timezone(tz_name)
    return datetime.now(tz)


def convert_timezone(dt: datetime, from_tz: str, to_tz: str) -> datetime:
    """
    Конвертирует время из одного часового пояса в другой
    
    Args:
        dt: Дата и время
        from_tz: Исходный часовой пояс
        to_tz: Целевой часовой пояс
        
    Returns:
        datetime: Время в целевом часовом поясе
    """
    # Если datetime naive, добавляем исходный часовой пояс
    if dt.tzinfo is None:
        source_tz = get_timezone(from_tz)
        dt = dt.replace(tzinfo=source_tz)
    
    # Конвертируем в целевой часовой пояс
    target_tz = get_timezone(to_tz)
    return dt.astimezone(target_tz)


def to_user_timezone(dt: datetime, user_tz: str) -> datetime:
    """
    Преобразует МСК время в часовой пояс пользователя
    
    Args:
        dt: Время в МСК
        user_tz: Часовой пояс пользователя
        
    Returns:
        datetime: Время в часовом поясе пользователя
    """
    # Если нет timezone, считаем что это МСК
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MSK)
    elif dt.tzinfo != MSK:
        dt = dt.astimezone(MSK)
    
    # Конвертируем в пояс пользователя
    target_tz = get_timezone(user_tz)
    return dt.astimezone(target_tz)


def from_user_timezone(dt: datetime, user_tz: str) -> datetime:
    """
    Преобразует время из часового пояса пользователя в МСК
    
    Args:
        dt: Время в часовом поясе пользователя
        user_tz: Часовой пояс пользователя
        
    Returns:
        datetime: Время в МСК
    """
    # Если нет timezone, добавляем пользовательский
    if dt.tzinfo is None:
        source_tz = get_timezone(user_tz)
        dt = dt.replace(tzinfo=source_tz)
    
    # Конвертируем в МСК
    return dt.astimezone(MSK)


def to_msk(dt: datetime) -> datetime:
    """
    Преобразует datetime в МСК
    
    Args:
        dt: Дата и время (с или без timezone)
        
    Returns:
        datetime: Время в МСК
    """
    if dt.tzinfo is None:
        # Если нет timezone, считаем что это МСК
        return dt.replace(tzinfo=MSK)
    else:
        # Конвертируем в МСК
        return dt.astimezone(MSK)


def to_utc(dt: datetime) -> datetime:
    """
    Преобразует datetime в UTC
    
    Args:
        dt: Дата и время (с или без timezone)
        
    Returns:
        datetime: Время в UTC
    """
    if dt.tzinfo is None:
        # Если нет timezone, считаем что это МСК и конвертируем
        msk_dt = dt.replace(tzinfo=MSK)
        return msk_dt.astimezone(UTC)
    else:
        return dt.astimezone(UTC)


def naive_to_msk(dt: datetime) -> datetime:
    """
    Добавляет МСК timezone к naive datetime
    
    Args:
        dt: Naive datetime (без timezone)
        
    Returns:
        datetime: Datetime с МСК timezone
    """
    if dt.tzinfo is not None:
        logger.warning(f"datetime уже имеет timezone: {dt.tzinfo}")
        return dt.astimezone(MSK)
    
    return dt.replace(tzinfo=MSK)


# ========================================================================
# ФУНКЦИИ ФОРМАТИРОВАНИЯ
# ========================================================================

def format_msk_time(dt: Optional[datetime] = None, fmt: str = "%d.%m.%Y %H:%M:%S") -> str:
    """
    Форматирует время в МСК для отображения
    
    Args:
        dt: Datetime для форматирования (по умолчанию текущее время)
        fmt: Формат строки
        
    Returns:
        str: Отформатированное время с указанием МСК
    """
    if dt is None:
        dt = now_msk()
    else:
        dt = to_msk(dt)
    
    return f"{dt.strftime(fmt)} МСК"


def format_date_russian(dt: Optional[datetime] = None) -> str:
    """
    Форматирует дату на русском языке
    
    Args:
        dt: Дата для форматирования (по умолчанию сегодня)
        
    Returns:
        str: Дата вида "19 января"
    """
    if dt is None:
        dt = today_msk()
    else:
        dt = to_msk(dt)
    
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }
    
    day = dt.day
    month = months[dt.month]
    
    return f"{day} {month}"


# ========================================================================
# ФУНКЦИИ РАБОТЫ С РАСПИСАНИЕМ
# ========================================================================

def parse_time_string(time_str: str, base_date: Optional[datetime] = None, tz_name: str = "Europe/Moscow") -> datetime:
    """
    Парсит строку времени (HH:MM) и возвращает datetime в указанном часовом поясе
    
    Args:
        time_str: Время в формате "HH:MM"
        base_date: Базовая дата (по умолчанию сегодня)
        tz_name: Часовой пояс (по умолчанию МСК)
        
    Returns:
        datetime: Полный datetime в указанном часовом поясе
    """
    tz = get_timezone(tz_name)
    
    if base_date is None:
        base_date = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        if base_date.tzinfo is None:
            base_date = base_date.replace(tzinfo=tz)
        else:
            base_date = base_date.astimezone(tz)
    
    try:
        hour, minute = map(int, time_str.split(':'))
        return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except (ValueError, AttributeError) as e:
        logger.error(f"Ошибка парсинга времени '{time_str}': {e}")
        raise ValueError(f"Неверный формат времени: {time_str}")


def get_next_scheduled_time(schedule: list[str]) -> Optional[datetime]:
    """
    Возвращает следующее время из расписания
    
    Args:
        schedule: Список времён в формате ["HH:MM", ...]
        
    Returns:
        datetime: Следующее запланированное время или None
    """
    now = now_msk()
    today = today_msk()
    
    for time_str in schedule:
        scheduled_dt = parse_time_string(time_str, today)
        
        if scheduled_dt > now:
            return scheduled_dt
    
    # Если сегодня все времена прошли, берём первое время завтра
    if schedule:
        tomorrow = tomorrow_msk()
        return parse_time_string(schedule[0], tomorrow)
    
    return None


def is_time_passed(time_str: str, base_date: Optional[datetime] = None) -> bool:
    """
    Проверяет, прошло ли указанное время
    
    Args:
        time_str: Время в формате "HH:MM"
        base_date: Базовая дата для сравнения
        
    Returns:
        bool: True если время уже прошло
    """
    if base_date is None:
        base_date = today_msk()
    
    scheduled_time = parse_time_string(time_str, base_date)
    return now_msk() >= scheduled_time


def time_until(target_dt: datetime) -> timedelta:
    """
    Возвращает время до указанного момента
    
    Args:
        target_dt: Целевое время
        
    Returns:
        timedelta: Время до целевого момента
    """
    target_dt = to_msk(target_dt)
    return target_dt - now_msk()


def time_since(past_dt: datetime) -> timedelta:
    """
    Возвращает время с указанного момента
    
    Args:
        past_dt: Прошедшее время
        
    Returns:
        timedelta: Время с указанного момента
    """
    past_dt = to_msk(past_dt)
    return now_msk() - past_dt


# ========================================================================
# ФУНКЦИИ ДЛЯ UI
# ========================================================================

def get_timezone_offset(tz_name: str) -> str:
    """
    Возвращает текущее смещение часового пояса от UTC
    
    Args:
        tz_name: Имя часового пояса
        
    Returns:
        str: Смещение в формате "+HH:MM" или "-HH:MM"
    """
    try:
        tz = get_timezone(tz_name)
        now = datetime.now(tz)
        offset = now.strftime('%z')
        # Форматируем как +HH:MM
        if offset:
            return f"{offset[:3]}:{offset[3:]}"
        return "+00:00"
    except Exception:
        return "+03:00"  # МСК по умолчанию


def get_all_timezones_with_offset() -> List[tuple[str, str, str]]:
    """
    Возвращает список всех часовых поясов с их смещениями
    
    Returns:
        List[tuple]: [(tz_name, display_name, offset), ...]
    """
    result = []
    for tz_name, display_name in POPULAR_TIMEZONES:
        offset = get_timezone_offset(tz_name)
        result.append((tz_name, display_name, offset))
    return sorted(result, key=lambda x: x[2])  # Сортируем по смещению


def format_schedule_preview(schedule: List[str], user_tz: str = "Europe/Moscow") -> List[Dict[str, str]]:
    """
    Форматирует расписание для предпросмотра с учетом часового пояса
    
    Args:
        schedule: Список времён публикации
        user_tz: Часовой пояс пользователя
        
    Returns:
        List[Dict]: Список с информацией о каждом времени публикации
    """
    result = []
    today = datetime.now(get_timezone(user_tz)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    for i, time_str in enumerate(schedule, 1):
        # Парсим время в пользовательском часовом поясе
        user_time = parse_time_string(time_str, today, user_tz)
        # Конвертируем в МСК
        msk_time = user_time.astimezone(MSK)
        
        result.append({
            "priority": i,
            "user_time": user_time.strftime("%H:%M"),
            "msk_time": msk_time.strftime("%H:%M"),
            "user_tz": user_tz,
            "is_next_day": msk_time.date() > user_time.date()  # Если в МСК уже следующий день
        })
    
    return result


# ========================================================================
# ФУНКЦИИ ВАЛИДАЦИИ
# ========================================================================

def is_valid_time_string(time_str: str) -> bool:
    """
    Проверяет корректность строки времени
    
    Args:
        time_str: Строка времени для проверки
        
    Returns:
        bool: True если формат корректный (HH:MM)
    """
    try:
        parts = time_str.split(':')
        if len(parts) != 2:
            return False
        
        hour, minute = map(int, parts)
        return 0 <= hour <= 23 and 0 <= minute <= 59
    except (ValueError, AttributeError):
        return False


def is_working_hours(start: str = "09:00", end: str = "21:00") -> bool:
    """
    Проверяет, находимся ли мы в рабочих часах
    
    Args:
        start: Начало рабочего дня
        end: Конец рабочего дня
        
    Returns:
        bool: True если сейчас рабочее время
    """
    now = now_msk()
    today = today_msk()
    
    start_time = parse_time_string(start, today)
    end_time = parse_time_string(end, today)
    
    return start_time <= now <= end_time


# ========================================================================
# ФУНКЦИИ ДЛЯ ЛОГИРОВАНИЯ
# ========================================================================

def log_with_timestamp(message: str, level: str = "INFO") -> None:
    """
    Логирует сообщение с меткой времени в МСК
    
    Args:
        message: Сообщение для логирования
        level: Уровень логирования
    """
    timestamp = format_msk_time()
    full_message = f"[{timestamp}] {message}"
    
    if level == "DEBUG":
        logger.debug(full_message)
    elif level == "INFO":
        logger.info(full_message)
    elif level == "WARNING":
        logger.warning(full_message)
    elif level == "ERROR":
        logger.error(full_message)
    else:
        logger.info(full_message)


# ========================================================================
# ФУНКЦИИ ДЛЯ ФАЙЛОВ
# ========================================================================

def get_date_based_filename(pattern: str, dt: Optional[datetime] = None) -> str:
    """
    Генерирует имя файла на основе даты
    
    Args:
        pattern: Паттерн имени файла с {date} placeholder
        dt: Дата для имени файла (по умолчанию сегодня)
        
    Returns:
        str: Имя файла с подставленной датой
    """
    if dt is None:
        dt = today_msk()
    else:
        dt = to_msk(dt)
    
    date_str = dt.strftime('%Y-%m-%d')
    return pattern.format(date=date_str)


def parse_date_from_filename(filename: str, pattern: str) -> Optional[datetime]:
    """
    Извлекает дату из имени файла
    
    Args:
        filename: Имя файла
        pattern: Паттерн с {date} placeholder
        
    Returns:
        datetime: Извлеченная дата или None
    """
    import re
    
    # Преобразуем паттерн в регулярное выражение
    regex_pattern = pattern.replace('{date}', r'(\d{4}-\d{2}-\d{2})')
    
    match = re.match(regex_pattern, filename)
    if match:
        date_str = match.group(1)
        try:
            # Парсим дату и добавляем МСК timezone
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            return naive_to_msk(dt)
        except ValueError:
            logger.error(f"Не удалось распарсить дату из {date_str}")
    
    return None


# ========================================================================
# ИНИЦИАЛИЗАЦИЯ И ТЕСТЫ
# ========================================================================

def test_timezone_functions():
    """Тестирует функции работы с timezone"""
    logger.info("Тестирование функций timezone...")
    
    # Тест получения времени
    msk_now = now_msk()
    utc_now = now_utc()
    logger.info(f"Сейчас в МСК: {format_msk_time(msk_now)}")
    logger.info(f"Сейчас в UTC: {utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Тест преобразований
    naive_dt = datetime(2025, 1, 15, 12, 30, 0)
    msk_dt = naive_to_msk(naive_dt)
    utc_dt = to_utc(msk_dt)
    logger.info(f"Naive время: {naive_dt}")
    logger.info(f"В МСК: {msk_dt}")
    logger.info(f"В UTC: {utc_dt}")
    
    # Тест расписания
    next_time = get_next_scheduled_time(config.PUBLICATION_SCHEDULE)
    if next_time:
        delta = time_until(next_time)
        logger.info(f"Следующая публикация: {format_msk_time(next_time)}")
        logger.info(f"Через: {delta}")
    
    logger.info("✅ Тесты timezone пройдены")


if __name__ == "__main__":
    test_timezone_functions()