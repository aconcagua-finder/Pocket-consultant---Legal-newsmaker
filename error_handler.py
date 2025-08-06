"""
Централизованный модуль обработки ошибок для NEWSMAKER

Обеспечивает единообразную обработку исключений и логирование.
"""

import sys
import traceback
from typing import Any, Callable, Optional, Type, Union
from functools import wraps
from loguru import logger
from datetime import datetime

import config
from timezone_utils import now_msk, format_msk_time


# ========================================================================
# CUSTOM EXCEPTIONS - Специализированные исключения
# ========================================================================

class NewsmakerException(Exception):
    """Базовое исключение для всех ошибок NEWSMAKER"""
    pass


class APIException(NewsmakerException):
    """Ошибки при работе с внешними API"""
    pass


class PerplexityAPIException(APIException):
    """Ошибки Perplexity API"""
    pass


class OpenAIAPIException(APIException):
    """Ошибки OpenAI API"""
    pass


class TelegramAPIException(APIException):
    """Ошибки Telegram API"""
    pass


class ConfigurationException(NewsmakerException):
    """Ошибки конфигурации"""
    pass


class FileOperationException(NewsmakerException):
    """Ошибки работы с файлами"""
    pass


class ValidationException(NewsmakerException):
    """Ошибки валидации данных"""
    pass


class ContentGenerationException(NewsmakerException):
    """Ошибки генерации контента"""
    pass


class SchedulingException(NewsmakerException):
    """Ошибки планировщика"""
    pass


# ========================================================================
# ERROR HANDLERS - Обработчики ошибок
# ========================================================================

def handle_exception(
    exception: Exception,
    context: Optional[str] = None,
    critical: bool = False,
    user_message: Optional[str] = None
) -> None:
    """
    Централизованная обработка исключений
    
    Args:
        exception: Исключение для обработки
        context: Контекст возникновения ошибки
        critical: Является ли ошибка критической
        user_message: Сообщение для пользователя
    """
    # Формируем детальное сообщение об ошибке
    error_type = type(exception).__name__
    error_message = str(exception)
    
    # Базовое логирование
    log_message = f"[{error_type}]"
    if context:
        log_message += f" в {context}"
    log_message += f": {error_message}"
    
    # Логируем с соответствующим уровнем
    if critical:
        logger.critical(log_message)
        logger.critical(f"Traceback:\n{traceback.format_exc()}")
    else:
        logger.error(log_message)
        if config.DEBUG_MODE:
            logger.debug(f"Traceback:\n{traceback.format_exc()}")
    
    # Выводим пользователю если есть сообщение
    if user_message:
        logger.info(f"💬 {user_message}")
    
    # Записываем в файл ошибок если критическая
    if critical:
        save_error_to_file(exception, context)
    
    # Отправляем уведомление если настроено
    if critical and hasattr(config, 'SEND_ERROR_NOTIFICATIONS') and config.SEND_ERROR_NOTIFICATIONS:
        send_error_notification(exception, context)


def save_error_to_file(exception: Exception, context: Optional[str] = None) -> None:
    """
    Сохраняет информацию об ошибке в файл
    
    Args:
        exception: Исключение
        context: Контекст ошибки
    """
    try:
        from pathlib import Path
        error_dir = Path(config.LOGS_DIR) / "errors"
        error_dir.mkdir(exist_ok=True)
        
        timestamp = now_msk().strftime('%Y%m%d_%H%M%S')
        error_file = error_dir / f"error_{timestamp}.txt"
        
        with open(error_file, 'w', encoding='utf-8') as f:
            f.write(f"Error Report - {format_msk_time()}\n")
            f.write("=" * 60 + "\n\n")
            
            if context:
                f.write(f"Context: {context}\n")
            
            f.write(f"Exception Type: {type(exception).__name__}\n")
            f.write(f"Exception Message: {str(exception)}\n\n")
            
            f.write("Traceback:\n")
            f.write(traceback.format_exc())
            f.write("\n" + "=" * 60 + "\n")
            
        logger.debug(f"Ошибка сохранена в {error_file}")
        
    except Exception as e:
        logger.error(f"Не удалось сохранить ошибку в файл: {e}")


def send_error_notification(exception: Exception, context: Optional[str] = None) -> None:
    """
    Отправляет уведомление об ошибке
    
    Args:
        exception: Исключение
        context: Контекст ошибки
    """
    # TODO: Реализовать отправку уведомлений через Telegram или Email
    pass


# ========================================================================
# DECORATORS - Декораторы для обработки ошибок
# ========================================================================

def safe_execution(
    default_return: Any = None,
    exceptions: tuple = (Exception,),
    context: Optional[str] = None,
    critical: bool = False
):
    """
    Декоратор для безопасного выполнения функций
    
    Args:
        default_return: Значение по умолчанию при ошибке
        exceptions: Tuple исключений для перехвата
        context: Контекст выполнения
        critical: Критичность ошибок
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                handle_exception(
                    e,
                    context=context or func.__name__,
                    critical=critical
                )
                return default_return
        return wrapper
    return decorator


def retry_on_error(
    max_attempts: int = 3,
    exceptions: tuple = (Exception,),
    delay: float = 1.0,
    backoff: float = 2.0
):
    """
    Декоратор для повторных попыток при ошибках
    
    Args:
        max_attempts: Максимум попыток
        exceptions: Исключения для повтора
        delay: Начальная задержка
        backoff: Множитель задержки
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    
                    if attempt >= max_attempts:
                        logger.error(f"Все {max_attempts} попыток исчерпаны для {func.__name__}")
                        raise
                    
                    logger.warning(
                        f"Попытка {attempt}/{max_attempts} неудачна для {func.__name__}, "
                        f"повтор через {current_delay:.1f} сек"
                    )
                    
                    import time
                    time.sleep(current_delay)
                    current_delay *= backoff
                    
        return wrapper
    return decorator


def validate_input(**validators):
    """
    Декоратор для валидации входных параметров
    
    Args:
        **validators: Словарь валидаторов для параметров
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Получаем имена параметров функции
            import inspect
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            
            # Валидируем каждый параметр
            for param_name, validator in validators.items():
                if param_name in bound.arguments:
                    value = bound.arguments[param_name]
                    
                    if not validator(value):
                        raise ValidationException(
                            f"Параметр '{param_name}' не прошел валидацию в {func.__name__}"
                        )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ========================================================================
# CONTEXT MANAGERS - Контекстные менеджеры
# ========================================================================

class ErrorContext:
    """Контекстный менеджер для обработки ошибок в блоке кода"""
    
    def __init__(
        self,
        context: str,
        suppress: bool = False,
        default_return: Any = None,
        critical: bool = False
    ):
        """
        Инициализация контекста обработки ошибок
        
        Args:
            context: Описание контекста
            suppress: Подавлять ли исключения
            default_return: Значение при ошибке
            critical: Критичность ошибок
        """
        self.context = context
        self.suppress = suppress
        self.default_return = default_return
        self.critical = critical
        self.exception = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.exception = exc_val
            handle_exception(
                exc_val,
                context=self.context,
                critical=self.critical
            )
            
            if self.suppress:
                return True  # Подавляем исключение
        
        return False


# ========================================================================
# ERROR RECOVERY - Восстановление после ошибок
# ========================================================================

def attempt_recovery(
    error_type: Type[Exception],
    recovery_action: Callable,
    max_attempts: int = 1
) -> bool:
    """
    Пытается восстановиться после ошибки
    
    Args:
        error_type: Тип ошибки
        recovery_action: Действие для восстановления
        max_attempts: Максимум попыток
        
    Returns:
        bool: Успешность восстановления
    """
    for attempt in range(max_attempts):
        try:
            recovery_action()
            logger.info(f"✅ Успешное восстановление после {error_type.__name__}")
            return True
        except Exception as e:
            logger.warning(f"Попытка восстановления {attempt+1}/{max_attempts} неудачна: {e}")
    
    return False


# ========================================================================
# ERROR REPORTING - Отчеты об ошибках
# ========================================================================

def generate_error_report() -> dict:
    """
    Генерирует отчет об ошибках за текущую сессию
    
    Returns:
        dict: Статистика ошибок
    """
    from pathlib import Path
    
    report = {
        'timestamp': format_msk_time(),
        'total_errors': 0,
        'critical_errors': 0,
        'errors_by_type': {},
        'recent_errors': []
    }
    
    # Анализируем логи
    log_file = Path(config.LOGS_DIR) / "newsmaker.log"
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if 'ERROR' in line or 'CRITICAL' in line:
                    report['total_errors'] += 1
                    
                    if 'CRITICAL' in line:
                        report['critical_errors'] += 1
    
    return report


# ========================================================================
# TESTING - Тестирование
# ========================================================================

def test_error_handlers():
    """Тестирует обработчики ошибок"""
    logger.info("🧪 Тестирование обработчиков ошибок...")
    
    # Тест safe_execution
    @safe_execution(default_return="default", context="test_function")
    def failing_function():
        raise ValueError("Test error")
    
    result = failing_function()
    assert result == "default", "safe_execution не работает"
    logger.info("✅ safe_execution работает")
    
    # Тест retry_on_error
    counter = {'attempts': 0}
    
    @retry_on_error(max_attempts=3, delay=0.1)
    def flaky_function():
        counter['attempts'] += 1
        if counter['attempts'] < 3:
            raise ConnectionError("Test connection error")
        return "success"
    
    result = flaky_function()
    assert result == "success", "retry_on_error не работает"
    assert counter['attempts'] == 3, "Неверное количество попыток"
    logger.info("✅ retry_on_error работает")
    
    # Тест ErrorContext
    with ErrorContext("test_context", suppress=True) as ctx:
        raise RuntimeError("Test runtime error")
    
    assert ctx.exception is not None, "ErrorContext не перехватил исключение"
    logger.info("✅ ErrorContext работает")
    
    logger.info("✅ Все тесты обработчиков ошибок пройдены")


if __name__ == "__main__":
    test_error_handlers()