"""
Утилиты для безопасной работы с файлами

Обеспечивает блокировки файлов, атомарные операции записи
и безопасное управление файловой системой.
"""

import json
import os
import shutil
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from loguru import logger
import time

# Определяем операционную систему
WINDOWS = os.name == 'nt'

if WINDOWS:
    try:
        import msvcrt
    except ImportError:
        msvcrt = None
else:
    try:
        import fcntl
    except ImportError:
        fcntl = None


# ========================================================================
# БЛОКИРОВКИ ФАЙЛОВ
# ========================================================================

class FileLock:
    """Класс для блокировки файлов при чтении/записи"""
    
    _locks = {}  # Глобальный словарь блокировок
    _lock = threading.Lock()  # Блокировка для доступа к словарю
    
    def __init__(self, filepath: Union[str, Path], timeout: float = 10.0):
        """
        Инициализация блокировки файла
        
        Args:
            filepath: Путь к файлу
            timeout: Таймаут ожидания блокировки в секундах
        """
        self.filepath = Path(filepath)
        self.timeout = timeout
        self.lock_file = Path(str(self.filepath) + '.lock')
        self.file_handle = None
        self.acquired = False
        
    def acquire(self) -> bool:
        """
        Получить блокировку файла
        
        Returns:
            bool: True если блокировка получена
        """
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            try:
                # Создаём lock файл
                self.file_handle = open(self.lock_file, 'w')
                
                if WINDOWS and msvcrt:
                    # На Windows используем msvcrt
                    msvcrt.locking(self.file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                elif not WINDOWS and fcntl:
                    # На Unix используем fcntl
                    fcntl.flock(self.file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    # Fallback - просто проверяем существование файла
                    pass
                
                self.acquired = True
                return True
                
            except (IOError, OSError) as e:
                # Блокировка занята, ждём
                if self.file_handle:
                    self.file_handle.close()
                    self.file_handle = None
                
                time.sleep(0.1)
                continue
        
        logger.warning(f"Не удалось получить блокировку для {self.filepath} за {self.timeout} секунд")
        return False
    
    def release(self):
        """Освободить блокировку файла"""
        if self.file_handle:
            try:
                if WINDOWS and msvcrt:
                    msvcrt.locking(self.file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                elif not WINDOWS and fcntl:
                    fcntl.flock(self.file_handle.fileno(), fcntl.LOCK_UN)
            except Exception as e:
                logger.error(f"Ошибка при освобождении блокировки: {e}")
            finally:
                self.file_handle.close()
                self.file_handle = None
        
        # Удаляем lock файл
        if self.lock_file.exists():
            try:
                self.lock_file.unlink()
            except Exception:
                pass
        
        self.acquired = False
    
    def __enter__(self):
        """Вход в контекст"""
        if not self.acquire():
            raise IOError(f"Не удалось заблокировать файл {self.filepath}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекста"""
        self.release()


# ========================================================================
# АТОМАРНЫЕ ОПЕРАЦИИ
# ========================================================================

@contextmanager
def atomic_write(filepath: Union[str, Path], mode: str = 'w', encoding: str = 'utf-8'):
    """
    Контекстный менеджер для атомарной записи в файл
    
    Сначала записывает во временный файл, затем атомарно перемещает его.
    
    Args:
        filepath: Путь к целевому файлу
        mode: Режим открытия файла
        encoding: Кодировка файла
        
    Yields:
        file: Файловый объект для записи
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # Создаём временный файл в той же директории
    temp_fd, temp_path = tempfile.mkstemp(
        dir=filepath.parent,
        prefix=f".{filepath.name}.",
        suffix='.tmp'
    )
    
    try:
        # Открываем временный файл для записи
        with os.fdopen(temp_fd, mode, encoding=encoding) as temp_file:
            yield temp_file
        
        # Атомарно перемещаем временный файл на место целевого
        if WINDOWS:
            # На Windows нужно сначала удалить целевой файл
            if filepath.exists():
                filepath.unlink()
        
        Path(temp_path).rename(filepath)
        
    except Exception as e:
        # В случае ошибки удаляем временный файл
        try:
            Path(temp_path).unlink()
        except:
            pass
        raise e


def safe_json_read(filepath: Union[str, Path], default: Any = None) -> Any:
    """
    Безопасное чтение JSON файла с блокировкой
    
    Args:
        filepath: Путь к JSON файлу
        default: Значение по умолчанию если файл не существует или повреждён
        
    Returns:
        Any: Содержимое JSON файла или default
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        return default
    
    try:
        with FileLock(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Ошибка чтения JSON из {filepath}: {e}")
        return default


def safe_json_write(filepath: Union[str, Path], data: Any, indent: int = 2) -> bool:
    """
    Безопасная запись JSON файла с блокировкой и атомарностью
    
    Args:
        filepath: Путь к JSON файлу
        data: Данные для сохранения
        indent: Отступ для форматирования
        
    Returns:
        bool: True если запись успешна
    """
    filepath = Path(filepath)
    
    try:
        with FileLock(filepath):
            with atomic_write(filepath, 'w', 'utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
        return True
    except Exception as e:
        logger.error(f"Ошибка записи JSON в {filepath}: {e}")
        return False


# ========================================================================
# УПРАВЛЕНИЕ ФАЙЛАМИ
# ========================================================================

def ensure_directory(dirpath: Union[str, Path]) -> Path:
    """
    Убеждается что директория существует, создаёт если нет
    
    Args:
        dirpath: Путь к директории
        
    Returns:
        Path: Путь к директории
    """
    dirpath = Path(dirpath)
    dirpath.mkdir(parents=True, exist_ok=True)
    return dirpath


def safe_delete_file(filepath: Union[str, Path]) -> bool:
    """
    Безопасное удаление файла
    
    Args:
        filepath: Путь к файлу
        
    Returns:
        bool: True если файл удалён или не существовал
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        return True
    
    try:
        filepath.unlink()
        logger.debug(f"Файл удалён: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления файла {filepath}: {e}")
        return False


def safe_move_file(src: Union[str, Path], dst: Union[str, Path]) -> bool:
    """
    Безопасное перемещение файла
    
    Args:
        src: Исходный путь
        dst: Целевой путь
        
    Returns:
        bool: True если перемещение успешно
    """
    src = Path(src)
    dst = Path(dst)
    
    if not src.exists():
        logger.error(f"Исходный файл не существует: {src}")
        return False
    
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        logger.debug(f"Файл перемещён: {src} -> {dst}")
        return True
    except Exception as e:
        logger.error(f"Ошибка перемещения файла {src} -> {dst}: {e}")
        return False


def safe_copy_file(src: Union[str, Path], dst: Union[str, Path]) -> bool:
    """
    Безопасное копирование файла
    
    Args:
        src: Исходный путь
        dst: Целевой путь
        
    Returns:
        bool: True если копирование успешно
    """
    src = Path(src)
    dst = Path(dst)
    
    if not src.exists():
        logger.error(f"Исходный файл не существует: {src}")
        return False
    
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        logger.debug(f"Файл скопирован: {src} -> {dst}")
        return True
    except Exception as e:
        logger.error(f"Ошибка копирования файла {src} -> {dst}: {e}")
        return False


# ========================================================================
# РЕЗЕРВНОЕ КОПИРОВАНИЕ
# ========================================================================

def create_backup(filepath: Union[str, Path], max_backups: int = 3) -> Optional[Path]:
    """
    Создаёт резервную копию файла
    
    Args:
        filepath: Путь к файлу
        max_backups: Максимальное количество резервных копий
        
    Returns:
        Path: Путь к созданной резервной копии или None
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        return None
    
    # Создаём имя для резервной копии
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"{filepath.stem}_backup_{timestamp}{filepath.suffix}"
    backup_path = filepath.parent / backup_name
    
    # Копируем файл
    if safe_copy_file(filepath, backup_path):
        logger.info(f"Создана резервная копия: {backup_path}")
        
        # Удаляем старые резервные копии
        cleanup_old_backups(filepath, max_backups)
        
        return backup_path
    
    return None


def cleanup_old_backups(original_filepath: Union[str, Path], max_backups: int = 3):
    """
    Удаляет старые резервные копии файла
    
    Args:
        original_filepath: Путь к оригинальному файлу
        max_backups: Максимальное количество резервных копий
    """
    filepath = Path(original_filepath)
    pattern = f"{filepath.stem}_backup_*{filepath.suffix}"
    
    # Находим все резервные копии
    backups = sorted(filepath.parent.glob(pattern), key=lambda p: p.stat().st_mtime)
    
    # Удаляем лишние
    while len(backups) > max_backups:
        oldest = backups.pop(0)
        safe_delete_file(oldest)
        logger.debug(f"Удалена старая резервная копия: {oldest}")


# ========================================================================
# ОЧИСТКА СТАРЫХ ФАЙЛОВ
# ========================================================================

def cleanup_old_files(directory: Union[str, Path], pattern: str, max_age_days: int):
    """
    Удаляет файлы старше указанного возраста
    
    Args:
        directory: Директория для очистки
        pattern: Паттерн файлов (glob)
        max_age_days: Максимальный возраст файлов в днях
    """
    directory = Path(directory)
    cutoff_date = datetime.now() - timedelta(days=max_age_days)
    
    for filepath in directory.glob(pattern):
        try:
            file_mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
            
            if file_mtime < cutoff_date:
                safe_delete_file(filepath)
                logger.info(f"Удалён старый файл: {filepath.name}")
                
        except Exception as e:
            logger.error(f"Ошибка при проверке файла {filepath}: {e}")


# ========================================================================
# СТАТИСТИКА ФАЙЛОВ
# ========================================================================

def get_directory_size(directory: Union[str, Path]) -> int:
    """
    Получает размер директории в байтах
    
    Args:
        directory: Путь к директории
        
    Returns:
        int: Размер в байтах
    """
    directory = Path(directory)
    total_size = 0
    
    for filepath in directory.rglob('*'):
        if filepath.is_file():
            total_size += filepath.stat().st_size
    
    return total_size


def format_file_size(size_bytes: int) -> str:
    """
    Форматирует размер файла в читаемый вид
    
    Args:
        size_bytes: Размер в байтах
        
    Returns:
        str: Отформатированный размер
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    
    return f"{size_bytes:.2f} PB"


def get_file_info(filepath: Union[str, Path]) -> Dict[str, Any]:
    """
    Получает информацию о файле
    
    Args:
        filepath: Путь к файлу
        
    Returns:
        dict: Информация о файле
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        return {"exists": False, "path": str(filepath)}
    
    stat = filepath.stat()
    
    return {
        "exists": True,
        "path": str(filepath),
        "name": filepath.name,
        "size": stat.st_size,
        "size_formatted": format_file_size(stat.st_size),
        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "is_file": filepath.is_file(),
        "is_dir": filepath.is_dir()
    }


# ========================================================================
# ТЕСТЫ
# ========================================================================

def test_file_operations():
    """Тестирует операции с файлами"""
    logger.info("Тестирование файловых операций...")
    
    test_dir = Path("test_files")
    test_file = test_dir / "test.json"
    
    # Создаём тестовую директорию
    ensure_directory(test_dir)
    
    # Тест атомарной записи
    test_data = {"test": "data", "number": 42}
    success = safe_json_write(test_file, test_data)
    assert success, "Ошибка записи JSON"
    
    # Тест чтения с блокировкой
    read_data = safe_json_read(test_file, {})
    assert read_data == test_data, "Данные не совпадают"
    
    # Тест резервного копирования
    backup = create_backup(test_file, max_backups=2)
    assert backup and backup.exists(), "Резервная копия не создана"
    
    # Очистка
    shutil.rmtree(test_dir)
    
    logger.info("✅ Тесты файловых операций пройдены")


if __name__ == "__main__":
    test_file_operations()