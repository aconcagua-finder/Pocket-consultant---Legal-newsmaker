"""
Unified Logger Setup для NEWSMAKER
Объединяет функционал базового и modern логгера с опциональной поддержкой Rich
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from loguru import logger

import config

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


class UnifiedLogger:
    """Унифицированная система логирования с опциональной поддержкой Rich"""
    
    def __init__(self, use_rich: bool = False):
        """
        Инициализация логгера
        
        Args:
            use_rich: Использовать Rich для красивого вывода (если доступен)
        """
        self.use_rich = use_rich and RICH_AVAILABLE
        self.console = Console() if self.use_rich else None
        
        # Маппинг уровней логирования на иконки и цвета
        self.level_icons = {
            'DEBUG': ('🔍', 'dim cyan', '[DEBUG]'),
            'INFO': ('📊', 'blue', '[INFO]'),
            'SUCCESS': ('✅', 'green', '[OK]'),
            'WARNING': ('⚠️', 'yellow', '[WARN]'),
            'ERROR': ('❌', 'red', '[ERROR]'),
            'CRITICAL': ('💥', 'bold red', '[CRITICAL]')
        }
    
    def setup(self, log_level: str = None, log_file: str = None):
        """
        Настройка системы логирования
        
        Args:
            log_level: Уровень логирования (по умолчанию из config)
            log_file: Файл для логов (по умолчанию из config)
        """
        # Удаляем стандартные обработчики
        logger.remove()
        
        # Используем значения из config если не переданы
        log_level = log_level or config.LOG_LEVEL
        log_file = log_file or config.LOG_FILE
        
        # Создаем папку для логов
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Настройка консольного вывода
        if self.use_rich and sys.stdout.isatty():
            self._setup_rich_console(log_level)
        else:
            self._setup_text_console(log_level)
        
        # Настройка файлового логирования
        self._setup_file_logging(logs_dir, log_file)
        
        # Логируем успешную настройку
        logger.info("📝 Система логирования настроена успешно")
        logger.info(f"📁 Логи сохраняются в папку: {logs_dir.absolute()}")
        logger.info(f"📊 Уровень логирования: {log_level}")
        if self.use_rich:
            logger.info("🎨 Rich форматирование включено")
    
    def _setup_rich_console(self, log_level: str):
        """Настройка Rich консольного вывода"""
        
        def rich_format(record):
            """Форматирование с использованием Rich"""
            level = record["level"].name
            icon, color, _ = self.level_icons.get(level, ('📝', 'white', '[LOG]'))
            
            time_str = record["time"].strftime("%H:%M:%S")
            message = record["message"]
            
            if level in ["ERROR", "CRITICAL"]:
                return f"[bold {color}]{icon}[/bold {color}] [{color}]{time_str}[/{color}] {message}"
            else:
                return f"{icon} [dim]{time_str}[/dim] {message}"
        
        logger.add(
            RichHandler(console=self.console, rich_tracebacks=True),
            format=rich_format,
            level=log_level
        )
    
    def _setup_text_console(self, log_level: str):
        """Настройка обычного текстового консольного вывода"""
        
        # Формат для консоли (красивый и читаемый)
        console_format = (
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<level>{message}</level>"
        )
        
        logger.add(
            sys.stdout,
            format=console_format,
            level=log_level,
            colorize=True,
            enqueue=True
        )
    
    def _setup_file_logging(self, logs_dir: Path, log_file: str):
        """Настройка файлового логирования"""
        
        # Формат для логов в файл (подробный)
        file_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
        
        # Основной лог файл (все сообщения)
        logger.add(
            logs_dir / log_file,
            format=file_format,
            level="DEBUG",
            rotation="10 MB",
            retention="30 days",
            compression="zip",
            enqueue=True,
            encoding="utf-8"
        )
        
        # Отдельный файл только для ошибок
        logger.add(
            logs_dir / "errors.log",
            format=file_format,
            level="ERROR",
            rotation="5 MB",
            retention="60 days",
            compression="zip",
            enqueue=True,
            encoding="utf-8"
        )
        
        # Отдельный файл для ежедневных отчетов
        daily_log_name = f"daily_{datetime.now().strftime('%Y%m')}.log"
        logger.add(
            logs_dir / daily_log_name,
            format=file_format,
            level="INFO",
            filter=lambda record: any(keyword in record["message"].lower() 
                                     for keyword in ["ежедневной задачи", "daily job"]) or
                                 any(emoji in record["message"] 
                                     for emoji in ["🚀", "✅", "❌"]),
            rotation="1 month",
            retention="12 months",
            compression="zip",
            enqueue=True,
            encoding="utf-8"
        )
    
    def print_startup_banner(self):
        """Выводит красивый баннер при запуске"""
        
        if self.use_rich and self.console:
            # Создаем красивый баннер с Rich
            banner = Panel.fit(
                Text.from_markup(
                    "[bold cyan]NEWSMAKER[/bold cyan] [dim]v2.3.1[/dim]\n"
                    "[yellow]Автоматический сервис юридических новостей РФ[/yellow]\n"
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
            # Текстовый баннер для обратной совместимости
            banner = """
    ╔════════════════════════════════════════════════╗
    ║                  NEWSMAKER                     ║
    ║            Автоматический сервис               ║
    ║         юридических новостей РФ                ║
    ║                                                ║
    ║  🤖 AI: Perplexity Sonar Deep Research        ║
    ║  📱 Публикация: Telegram                      ║
    ║  ⏰ Расписание: 7 публикаций в день           ║
    ╚════════════════════════════════════════════════╝
            """
            
            for line in banner.strip().split('\n'):
                logger.opt(colors=True).info(f"<cyan>{line}</cyan>")


# Глобальный экземпляр логгера
_unified_logger = None


def setup_logger(use_rich: bool = False, log_level: str = None, log_file: str = None):
    """
    Настраивает систему логирования для всего проекта
    
    Args:
        use_rich: Использовать Rich для красивого вывода (если доступен)
        log_level: Уровень логирования
        log_file: Файл для логов
    """
    global _unified_logger
    
    # Определяем, использовать ли Rich по умолчанию
    # Если Rich доступен и терминал поддерживает - используем
    if use_rich is None:
        use_rich = RICH_AVAILABLE and sys.stdout.isatty()
    
    _unified_logger = UnifiedLogger(use_rich)
    _unified_logger.setup(log_level, log_file)
    
    return _unified_logger


def log_system_info():
    """Логирует информацию о системе при запуске"""
    logger.info("=" * 60)
    logger.info("🌟 NEWSMAKER - Запуск системы")
    logger.info("=" * 60)
    
    # Информация о системе
    import platform
    logger.info(f"💻 Система: {platform.system()} {platform.release()}")
    logger.info(f"🐍 Python: {platform.python_version()}")
    logger.info(f"📅 Запуск: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    
    # Проверка конфигурации
    logger.info("🔧 Проверка конфигурации:")
    
    perplexity_key_ok = bool(config.PERPLEXITY_API_KEY)
    telegram_token_ok = bool(config.TELEGRAM_BOT_TOKEN)
    telegram_channel_ok = bool(config.TELEGRAM_CHANNEL_ID)
    
    logger.info(f"  ✓ Perplexity API ключ: {'✅ Настроен' if perplexity_key_ok else '❌ Не настроен'}")
    logger.info(f"  ✓ Telegram токен: {'✅ Настроен' if telegram_token_ok else '❌ Не настроен'}")
    logger.info(f"  ✓ Telegram канал: {'✅ Настроен' if telegram_channel_ok else '❌ Не настроен'}")
    logger.info(f"  ✓ Время сбора: {config.COLLECTION_TIME}")
    logger.info(f"  ✓ Rich доступен: {'✅ Да' if RICH_AVAILABLE else '❌ Нет'}")
    
    # Предупреждения о недостающей конфигурации
    if not telegram_token_ok:
        logger.warning("⚠️ TELEGRAM_BOT_TOKEN не установлен в .env файле")
    if not telegram_channel_ok:
        logger.warning("⚠️ TELEGRAM_CHANNEL_ID не установлен в .env файле")
    
    config_complete = perplexity_key_ok and telegram_token_ok and telegram_channel_ok
    
    if config_complete:
        logger.info("🎉 Конфигурация полная - готов к работе!")
    else:
        logger.warning("⚠️ Неполная конфигурация - некоторые функции могут не работать")
    
    logger.info("=" * 60)


def log_startup_banner():
    """Выводит красивый баннер при запуске"""
    global _unified_logger
    
    if _unified_logger:
        _unified_logger.print_startup_banner()
    else:
        # Fallback если логгер не инициализирован
        logger.info("🚀 NEWSMAKER v2.3.1 - Запуск системы")


def get_log_stats():
    """Возвращает статистику логов для отчетов"""
    logs_dir = Path("logs")
    
    if not logs_dir.exists():
        return "Папка логов не найдена"
    
    stats = []
    stats.append(f"📁 Папка логов: {logs_dir.absolute()}")
    
    # Размер всех лог файлов
    total_size = 0
    log_count = 0
    
    for log_file in logs_dir.glob("*.log*"):
        if log_file.is_file():
            size = log_file.stat().st_size
            total_size += size
            log_count += 1
            
            # Читаемый размер
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            
            stats.append(f"  📄 {log_file.name}: {size_str}")
    
    # Общая статистика
    if total_size < 1024:
        total_str = f"{total_size} B"
    elif total_size < 1024 * 1024:
        total_str = f"{total_size / 1024:.1f} KB"
    else:
        total_str = f"{total_size / (1024 * 1024):.1f} MB"
    
    stats.insert(1, f"📊 Всего файлов: {log_count}, общий размер: {total_str}")
    
    return "\n".join(stats)


def get_logger():
    """Возвращает настроенный logger для использования в других модулях"""
    return logger


# Для обратной совместимости со старым кодом
if __name__ == "__main__":
    # Тестирование
    setup_logger(use_rich=True)
    log_startup_banner()
    log_system_info()
    
    # Тестовые сообщения
    logger.debug("🔍 Отладочное сообщение")
    logger.info("📊 Информационное сообщение")
    logger.success("✅ Успешное выполнение")
    logger.warning("⚠️ Предупреждение")
    logger.error("❌ Ошибка")
    
    # Статистика
    print("\n" + get_log_stats())