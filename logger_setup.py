import sys
import os
from pathlib import Path
from loguru import logger
from datetime import datetime

import config


def setup_logger():
    """Настраивает систему логирования для всего проекта"""
    
    # Удаляем стандартный обработчик loguru
    logger.remove()
    
    # Создаем папку для логов если её нет
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Формат для логов в файл (подробный)
    file_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # Формат для консоли (красивый и читаемый)
    console_format = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
    )
    
    # Консольный вывод (цветной и красивый)
    logger.add(
        sys.stdout,
        format=console_format,
        level=config.LOG_LEVEL,
        colorize=True,
        enqueue=True
    )
    
    # Основной лог файл (все сообщения)
    logger.add(
        logs_dir / config.LOG_FILE,
        format=file_format,
        level="DEBUG",
        rotation="10 MB",  # Создавать новый файл при достижении 10MB
        retention="30 days",  # Хранить логи 30 дней
        compression="zip",  # Сжимать старые логи
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
        filter=lambda record: "ежедневной задачи" in record["message"].lower() or 
                             "daily job" in record["message"].lower() or
                             "🚀" in record["message"] or "✅" in record["message"] or "❌" in record["message"],
        rotation="1 month",
        retention="12 months",
        compression="zip",
        enqueue=True,
        encoding="utf-8"
    )
    
    # Логируем успешную настройку
    logger.info("📝 Система логирования настроена успешно")
    logger.info(f"📁 Логи сохраняются в папку: {logs_dir.absolute()}")
    logger.info(f"📊 Уровень логирования: {config.LOG_LEVEL}")


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
    logger.info(f"  ✓ Время запуска: {config.DAILY_RUN_TIME}")
    
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
    banner = """
    ╔════════════════════════════════════════════════╗
    ║                  NEWSMAKER                     ║
    ║            Автоматический сервис               ║
    ║         юридических новостей РФ                ║
    ║                                                ║
    ║  🤖 AI: Perplexity Sonar-pro                  ║
    ║  📱 Публикация: Telegram                      ║
    ║  ⏰ Расписание: Каждые 3 часа                 ║
    ╚════════════════════════════════════════════════╝
    """
    
    # Логируем каждую строку баннера отдельно
    for line in banner.strip().split('\n'):
        logger.opt(colors=True).info(f"<cyan>{line}</cyan>")


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


# Функция для быстрого импорта в других модулях
def get_logger():
    """Возвращает настроенный logger для использования в других модулях"""
    return logger 