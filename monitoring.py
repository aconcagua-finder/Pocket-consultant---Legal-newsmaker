"""
Модуль мониторинга и метрик для NEWSMAKER

Обеспечивает отслеживание производительности, сбор метрик и алертинг.
"""

import time
import json
import psutil
import platform
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
from functools import wraps
from loguru import logger

import config
from file_utils import safe_json_write, safe_json_read, ensure_directory


# ========================================================================
# КОНФИГУРАЦИЯ МОНИТОРИНГА
# ========================================================================

METRICS_DIR = Path("metrics")
ensure_directory(METRICS_DIR)

# Файлы для хранения метрик
PERFORMANCE_METRICS_FILE = METRICS_DIR / "performance.json"
API_METRICS_FILE = METRICS_DIR / "api_calls.json"
ERROR_METRICS_FILE = METRICS_DIR / "errors.json"
DAILY_STATS_FILE = METRICS_DIR / "daily_stats.json"

# Лимиты для алертов
ALERT_THRESHOLDS = {
    'cpu_percent': 80.0,
    'memory_percent': 85.0,
    'disk_percent': 90.0,
    'api_error_rate': 0.3,  # 30% ошибок
    'response_time_ms': 5000,  # 5 секунд
}


# ========================================================================
# СТРУКТУРЫ ДАННЫХ
# ========================================================================

@dataclass
class PerformanceMetric:
    """Метрика производительности"""
    timestamp: str
    operation: str
    duration_ms: float
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class APICallMetric:
    """Метрика API вызова"""
    timestamp: str
    api_name: str
    endpoint: str
    method: str
    status_code: Optional[int]
    response_time_ms: float
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SystemMetric:
    """Метрика состояния системы"""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_percent: float
    disk_free_gb: float
    process_count: int
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DailyStats:
    """Ежедневная статистика"""
    date: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    total_api_calls: int
    successful_api_calls: int
    failed_api_calls: int
    news_collected: int
    news_published: int
    images_generated: int
    avg_response_time_ms: float
    total_errors: int
    uptime_hours: float
    
    def to_dict(self) -> Dict:
        return asdict(self)


# ========================================================================
# КОЛЛЕКТОРЫ МЕТРИК
# ========================================================================

class MetricsCollector:
    """Основной коллектор метрик"""
    
    def __init__(self):
        self.performance_buffer = deque(maxlen=1000)
        self.api_buffer = deque(maxlen=1000)
        self.error_buffer = deque(maxlen=500)
        self.system_metrics_buffer = deque(maxlen=100)
        
        # Счетчики для быстрого доступа
        self.counters = defaultdict(int)
        self.timers = defaultdict(list)
        
        # Время запуска для расчета uptime
        self.start_time = time.time()
    
    def record_performance(
        self,
        operation: str,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None
    ):
        """
        Записывает метрику производительности
        
        Args:
            operation: Название операции
            duration_ms: Длительность в миллисекундах
            success: Успешность операции
            error: Описание ошибки если есть
        """
        metric = PerformanceMetric(
            timestamp=datetime.now().isoformat(),
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            error=error
        )
        
        self.performance_buffer.append(metric)
        
        # Обновляем счетчики
        self.counters[f"{operation}_total"] += 1
        if success:
            self.counters[f"{operation}_success"] += 1
        else:
            self.counters[f"{operation}_failed"] += 1
        
        # Записываем время выполнения
        self.timers[operation].append(duration_ms)
        
        # Логируем если операция медленная
        if duration_ms > ALERT_THRESHOLDS['response_time_ms']:
            logger.warning(f"Медленная операция {operation}: {duration_ms:.0f}ms")
    
    def record_api_call(
        self,
        api_name: str,
        endpoint: str,
        method: str,
        status_code: Optional[int],
        response_time_ms: float,
        success: bool,
        error: Optional[str] = None
    ):
        """
        Записывает метрику API вызова
        
        Args:
            api_name: Название API (Perplexity, OpenAI, Telegram)
            endpoint: URL endpoint
            method: HTTP метод
            status_code: Код ответа
            response_time_ms: Время ответа в мс
            success: Успешность вызова
            error: Описание ошибки
        """
        metric = APICallMetric(
            timestamp=datetime.now().isoformat(),
            api_name=api_name,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            success=success,
            error=error
        )
        
        self.api_buffer.append(metric)
        
        # Обновляем счетчики
        self.counters[f"api_{api_name}_total"] += 1
        if success:
            self.counters[f"api_{api_name}_success"] += 1
        else:
            self.counters[f"api_{api_name}_failed"] += 1
        
        # Проверяем error rate
        self._check_api_error_rate(api_name)
    
    def record_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[Dict] = None
    ):
        """
        Записывает ошибку
        
        Args:
            error_type: Тип ошибки
            error_message: Сообщение об ошибке
            context: Дополнительный контекст
        """
        error_data = {
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': error_message,
            'context': context or {}
        }
        
        self.error_buffer.append(error_data)
        self.counters[f"error_{error_type}"] += 1
        
        # Алерт если слишком много ошибок
        if len(self.error_buffer) > 100:
            recent_errors = list(self.error_buffer)[-100:]
            error_rate = sum(1 for e in recent_errors 
                           if datetime.fromisoformat(e['timestamp']) > 
                           datetime.now() - timedelta(minutes=10))
            
            if error_rate > 20:  # Более 20 ошибок за 10 минут
                logger.critical(f"Высокий уровень ошибок: {error_rate} за последние 10 минут")
    
    def collect_system_metrics(self) -> SystemMetric:
        """
        Собирает метрики системы
        
        Returns:
            SystemMetric с текущими показателями
        """
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Память
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_mb = memory.used / (1024 * 1024)
        
        # Диск
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_free_gb = disk.free / (1024 * 1024 * 1024)
        
        # Процессы
        process_count = len(psutil.pids())
        
        metric = SystemMetric(
            timestamp=datetime.now().isoformat(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_mb=memory_mb,
            disk_percent=disk_percent,
            disk_free_gb=disk_free_gb,
            process_count=process_count
        )
        
        self.system_metrics_buffer.append(metric)
        
        # Проверяем пороги для алертов
        self._check_system_alerts(metric)
        
        return metric
    
    def _check_api_error_rate(self, api_name: str):
        """Проверяет error rate для API"""
        total = self.counters[f"api_{api_name}_total"]
        failed = self.counters[f"api_{api_name}_failed"]
        
        if total > 10:  # Минимум 10 вызовов для расчета
            error_rate = failed / total
            if error_rate > ALERT_THRESHOLDS['api_error_rate']:
                logger.critical(
                    f"Высокий error rate для {api_name}: "
                    f"{error_rate:.1%} ({failed}/{total})"
                )
    
    def _check_system_alerts(self, metric: SystemMetric):
        """Проверяет системные метрики на превышение порогов"""
        alerts = []
        
        if metric.cpu_percent > ALERT_THRESHOLDS['cpu_percent']:
            alerts.append(f"CPU: {metric.cpu_percent:.1f}%")
        
        if metric.memory_percent > ALERT_THRESHOLDS['memory_percent']:
            alerts.append(f"Memory: {metric.memory_percent:.1f}%")
        
        if metric.disk_percent > ALERT_THRESHOLDS['disk_percent']:
            alerts.append(f"Disk: {metric.disk_percent:.1f}%")
        
        if alerts:
            logger.warning(f"⚠️ Системные алерты: {', '.join(alerts)}")
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Получает сводку метрик
        
        Returns:
            Dict со сводкой
        """
        uptime_seconds = time.time() - self.start_time
        uptime_hours = uptime_seconds / 3600
        
        # Считаем средние времена
        avg_times = {}
        for operation, times in self.timers.items():
            if times:
                avg_times[operation] = sum(times) / len(times)
        
        return {
            'uptime_hours': round(uptime_hours, 2),
            'counters': dict(self.counters),
            'average_times_ms': avg_times,
            'buffer_sizes': {
                'performance': len(self.performance_buffer),
                'api': len(self.api_buffer),
                'errors': len(self.error_buffer),
                'system': len(self.system_metrics_buffer)
            }
        }
    
    def save_metrics(self):
        """Сохраняет метрики в файлы"""
        try:
            # Сохраняем производительность
            if self.performance_buffer:
                perf_data = [m.to_dict() for m in self.performance_buffer]
                safe_json_write(PERFORMANCE_METRICS_FILE, perf_data)
            
            # Сохраняем API метрики
            if self.api_buffer:
                api_data = [m.to_dict() for m in self.api_buffer]
                safe_json_write(API_METRICS_FILE, api_data)
            
            # Сохраняем ошибки
            if self.error_buffer:
                error_data = list(self.error_buffer)
                safe_json_write(ERROR_METRICS_FILE, error_data)
            
            logger.debug("Метрики сохранены")
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении метрик: {e}")
    
    def generate_daily_stats(self) -> DailyStats:
        """
        Генерирует ежедневную статистику
        
        Returns:
            DailyStats объект
        """
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Считаем операции
        total_ops = sum(1 for _ in self.performance_buffer)
        successful_ops = sum(1 for m in self.performance_buffer if m.success)
        failed_ops = total_ops - successful_ops
        
        # Считаем API вызовы
        total_api = sum(1 for _ in self.api_buffer)
        successful_api = sum(1 for m in self.api_buffer if m.success)
        failed_api = total_api - successful_api
        
        # Считаем среднее время ответа
        response_times = [m.response_time_ms for m in self.api_buffer]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Специфичные счетчики
        news_collected = self.counters.get('news_collection_success', 0)
        news_published = self.counters.get('news_publication_success', 0)
        images_generated = self.counters.get('image_generation_success', 0)
        
        # Uptime
        uptime_hours = (time.time() - self.start_time) / 3600
        
        stats = DailyStats(
            date=today,
            total_operations=total_ops,
            successful_operations=successful_ops,
            failed_operations=failed_ops,
            total_api_calls=total_api,
            successful_api_calls=successful_api,
            failed_api_calls=failed_api,
            news_collected=news_collected,
            news_published=news_published,
            images_generated=images_generated,
            avg_response_time_ms=round(avg_response_time, 2),
            total_errors=len(self.error_buffer),
            uptime_hours=round(uptime_hours, 2)
        )
        
        # Сохраняем статистику
        safe_json_write(DAILY_STATS_FILE, stats.to_dict())
        
        return stats


# Глобальный экземпляр коллектора
metrics_collector = MetricsCollector()


# ========================================================================
# ДЕКОРАТОРЫ ДЛЯ МОНИТОРИНГА
# ========================================================================

def monitor_performance(operation_name: Optional[str] = None):
    """
    Декоратор для мониторинга производительности функции
    
    Args:
        operation_name: Название операции (по умолчанию имя функции)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            start_time = time.perf_counter()
            error = None
            result = None
            
            try:
                result = func(*args, **kwargs)
                success = True
            except Exception as e:
                error = str(e)
                success = False
                raise
            finally:
                duration_ms = (time.perf_counter() - start_time) * 1000
                metrics_collector.record_performance(
                    operation=op_name,
                    duration_ms=duration_ms,
                    success=success,
                    error=error
                )
            
            return result
        
        return wrapper
    return decorator


def monitor_api_call(api_name: str):
    """
    Декоратор для мониторинга API вызовов
    
    Args:
        api_name: Название API
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            status_code = None
            error = None
            
            try:
                result = func(*args, **kwargs)
                
                # Пытаемся извлечь status code из результата
                if isinstance(result, dict):
                    status_code = result.get('status_code', 200)
                elif hasattr(result, 'status_code'):
                    status_code = result.status_code
                else:
                    status_code = 200
                
                success = status_code < 400
                
            except Exception as e:
                error = str(e)
                success = False
                status_code = 500
                raise
                
            finally:
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                # Извлекаем endpoint из аргументов если возможно
                endpoint = "unknown"
                if args and isinstance(args[0], str):
                    endpoint = args[0]
                elif 'url' in kwargs:
                    endpoint = kwargs['url']
                
                metrics_collector.record_api_call(
                    api_name=api_name,
                    endpoint=endpoint,
                    method=kwargs.get('method', 'GET'),
                    status_code=status_code,
                    response_time_ms=duration_ms,
                    success=success,
                    error=error
                )
            
            return result
        
        return wrapper
    return decorator


# ========================================================================
# HEALTH CHECK
# ========================================================================

class HealthChecker:
    """Класс для проверки здоровья системы"""
    
    @staticmethod
    def check_system_health() -> Dict[str, Any]:
        """
        Проверяет здоровье системы
        
        Returns:
            Dict с результатами проверки
        """
        health = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'checks': {}
        }
        
        # Проверяем систему
        system_metric = metrics_collector.collect_system_metrics()
        
        health['checks']['system'] = {
            'cpu_percent': system_metric.cpu_percent,
            'memory_percent': system_metric.memory_percent,
            'disk_percent': system_metric.disk_percent,
            'status': 'ok' if all([
                system_metric.cpu_percent < ALERT_THRESHOLDS['cpu_percent'],
                system_metric.memory_percent < ALERT_THRESHOLDS['memory_percent'],
                system_metric.disk_percent < ALERT_THRESHOLDS['disk_percent']
            ]) else 'warning'
        }
        
        # Проверяем API
        api_health = {}
        for api in ['Perplexity', 'OpenAI', 'Telegram']:
            total = metrics_collector.counters.get(f"api_{api}_total", 0)
            failed = metrics_collector.counters.get(f"api_{api}_failed", 0)
            
            if total > 0:
                error_rate = failed / total
                api_health[api] = {
                    'total_calls': total,
                    'failed_calls': failed,
                    'error_rate': round(error_rate, 3),
                    'status': 'ok' if error_rate < ALERT_THRESHOLDS['api_error_rate'] else 'warning'
                }
        
        health['checks']['apis'] = api_health
        
        # Общий статус
        if any(check.get('status') == 'warning' 
              for check in health['checks'].values()):
            health['status'] = 'degraded'
        
        return health
    
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """
        Получает информацию о системе
        
        Returns:
            Dict с информацией
        """
        return {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'total_memory_gb': round(psutil.virtual_memory().total / (1024**3), 2),
            'total_disk_gb': round(psutil.disk_usage('/').total / (1024**3), 2),
            'hostname': platform.node()
        }


# ========================================================================
# ТЕСТИРОВАНИЕ
# ========================================================================

def test_monitoring():
    """Тестирует функциональность мониторинга"""
    logger.info("🧪 Тестирование системы мониторинга...")
    
    # Тест записи метрик
    @monitor_performance()
    def test_function(x: int) -> int:
        time.sleep(0.1)
        return x * 2
    
    result = test_function(5)
    assert result == 10
    
    # Проверяем что метрика записана
    assert metrics_collector.counters['test_function_total'] == 1
    assert metrics_collector.counters['test_function_success'] == 1
    logger.info("✅ Мониторинг производительности работает")
    
    # Тест API мониторинга
    metrics_collector.record_api_call(
        api_name="TestAPI",
        endpoint="/test",
        method="GET",
        status_code=200,
        response_time_ms=100,
        success=True
    )
    
    assert metrics_collector.counters['api_TestAPI_total'] == 1
    assert metrics_collector.counters['api_TestAPI_success'] == 1
    logger.info("✅ Мониторинг API работает")
    
    # Тест системных метрик
    system_metric = metrics_collector.collect_system_metrics()
    assert system_metric.cpu_percent >= 0
    assert system_metric.memory_percent >= 0
    logger.info("✅ Системные метрики работают")
    
    # Тест health check
    health = HealthChecker.check_system_health()
    assert health['status'] in ['healthy', 'degraded']
    logger.info(f"✅ Health check: {health['status']}")
    
    # Тест сохранения метрик
    metrics_collector.save_metrics()
    assert PERFORMANCE_METRICS_FILE.exists() or len(metrics_collector.performance_buffer) == 0
    logger.info("✅ Сохранение метрик работает")
    
    # Генерируем дневную статистику
    stats = metrics_collector.generate_daily_stats()
    logger.info(f"📊 Дневная статистика: {stats.total_operations} операций")
    
    logger.info("✅ Все тесты мониторинга пройдены")


if __name__ == "__main__":
    test_monitoring()