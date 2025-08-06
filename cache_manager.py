"""
Менеджер кеширования для NEWSMAKER

Обеспечивает кеширование дорогих операций для повышения производительности
и снижения нагрузки на API.
"""

import json
import hashlib
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional, Callable, Dict, Union
from functools import wraps
from loguru import logger
from cachetools import TTLCache, LRUCache

import config
from file_utils import safe_json_read, safe_json_write, ensure_directory


# ========================================================================
# КОНФИГУРАЦИЯ КЕШИРОВАНИЯ
# ========================================================================

# Директория для файлового кеша
CACHE_DIR = Path("cache")
ensure_directory(CACHE_DIR)

# Время жизни кеша по умолчанию (в секундах)
DEFAULT_TTL = 3600  # 1 час
NEWS_CACHE_TTL = 86400  # 24 часа для новостей
IMAGE_CACHE_TTL = 604800  # 7 дней для изображений
API_CACHE_TTL = 300  # 5 минут для API ответов


# ========================================================================
# IN-MEMORY КЕШИ
# ========================================================================

class MemoryCache:
    """Менеджер in-memory кешей"""
    
    def __init__(self):
        # TTL кеш для API ответов (максимум 100 элементов, TTL 5 минут)
        self.api_cache = TTLCache(maxsize=100, ttl=API_CACHE_TTL)
        
        # LRU кеш для обработанных данных (максимум 500 элементов)
        self.processed_cache = LRUCache(maxsize=500)
        
        # Кеш для промптов (максимум 50 элементов)
        self.prompt_cache = LRUCache(maxsize=50)
        
    def get(self, cache_name: str, key: str) -> Optional[Any]:
        """
        Получает значение из указанного кеша
        
        Args:
            cache_name: Имя кеша ('api', 'processed', 'prompt')
            key: Ключ для поиска
            
        Returns:
            Закешированное значение или None
        """
        cache = getattr(self, f"{cache_name}_cache", None)
        if cache is None:
            return None
        
        try:
            return cache.get(key)
        except KeyError:
            return None
    
    def set(self, cache_name: str, key: str, value: Any) -> bool:
        """
        Сохраняет значение в указанный кеш
        
        Args:
            cache_name: Имя кеша
            key: Ключ
            value: Значение
            
        Returns:
            bool: Успешность операции
        """
        cache = getattr(self, f"{cache_name}_cache", None)
        if cache is None:
            return False
        
        try:
            cache[key] = value
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении в кеш {cache_name}: {e}")
            return False
    
    def clear(self, cache_name: Optional[str] = None):
        """
        Очищает указанный кеш или все кеши
        
        Args:
            cache_name: Имя кеша для очистки (None = все кеши)
        """
        if cache_name:
            cache = getattr(self, f"{cache_name}_cache", None)
            if cache:
                cache.clear()
                logger.info(f"Кеш {cache_name} очищен")
        else:
            self.api_cache.clear()
            self.processed_cache.clear()
            self.prompt_cache.clear()
            logger.info("Все in-memory кеши очищены")


# Глобальный экземпляр memory cache
memory_cache = MemoryCache()


# ========================================================================
# ФАЙЛОВЫЙ КЕШ
# ========================================================================

class FileCache:
    """Менеджер файлового кеша для долгосрочного хранения"""
    
    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        ensure_directory(self.cache_dir)
        
        # Создаем поддиректории для разных типов кеша
        self.news_cache_dir = self.cache_dir / "news"
        self.image_cache_dir = self.cache_dir / "images"
        self.api_cache_dir = self.cache_dir / "api"
        
        ensure_directory(self.news_cache_dir)
        ensure_directory(self.image_cache_dir)
        ensure_directory(self.api_cache_dir)
    
    def _get_cache_key(self, key: str) -> str:
        """
        Генерирует безопасный ключ для имени файла
        
        Args:
            key: Исходный ключ
            
        Returns:
            str: Хеш ключа
        """
        return hashlib.md5(key.encode()).hexdigest()
    
    def _get_cache_path(self, cache_type: str, key: str) -> Path:
        """
        Получает путь к файлу кеша
        
        Args:
            cache_type: Тип кеша ('news', 'image', 'api')
            key: Ключ
            
        Returns:
            Path: Путь к файлу кеша
        """
        cache_key = self._get_cache_key(key)
        cache_subdir = getattr(self, f"{cache_type}_cache_dir", self.cache_dir)
        return cache_subdir / f"{cache_key}.cache"
    
    def get(self, cache_type: str, key: str, max_age: Optional[int] = None) -> Optional[Any]:
        """
        Получает значение из файлового кеша
        
        Args:
            cache_type: Тип кеша
            key: Ключ
            max_age: Максимальный возраст в секундах (None = без проверки)
            
        Returns:
            Закешированное значение или None
        """
        cache_path = self._get_cache_path(cache_type, key)
        
        if not cache_path.exists():
            return None
        
        # Проверяем возраст файла
        if max_age:
            file_age = datetime.now().timestamp() - cache_path.stat().st_mtime
            if file_age > max_age:
                logger.debug(f"Кеш устарел для {key} (возраст: {file_age:.0f} сек)")
                cache_path.unlink()  # Удаляем устаревший кеш
                return None
        
        try:
            # Пробуем загрузить как JSON
            if cache_path.suffix == '.json' or cache_type == 'api':
                return safe_json_read(cache_path)
            else:
                # Иначе используем pickle
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            logger.error(f"Ошибка чтения кеша {cache_path}: {e}")
            return None
    
    def set(self, cache_type: str, key: str, value: Any) -> bool:
        """
        Сохраняет значение в файловый кеш
        
        Args:
            cache_type: Тип кеша
            key: Ключ
            value: Значение
            
        Returns:
            bool: Успешность операции
        """
        cache_path = self._get_cache_path(cache_type, key)
        
        try:
            # Сохраняем как JSON если возможно
            if isinstance(value, (dict, list, str, int, float, bool, type(None))):
                cache_path = cache_path.with_suffix('.json')
                return safe_json_write(cache_path, value)
            else:
                # Иначе используем pickle
                with open(cache_path, 'wb') as f:
                    pickle.dump(value, f)
                return True
        except Exception as e:
            logger.error(f"Ошибка записи кеша {cache_path}: {e}")
            return False
    
    def delete(self, cache_type: str, key: str) -> bool:
        """
        Удаляет значение из кеша
        
        Args:
            cache_type: Тип кеша
            key: Ключ
            
        Returns:
            bool: Успешность операции
        """
        cache_path = self._get_cache_path(cache_type, key)
        
        if cache_path.exists():
            try:
                cache_path.unlink()
                return True
            except Exception as e:
                logger.error(f"Ошибка удаления кеша {cache_path}: {e}")
                return False
        
        # Проверяем JSON версию
        json_path = cache_path.with_suffix('.json')
        if json_path.exists():
            try:
                json_path.unlink()
                return True
            except Exception as e:
                logger.error(f"Ошибка удаления кеша {json_path}: {e}")
                return False
        
        return False
    
    def clear_old_cache(self, max_age_days: int = 7):
        """
        Удаляет старые файлы кеша
        
        Args:
            max_age_days: Максимальный возраст файлов в днях
        """
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        
        for cache_file in self.cache_dir.rglob("*.cache"):
            try:
                if datetime.fromtimestamp(cache_file.stat().st_mtime) < cutoff_time:
                    cache_file.unlink()
                    logger.debug(f"Удален старый кеш: {cache_file.name}")
            except Exception as e:
                logger.error(f"Ошибка при удалении старого кеша {cache_file}: {e}")
    
    def get_cache_size(self) -> Dict[str, int]:
        """
        Получает размер кеша по типам
        
        Returns:
            Dict с размерами в байтах
        """
        sizes = {}
        for cache_type in ['news', 'image', 'api']:
            cache_dir = getattr(self, f"{cache_type}_cache_dir")
            total_size = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
            sizes[cache_type] = total_size
        
        sizes['total'] = sum(sizes.values())
        return sizes


# Глобальный экземпляр файлового кеша
file_cache = FileCache()


# ========================================================================
# ДЕКОРАТОРЫ ДЛЯ КЕШИРОВАНИЯ
# ========================================================================

def cache_result(
    cache_type: str = 'processed',
    ttl: Optional[int] = None,
    key_func: Optional[Callable] = None,
    use_file_cache: bool = False
):
    """
    Декоратор для кеширования результатов функции
    
    Args:
        cache_type: Тип кеша ('api', 'processed', 'prompt')
        ttl: Время жизни в секундах (None = без ограничения)
        key_func: Функция для генерации ключа кеша
        use_file_cache: Использовать ли файловый кеш
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Генерируем ключ кеша
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Дефолтный ключ на основе имени функции и аргументов
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)
            
            # Проверяем memory cache
            cached_value = memory_cache.get(cache_type, cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit (memory) для {func.__name__}: {cache_key[:50]}")
                return cached_value
            
            # Проверяем файловый кеш если нужно
            if use_file_cache:
                cached_value = file_cache.get(cache_type, cache_key, max_age=ttl)
                if cached_value is not None:
                    logger.debug(f"Cache hit (file) для {func.__name__}: {cache_key[:50]}")
                    # Сохраняем в memory cache для быстрого доступа
                    memory_cache.set(cache_type, cache_key, cached_value)
                    return cached_value
            
            # Cache miss - выполняем функцию
            logger.debug(f"Cache miss для {func.__name__}: {cache_key[:50]}")
            result = func(*args, **kwargs)
            
            # Сохраняем результат в кеш
            memory_cache.set(cache_type, cache_key, result)
            if use_file_cache:
                file_cache.set(cache_type, cache_key, result)
            
            return result
        
        # Добавляем метод для очистки кеша этой функции
        def clear_cache():
            memory_cache.clear(cache_type)
            logger.info(f"Кеш очищен для {func.__name__}")
        
        wrapper.clear_cache = clear_cache
        return wrapper
    
    return decorator


def cache_api_response(ttl: int = API_CACHE_TTL):
    """
    Специализированный декоратор для кеширования API ответов
    
    Args:
        ttl: Время жизни кеша в секундах
    """
    return cache_result(
        cache_type='api',
        ttl=ttl,
        use_file_cache=True
    )


def cache_news_data(ttl: int = NEWS_CACHE_TTL):
    """
    Специализированный декоратор для кеширования новостных данных
    
    Args:
        ttl: Время жизни кеша в секундах
    """
    return cache_result(
        cache_type='processed',
        ttl=ttl,
        use_file_cache=True
    )


# ========================================================================
# УПРАВЛЕНИЕ КЕШЕМ
# ========================================================================

class CacheManager:
    """Центральный менеджер для управления всеми видами кеша"""
    
    def __init__(self):
        self.memory = memory_cache
        self.file = file_cache
    
    def clear_all(self):
        """Очищает весь кеш"""
        self.memory.clear()
        logger.info("Memory кеш очищен")
        
        # Удаляем все файлы кеша
        for cache_file in CACHE_DIR.rglob("*"):
            if cache_file.is_file():
                try:
                    cache_file.unlink()
                except Exception as e:
                    logger.error(f"Ошибка удаления {cache_file}: {e}")
        
        logger.info("Файловый кеш очищен")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику использования кеша
        
        Returns:
            Dict со статистикой
        """
        file_sizes = self.file.get_cache_size()
        
        return {
            'memory_cache': {
                'api_items': len(self.memory.api_cache),
                'processed_items': len(self.memory.processed_cache),
                'prompt_items': len(self.memory.prompt_cache)
            },
            'file_cache': {
                'news_size': file_sizes.get('news', 0),
                'image_size': file_sizes.get('image', 0),
                'api_size': file_sizes.get('api', 0),
                'total_size': file_sizes.get('total', 0)
            }
        }
    
    def cleanup(self, max_age_days: int = 7):
        """
        Очищает старые и неиспользуемые данные кеша
        
        Args:
            max_age_days: Максимальный возраст файлов в днях
        """
        logger.info(f"Очистка кеша старше {max_age_days} дней...")
        self.file.clear_old_cache(max_age_days)
        logger.info("Очистка завершена")


# Глобальный экземпляр менеджера кеша
cache_manager = CacheManager()


# ========================================================================
# ТЕСТИРОВАНИЕ
# ========================================================================

def test_cache_functionality():
    """Тестирует функциональность кеширования"""
    logger.info("🧪 Тестирование системы кеширования...")
    
    # Тест memory cache
    memory_cache.set('api', 'test_key', {'data': 'test'})
    result = memory_cache.get('api', 'test_key')
    assert result == {'data': 'test'}, "Memory cache failed"
    logger.info("✅ Memory cache работает")
    
    # Тест file cache
    file_cache.set('api', 'test_file_key', {'file_data': 'test'})
    result = file_cache.get('api', 'test_file_key')
    assert result == {'file_data': 'test'}, "File cache failed"
    logger.info("✅ File cache работает")
    
    # Тест декоратора
    @cache_result(cache_type='processed', use_file_cache=False)
    def expensive_function(x: int) -> int:
        logger.debug(f"Вычисляю expensive_function({x})")
        return x * x
    
    # Первый вызов - cache miss
    result1 = expensive_function(5)
    assert result1 == 25
    
    # Второй вызов - cache hit
    result2 = expensive_function(5)
    assert result2 == 25
    logger.info("✅ Cache декоратор работает")
    
    # Получаем статистику
    stats = cache_manager.get_statistics()
    logger.info(f"📊 Статистика кеша: {stats}")
    
    # Очищаем тестовые данные
    cache_manager.clear_all()
    
    logger.info("✅ Все тесты кеширования пройдены")


if __name__ == "__main__":
    test_cache_functionality()