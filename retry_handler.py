"""
Модуль для обработки повторных попыток с exponential backoff

Обеспечивает устойчивость к временным сбоям API и сети.
"""

import time
import random
from typing import TypeVar, Callable, Optional, Any, Dict
from functools import wraps
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
import requests
from openai import RateLimitError, APIError, Timeout

# Типы для типизации
T = TypeVar('T')


# ========================================================================
# ДЕКОРАТОРЫ ДЛЯ RETRY ЛОГИКИ
# ========================================================================

def retry_with_exponential_backoff(
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 60.0,
    jitter: bool = True
):
    """
    Декоратор для повторных попыток с exponential backoff
    
    Args:
        max_attempts: Максимальное количество попыток
        initial_wait: Начальная задержка в секундах
        max_wait: Максимальная задержка в секундах
        jitter: Добавлять ли случайную задержку для предотвращения thundering herd
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            attempt = 0
            last_exception = None
            
            while attempt < max_attempts:
                try:
                    attempt += 1
                    logger.debug(f"Попытка {attempt}/{max_attempts} для {func.__name__}")
                    return func(*args, **kwargs)
                    
                except (requests.exceptions.Timeout, 
                       requests.exceptions.ConnectionError,
                       RateLimitError) as e:
                    last_exception = e
                    
                    if attempt >= max_attempts:
                        logger.error(f"Все {max_attempts} попыток исчерпаны для {func.__name__}")
                        raise
                    
                    # Вычисляем задержку с exponential backoff
                    wait_time = min(initial_wait * (2 ** (attempt - 1)), max_wait)
                    
                    # Добавляем jitter если нужно
                    if jitter:
                        wait_time += random.uniform(0, wait_time * 0.1)
                    
                    logger.warning(
                        f"Ошибка {type(e).__name__} в {func.__name__}, "
                        f"повтор через {wait_time:.1f} сек..."
                    )
                    time.sleep(wait_time)
                    
                except Exception as e:
                    logger.error(f"Неожиданная ошибка в {func.__name__}: {e}")
                    raise
            
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


def retry_api_call(
    exceptions=(requests.RequestException, APIError, Timeout),
    max_attempts: int = 3,
    wait_multiplier: float = 1.0
):
    """
    Специализированный декоратор для API вызовов с использованием tenacity
    
    Args:
        exceptions: Tuple исключений для перехвата
        max_attempts: Максимум попыток
        wait_multiplier: Множитель для задержки
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=wait_multiplier, min=1, max=30),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, "WARNING"),
        after=after_log(logger, "INFO")
    )


# ========================================================================
# ОБРАБОТЧИКИ RATE LIMITING
# ========================================================================

class RateLimiter:
    """Класс для контроля частоты запросов к API"""
    
    def __init__(self, calls_per_minute: int = 60):
        """
        Инициализация rate limiter
        
        Args:
            calls_per_minute: Максимум вызовов в минуту
        """
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute
        self.last_call_time = 0.0
        
    def wait_if_needed(self):
        """Ожидает если необходимо для соблюдения rate limit"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        
        if time_since_last_call < self.min_interval:
            wait_time = self.min_interval - time_since_last_call
            logger.debug(f"Rate limiting: ожидание {wait_time:.2f} сек")
            time.sleep(wait_time)
        
        self.last_call_time = time.time()
    
    def __enter__(self):
        """Вход в контекстный менеджер"""
        self.wait_if_needed()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекстного менеджера"""
        pass


# ========================================================================
# СПЕЦИАЛИЗИРОВАННЫЕ ОБРАБОТЧИКИ ДЛЯ РАЗНЫХ API
# ========================================================================

class PerplexityRetryHandler:
    """Обработчик повторных попыток для Perplexity API"""
    
    @staticmethod
    @retry_api_call(max_attempts=3, wait_multiplier=2)
    def make_request(url: str, headers: Dict, json_data: Dict, timeout: int) -> requests.Response:
        """
        Выполняет запрос к Perplexity API с обработкой ошибок
        
        Args:
            url: URL API endpoint
            headers: Заголовки запроса
            json_data: Тело запроса
            timeout: Таймаут запроса
            
        Returns:
            Response объект
        """
        response = requests.post(url, headers=headers, json=json_data, timeout=timeout)
        
        # Проверяем rate limiting
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            logger.warning(f"Rate limit достигнут, ожидание {retry_after} сек")
            time.sleep(retry_after)
            raise requests.exceptions.RequestException("Rate limit exceeded")
        
        response.raise_for_status()
        return response


class OpenAIRetryHandler:
    """Обработчик повторных попыток для OpenAI API"""
    
    @staticmethod
    def handle_openai_error(func: Callable[..., T]) -> Callable[..., T]:
        """
        Декоратор для обработки специфичных ошибок OpenAI
        
        Args:
            func: Функция для обертки
            
        Returns:
            Обернутая функция
        """
        @wraps(func)
        @retry_with_exponential_backoff(max_attempts=3, initial_wait=2.0)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except RateLimitError as e:
                logger.warning(f"OpenAI rate limit: {e}")
                # Извлекаем время ожидания из ошибки если есть
                wait_time = getattr(e, 'retry_after', 60)
                time.sleep(wait_time)
                raise
            except APIError as e:
                logger.error(f"OpenAI API error: {e}")
                raise
            except Timeout as e:
                logger.error(f"OpenAI timeout: {e}")
                raise
                
        return wrapper


class TelegramRetryHandler:
    """Обработчик повторных попыток для Telegram API"""
    
    @staticmethod
    @retry_api_call(
        exceptions=(requests.RequestException,),
        max_attempts=5,
        wait_multiplier=1.5
    )
    def send_with_retry(send_func: Callable, *args, **kwargs) -> bool:
        """
        Отправляет сообщение в Telegram с повторными попытками
        
        Args:
            send_func: Функция отправки
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            bool: Успешность отправки
        """
        return send_func(*args, **kwargs)


# ========================================================================
# УТИЛИТЫ ДЛЯ ОБРАБОТКИ ОШИБОК
# ========================================================================

def is_retryable_error(exception: Exception) -> bool:
    """
    Определяет, является ли ошибка временной и можно ли повторить
    
    Args:
        exception: Исключение для проверки
        
    Returns:
        bool: True если можно повторить попытку
    """
    retryable_types = (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.HTTPError,
        RateLimitError,
        Timeout
    )
    
    if isinstance(exception, retryable_types):
        return True
    
    # Проверяем HTTP статус коды
    if isinstance(exception, requests.exceptions.HTTPError):
        if hasattr(exception.response, 'status_code'):
            # 429 - Too Many Requests, 503 - Service Unavailable
            # 502 - Bad Gateway, 504 - Gateway Timeout
            retryable_codes = {429, 502, 503, 504}
            return exception.response.status_code in retryable_codes
    
    return False


def calculate_backoff_time(
    attempt: int,
    base_wait: float = 1.0,
    max_wait: float = 60.0,
    jitter: bool = True
) -> float:
    """
    Вычисляет время ожидания для exponential backoff
    
    Args:
        attempt: Номер попытки (начиная с 1)
        base_wait: Базовое время ожидания
        max_wait: Максимальное время ожидания
        jitter: Добавлять ли случайный компонент
        
    Returns:
        float: Время ожидания в секундах
    """
    wait_time = min(base_wait * (2 ** (attempt - 1)), max_wait)
    
    if jitter:
        # Добавляем до 10% случайной задержки
        wait_time += random.uniform(0, wait_time * 0.1)
    
    return wait_time


# ========================================================================
# КОНТЕКСТНЫЕ МЕНЕДЖЕРЫ
# ========================================================================

class RetryContext:
    """Контекстный менеджер для блока кода с повторными попытками"""
    
    def __init__(self, max_attempts: int = 3, wait_time: float = 1.0):
        self.max_attempts = max_attempts
        self.wait_time = wait_time
        self.attempt = 0
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and is_retryable_error(exc_val):
            self.attempt += 1
            if self.attempt < self.max_attempts:
                wait = calculate_backoff_time(self.attempt, self.wait_time)
                logger.warning(f"Попытка {self.attempt}/{self.max_attempts} неудачна, повтор через {wait:.1f} сек")
                time.sleep(wait)
                return False  # Не подавляем исключение, позволяем повторить
        return False


# ========================================================================
# ТЕСТИРОВАНИЕ
# ========================================================================

def test_retry_handlers():
    """Тестирует функционал обработки повторных попыток"""
    logger.info("🧪 Тестирование retry handlers...")
    
    # Тест exponential backoff
    @retry_with_exponential_backoff(max_attempts=3, initial_wait=0.1)
    def flaky_function(fail_times: int = 2):
        """Функция которая падает первые N раз"""
        if not hasattr(flaky_function, 'call_count'):
            flaky_function.call_count = 0
        flaky_function.call_count += 1
        
        if flaky_function.call_count <= fail_times:
            raise requests.exceptions.Timeout("Временная ошибка")
        return "Успех!"
    
    try:
        result = flaky_function(fail_times=2)
        logger.info(f"✅ Тест exponential backoff пройден: {result}")
    except Exception as e:
        logger.error(f"❌ Тест exponential backoff провален: {e}")
    
    # Тест rate limiter
    rate_limiter = RateLimiter(calls_per_minute=120)  # 2 вызова в секунду
    
    start_time = time.time()
    for i in range(3):
        with rate_limiter:
            logger.debug(f"Вызов {i+1}")
    elapsed = time.time() - start_time
    
    if elapsed >= 1.0:  # Должно занять минимум 1 секунду для 3 вызовов при лимите 2/сек
        logger.info(f"✅ Тест rate limiter пройден: {elapsed:.2f} сек")
    else:
        logger.error(f"❌ Тест rate limiter провален: слишком быстро ({elapsed:.2f} сек)")
    
    logger.info("✅ Тесты retry handlers завершены")


if __name__ == "__main__":
    test_retry_handlers()