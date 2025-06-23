#!/usr/bin/env python3
"""
NEWSMAKER - Автоматический сервис юридических новостей РФ

Получает ежедневные обновления законодательства через Perplexity AI
и публикует их в Telegram канале.

"""

import sys
import argparse
from pathlib import Path

# Настройка логирования должна быть первой
from logger_setup import setup_logger, log_startup_banner, log_system_info, get_log_stats
from scheduler import NewsmakerScheduler
from perplexity_client import PerplexityClient
from telegram_client import TelegramClient
import config

# Инициализируем логирование
setup_logger()
from loguru import logger


def test_mode():
    """Режим тестирования всех компонентов"""
    logger.info("🧪 Запуск режима тестирования...")
    
    scheduler = NewsmakerScheduler()
    
    # Тестируем все компоненты
    success = scheduler.test_components()
    
    if success:
        logger.info("🎉 Все тесты пройдены успешно!")
        logger.info("✨ Система готова к работе!")
        return True
    else:
        logger.error("❌ Некоторые тесты не прошли")
        logger.error("🔧 Проверьте конфигурацию и попробуйте снова")
        return False


def manual_run():
    """Ручной запуск получения и отправки новостей"""
    logger.info("🚀 Ручной запуск задачи...")
    
    scheduler = NewsmakerScheduler()
    scheduler.run_once_now()
    
    logger.info("✅ Ручной запуск завершен")


def scheduler_mode():
    """Режим планировщика - постоянная работа"""
    logger.info("⏰ Запуск в режиме планировщика...")
    
    scheduler = NewsmakerScheduler()
    
    # Сначала тестируем компоненты
    logger.info("🔧 Предварительная проверка компонентов...")
    if not scheduler.test_components():
        logger.error("❌ Компоненты не прошли проверку")
        logger.error("🛑 Запуск планировщика отменен")
        return False
    
    logger.info("✅ Компоненты готовы к работе")
    
    # Запускаем планировщик
    try:
        scheduler.start_scheduler()
    except KeyboardInterrupt:
        logger.info("⏹️ Планировщик остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка планировщика: {e}")
        return False
    
    return True


def info_mode():
    """Показывает информацию о системе"""
    log_startup_banner()
    log_system_info()
    
    logger.info("\n" + "📋 СТАТИСТИКА ЛОГОВ:")
    stats = get_log_stats()
    for line in stats.split('\n'):
        logger.info(f"   {line}")
    
    # Показываем следующие шаги
    logger.info("\n" + "🎯 ДОСТУПНЫЕ КОМАНДЫ:")
    logger.info("   python main.py --test     # Тестирование компонентов")
    logger.info("   python main.py --run      # Ручной запуск задачи")  
    logger.info("   python main.py --start    # Запуск планировщика")
    logger.info("   python main.py --info     # Показать эту информацию")


def setup_dotenv_if_needed():
    """Создает .env файл если его нет"""
    env_file = Path(".env")
    
    if not env_file.exists():
        logger.warning("📝 Файл .env не найден, создаю из шаблона...")
        
        env_content = """# Скопировано из env_example.txt
# Заполните своими данными

TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHANNEL_ID=your_channel_id_here
"""
        
        try:
            env_file.write_text(env_content, encoding='utf-8')
            logger.info("✅ Файл .env создан")
            logger.warning("⚠️ Не забудьте заполнить TELEGRAM_BOT_TOKEN и TELEGRAM_CHANNEL_ID!")
        except Exception as e:
            logger.error(f"❌ Ошибка при создании .env: {e}")


def main():
    """Главная функция приложения"""
    
    # Красивый баннер
    log_startup_banner()
    
    # Настройка аргументов командной строки
    parser = argparse.ArgumentParser(
        description="NEWSMAKER - Автоматический сервис юридических новостей РФ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python main.py --info     # Информация о системе
  python main.py --test     # Тестирование всех компонентов  
  python main.py --run      # Ручной запуск получения новостей
  python main.py --start    # Запуск планировщика (основной режим)

Для первого запуска:
  1. Заполните .env файл (токен бота и ID канала)
  2. Запустите тест: python main.py --test
  3. Если тест прошел, запустите: python main.py --start
        """
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--test', action='store_true', 
                      help='Тестировать все компоненты системы')
    group.add_argument('--run', action='store_true',
                      help='Запустить задачу вручную (один раз)')
    group.add_argument('--start', action='store_true',
                      help='Запустить планировщик (основной режим)')
    group.add_argument('--info', action='store_true',
                      help='Показать информацию о системе')
    
    args = parser.parse_args()
    
    # Проверяем .env файл
    setup_dotenv_if_needed()
    
    # Логируем системную информацию
    log_system_info()
    
    # Выполняем нужное действие
    try:
        if args.test:
            success = test_mode()
            sys.exit(0 if success else 1)
            
        elif args.run:
            manual_run()
            sys.exit(0)
            
        elif args.start:
            success = scheduler_mode()
            sys.exit(0 if success else 1)
            
        elif args.info:
            info_mode()
            sys.exit(0)
            
        else:
            # Если аргументы не указаны, показываем информацию
            info_mode()
            logger.info("\n💡 Укажите нужный режим работы (см. примеры выше)")
            sys.exit(0)
            
    except KeyboardInterrupt:
        logger.info("\n⏹️ Программа остановлена пользователем")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")
        sys.exit(1)


if __name__ == "__main__":
    main() 