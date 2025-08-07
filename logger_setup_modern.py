"""
Modern Logger Setup для NEWSMAKER с красивыми иконками
Использует Rich library для стильного форматирования
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# Пробуем импортировать Rich, если не установлен - используем fallback
try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from loguru import logger
import config

# Импортируем наш маппер иконок
sys.path.insert(0, str(Path(__file__).parent))
from utils.icon_mapper import IconMapper, IconStyle


class ModernLogger:
    """Современная система логирования с красивыми иконками"""
    
    def __init__(self):
        self.icon_mapper = IconMapper()
        self.console = Console() if RICH_AVAILABLE else None
        
        # Маппинг уровней логирования на иконки и цвета
        self.level_icons = {
            'DEBUG': ('🔍', 'dim cyan', '[DEBUG]'),
            'INFO': ('📊', 'blue', '[INFO]'),
            'SUCCESS': ('✅', 'green', '[OK]'),
            'WARNING': ('⚠️', 'yellow', '[WARN]'),
            'ERROR': ('❌', 'red', '[ERROR]'),
            'CRITICAL': ('💥', 'bold red', '[CRITICAL]')
        }
        
        self.setup_logger()
    
    def setup_logger(self):
        """Настройка логирования с красивым форматированием"""
        
        # Удаляем стандартные обработчики
        logger.remove()
        
        if RICH_AVAILABLE and sys.stdout.isatty():
            # Используем Rich для красивого вывода в консоль
            self._setup_rich_logging()
        else:
            # Fallback на обычное логирование с текстовыми иконками
            self._setup_text_logging()
        
        # Добавляем файловое логирование
        self._setup_file_logging()
    
    def _setup_rich_logging(self):
        """Настройка Rich логирования"""
        
        def rich_format(record):
            """Форматирование с использованием Rich"""
            level = record["level"].name
            icon, color, _ = self.level_icons.get(level, ('📝', 'white', '[LOG]'))
            
            # Заменяем эмодзи в сообщении на стильные иконки
            message = self.icon_mapper.replace_all_emojis(
                record["message"], 
                IconStyle.RICH
            )
            
            # Форматируем время
            time_str = record["time"].strftime("%H:%M:%S")
            
            # Создаем красивое форматирование
            if level == "ERROR" or level == "CRITICAL":
                return f"[bold {color}]{icon}[/bold {color}] [{color}]{time_str}[/{color}] {message}"
            else:
                return f"{icon} [dim]{time_str}[/dim] {message}"
        
        logger.add(
            RichHandler(console=self.console, rich_tracebacks=True),
            format=rich_format,
            level=config.LOG_LEVEL
        )
    
    def _setup_text_logging(self):
        """Настройка обычного текстового логирования"""
        
        def text_format(record):
            """Форматирование без Rich"""
            level = record["level"].name
            _, _, text_icon = self.level_icons.get(level, ('📝', 'white', '[LOG]'))
            
            # Заменяем эмодзи на текстовые маркеры
            message = self.icon_mapper.replace_all_emojis(
                record["message"], 
                IconStyle.TEXT
            )
            
            time_str = record["time"].strftime("%H:%M:%S")
            
            return f"{text_icon} {time_str} | {message}\n"
        
        logger.add(
            sys.stdout,
            format=text_format,
            level=config.LOG_LEVEL,
            colorize=True
        )
    
    def _setup_file_logging(self):
        """Настройка файлового логирования"""
        
        # Создаем папку для логов
        log_dir = Path(config.LOG_DIR)
        log_dir.mkdir(exist_ok=True)
        
        # Основной лог - без иконок, чистый текст
        logger.add(
            log_dir / config.LOG_FILE,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            level="DEBUG",
            rotation=config.LOG_ROTATION,
            retention=config.LOG_RETENTION,
            compression="zip",
            filter=lambda record: self.icon_mapper.strip_all_icons(record["message"])
        )
        
        # Лог ошибок
        logger.add(
            log_dir / "errors.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            level="ERROR",
            rotation="1 week",
            filter=lambda record: self.icon_mapper.strip_all_icons(record["message"])
        )
    
    def print_startup_banner(self):
        """Выводит красивый баннер при запуске"""
        
        if RICH_AVAILABLE and self.console:
            # Создаем красивый баннер с Rich
            banner = Panel.fit(
                Text.from_markup(
                    "[bold cyan]NEWSMAKER[/bold cyan] [dim]v2.1.0[/dim]\n"
                    "[yellow]Автоматический сервис юридических новостей[/yellow]\n"
                    f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
                    justify="center"
                ),
                border_style="bright_blue",
                padding=(1, 2)
            )
            self.console.print(banner)
            
            # Таблица конфигурации
            table = Table(title="Конфигурация системы", show_header=False)
            table.add_column("Параметр", style="cyan")
            table.add_column("Значение", style="green")
            
            table.add_row("📅 Сбор новостей", config.COLLECTION_TIME)
            table.add_row("📰 Количество новостей", "7 в день")
            table.add_row("⏰ Расписание", f"{len(config.PUBLICATION_SCHEDULE)} публикаций")
            table.add_row("🎨 Генерация изображений", "Включена")
            
            self.console.print(table)
        else:
            # Текстовый баннер
            print("\n" + "="*50)
            print(" " * 15 + "NEWSMAKER v2.1.0")
            print(" " * 5 + "Автоматический сервис юридических новостей")
            print("="*50)
            print(f"[CONFIG] Сбор новостей: {config.COLLECTION_TIME}")
            print(f"[CONFIG] Количество новостей: 7 в день")
            print(f"[CONFIG] Расписание: {len(config.PUBLICATION_SCHEDULE)} публикаций")
            print("="*50 + "\n")
    
    def log_with_icon(self, level: str, message: str, icon: Optional[str] = None):
        """
        Логирование с кастомной иконкой
        
        Args:
            level: Уровень логирования
            message: Сообщение
            icon: Кастомная иконка (опционально)
        """
        if icon:
            formatted_icon = self.icon_mapper.get_icon(icon)
            message = f"{formatted_icon} {message}"
        
        getattr(logger, level.lower())(message)
    
    def create_progress_bar(self, total: int, description: str = "Обработка"):
        """Создает прогресс-бар для длительных операций"""
        
        if RICH_AVAILABLE and self.console:
            from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
            
            return Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console
            )
        else:
            # Простой текстовый прогресс
            class SimpleProgress:
                def __init__(self, total, desc):
                    self.total = total
                    self.current = 0
                    self.desc = desc
                
                def update(self, advance=1):
                    self.current += advance
                    percent = (self.current / self.total) * 100
                    print(f"\r[PROGRESS] {self.desc}: {percent:.1f}%", end="")
                    if self.current >= self.total:
                        print()  # Новая строка в конце
            
            return SimpleProgress(total, description)


# Создаем глобальный экземпляр
modern_logger = ModernLogger()


# Экспортируем функции для обратной совместимости
def setup_logger():
    """Обратная совместимость с старым кодом"""
    return modern_logger


def log_startup_banner():
    """Вывод баннера при запуске"""
    modern_logger.print_startup_banner()


def log_system_info():
    """Логирование системной информации"""
    logger.info(f"Python версия: {sys.version}")
    logger.info(f"Рабочая директория: {os.getcwd()}")
    logger.info(f"Rich доступен: {'Да' if RICH_AVAILABLE else 'Нет'}")


def get_log_stats() -> List[str]:
    """Получение статистики логов"""
    log_dir = Path(config.LOG_DIR)
    if not log_dir.exists():
        return ["Папка логов не найдена"]
    
    stats = []
    total_size = 0
    file_count = 0
    
    for log_file in log_dir.glob("*.log*"):
        size = log_file.stat().st_size
        total_size += size
        file_count += 1
    
    stats.append(f"Файлов логов: {file_count}")
    stats.append(f"Общий размер: {total_size / 1024 / 1024:.2f} MB")
    
    return stats


# Тестирование при запуске
if __name__ == "__main__":
    # Инициализация
    setup_logger()
    
    # Показываем баннер
    log_startup_banner()
    
    # Тестовые сообщения
    logger.debug("🔍 Отладочное сообщение")
    logger.info("📊 Информационное сообщение")
    logger.success("✅ Успешное выполнение")
    logger.warning("⚠️ Предупреждение")
    logger.error("❌ Ошибка")
    
    # Системная информация
    log_system_info()
    
    # Статистика
    stats = get_log_stats()
    for stat in stats:
        logger.info(f"📊 {stat}")