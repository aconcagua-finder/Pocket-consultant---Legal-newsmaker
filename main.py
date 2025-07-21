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
from news_collector import NewsCollector
from news_publisher import NewsPublisher
from news_scheduler import NewsmakerScheduler as NewNewsmakerScheduler
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


def collect_news_mode():
    """Ручной сбор новостей"""
    logger.info("🔍 Ручной сбор законодательных новостей...")
    
    collector = NewsCollector()
    success = collector.collect_daily_news()
    
    if success:
        status = collector.get_news_file_status()
        logger.info(f"📊 Собрано новостей: {status.get('total_news', 0)}")
        logger.info("✅ Сбор завершен успешно")
    else:
        logger.error("❌ Ошибка при сборе новостей")
        sys.exit(1)


def publish_next_mode():
    """Публикация следующей новости"""
    logger.info("📱 Публикация следующей новости...")
    
    publisher = NewsPublisher()
    result = publisher.publish_next_scheduled_news()
    
    if result['success']:
        title = result.get('title', 'Без названия')
        logger.info(f"✅ Опубликовано: {title[:50]}...")
    else:
        reason = result.get('reason', 'unknown')
        if reason == 'no_news_ready':
            logger.info("📰 Нет новостей готовых к публикации")
        else:
            logger.error(f"❌ Ошибка публикации: {reason}")
            sys.exit(1)


def force_publish_mode(priority: int):
    """Принудительная публикация новости с приоритетом"""
    logger.info(f"🚀 Принудительная публикация приоритет {priority}...")
    
    publisher = NewsPublisher()
    success = publisher.force_publish_by_priority(priority)
    
    if success:
        logger.info(f"✅ Новость приоритет {priority} опубликована")
    else:
        logger.error(f"❌ Не удалось опубликовать приоритет {priority}")
        sys.exit(1)


def test_publish_all_mode():
    """Тестовая публикация всех новостей подряд с интервалом"""
    logger.info("🧪 Тестовая публикация всех новостей подряд...")
    
    publisher = NewsPublisher()
    result = publisher.publish_all_news_for_testing(interval=6)
    
    if result['success']:
        total = result['total_news']
        successful = result['successful_count']
        failed = result['failed_count']
        rate = result['success_rate'] * 100
        
        logger.info("🎉 Тестирование завершено!")
        logger.info(f"📊 Результат: {successful}/{total} успешно ({rate:.1f}%)")
        
        if failed > 0:
            logger.warning(f"⚠️ Неудачных публикаций: {failed}")
    else:
        reason = result.get('reason', 'unknown')
        message = result.get('message', 'Неизвестная ошибка')
        logger.error(f"❌ Ошибка тестирования: {reason} - {message}")
        sys.exit(1)


def status_mode():
    """Показывает статус системы"""
    logger.info("📊 СТАТУС СИСТЕМЫ:")
    logger.info("=" * 50)
    
    # Статус сбора
    collector = NewsCollector()
    collection_status = collector.get_news_file_status()
    
    logger.info("🔍 СБОР НОВОСТЕЙ:")
    if collection_status['exists']:
        logger.info(f"   ✅ Файл новостей: {collection_status['date']}")
        logger.info(f"   📰 Всего новостей: {collection_status.get('total_news', 0)}")
        logger.info(f"   ⏰ Время сбора: {collection_status.get('collected_at', 'неизвестно')}")
    else:
        logger.info("   ❌ Новости еще не собраны")
    
    # Статус публикаций
    publisher = NewsPublisher()
    publication_status = publisher.get_publication_status()
    
    logger.info("\n📱 ПУБЛИКАЦИИ:")
    if publication_status['file_exists']:
        total = publication_status['total_news']
        published = publication_status['published_count']
        unpublished = publication_status['unpublished_count']
        
        logger.info(f"   📊 Опубликовано: {published}/{total}")
        logger.info(f"   ⏳ Ожидают: {unpublished}")
        
        logger.info("\n   📋 ДЕТАЛИ:")
        for detail in publication_status.get('news_details', []):
            status_icon = "✅" if detail['published'] else "⏳"
            priority = detail['priority']
            time_str = detail['scheduled_time']
            title = detail['title']
            
            if detail['published']:
                logger.info(f"   {status_icon} Приоритет {priority} ({time_str}): {title}")
            else:
                logger.info(f"   {status_icon} Приоритет {priority} ({time_str}): {title}")
    else:
        logger.info("   ❌ Нет данных о публикациях")
    
    logger.info("=" * 50)


def info_mode():
    """Показывает информацию о системе"""
    log_startup_banner()
    log_system_info()
    
    logger.info("\n" + "📋 СТАТИСТИКА ЛОГОВ:")
    stats = get_log_stats()
    for line in stats.split('\n'):
        logger.info(f"   {line}")
    
    # Показываем следующие шаги
    logger.info("\n" + "🎯 ОСНОВНЫЕ КОМАНДЫ:")
    logger.info("   python main.py --test        # Тестирование компонентов")
    logger.info("   python main.py --start       # Запуск планировщика")
    logger.info("   python main.py --status      # Статус системы")
    
    logger.info("\n" + "🛠️ КОМАНДЫ НОВОЙ АРХИТЕКТУРЫ:")
    logger.info("   python main.py --collect        # Ручной сбор новостей")
    logger.info("   python main.py --publish-next   # Публикация следующей новости")
    logger.info("   python main.py --force-publish N # Публикация приоритет N (1-5)")
    logger.info("   python main.py --test-publish-all # 🧪 ТЕСТ: Все новости подряд")
    
    logger.info("\n" + "🔄 LEGACY КОМАНДЫ:")
    logger.info("   python main.py --run         # Ручной запуск (старый режим)")
    logger.info("   python main.py --info        # Показать эту информацию")


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
    group.add_argument('--start', action='store_true',
                      help='Запустить планировщик (основной режим)')
    group.add_argument('--status', action='store_true',
                      help='Показать статус системы')
    
    # Новые команды архитектуры
    group.add_argument('--collect', action='store_true',
                      help='Ручной сбор новостей')
    group.add_argument('--publish-next', action='store_true',
                      help='Публикация следующей новости')
    group.add_argument('--force-publish', type=int, metavar='N',
                      help='Принудительная публикация приоритет N (1-5)')
    group.add_argument('--test-publish-all', action='store_true',
                      help='🧪 ТЕСТ: Опубликовать все новости подряд с интервалом 6 сек')
    
    # Legacy команды
    group.add_argument('--run', action='store_true',
                      help='Запустить задачу вручную (legacy)')
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
            
        elif args.start:
            success = scheduler_mode()
            sys.exit(0 if success else 1)
            
        elif args.status:
            status_mode()
            sys.exit(0)
            
        # Новые команды архитектуры
        elif args.collect:
            collect_news_mode()
            sys.exit(0)
            
        elif getattr(args, 'publish_next', False):
            publish_next_mode()
            sys.exit(0)
            
        elif args.force_publish:
            if args.force_publish < 1 or args.force_publish > 7:
                logger.error("❌ Приоритет должен быть от 1 до 7")
                sys.exit(1)
            force_publish_mode(args.force_publish)
            sys.exit(0)
            
        elif getattr(args, 'test_publish_all', False):
            test_publish_all_mode()
            sys.exit(0)
            
        # Legacy команды
        elif args.run:
            manual_run()
            sys.exit(0)
            
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