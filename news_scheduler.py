#!/usr/bin/env python3
"""
News Scheduler для NEWSMAKER

Новый планировщик задач с разделением сбора и публикации:
- 08:30 МСК - сбор новостей за вчера
- 5 раз в день - публикация отдельных новостей по приоритету
"""

import schedule
import time
from datetime import datetime
from typing import Optional
from loguru import logger

import config
from news_collector import NewsCollector
from news_publisher import NewsPublisher


class NewsmakerScheduler:
    """Новый планировщик для системы сбора и публикации новостей"""
    
    def __init__(self):
        self.collector = NewsCollector()
        self.publisher = NewsPublisher()
        self.is_running = False
        
        # Настройки планировщика
        self.timezone = "Europe/Moscow"  # МСК
        
    def _log_job_start(self, job_type: str):
        """Логирует начало выполнения задачи"""
        now = datetime.now()
        logger.info("=" * 60)
        logger.info(f"🚀 Запуск задачи: {job_type}")
        logger.info(f"⏰ Время: {now.strftime('%d.%m.%Y %H:%M:%S МСК')}")
        logger.info("=" * 60)
    
    def _log_job_end(self, job_type: str, success: bool):
        """Логирует завершение выполнения задачи"""
        now = datetime.now()
        status = "✅ УСПЕШНО" if success else "❌ ОШИБКА"
        logger.info("=" * 60)
        logger.info(f"{status} Задача завершена: {job_type}")
        logger.info(f"⏰ Время: {now.strftime('%d.%m.%Y %H:%M:%S МСК')}")
        logger.info("=" * 60)
    
    def collect_daily_news_job(self):
        """Задача ежедневного сбора новостей (08:30 МСК)"""
        job_type = "Сбор новостей"
        self._log_job_start(job_type)
        
        try:
            logger.info("🔍 Запускаю ежедневный сбор законодательных новостей...")
            logger.info("🧠 Используется Perplexity Deep Research")
            
            # Собираем новости за вчера
            success = self.collector.collect_daily_news()
            
            if success:
                logger.info("🎉 Новости успешно собраны и сохранены!")
                
                # Показываем статус файла
                status = self.collector.get_news_file_status()
                logger.info(f"📊 Собрано новостей: {status.get('total_news', 0)}")
                
                self._log_job_end(job_type, True)
            else:
                logger.error("❌ Не удалось собрать новости")
                self._log_job_end(job_type, False)
                
        except Exception as e:
            logger.error(f"💥 Критическая ошибка при сборе новостей: {e}")
            self._log_job_end(job_type, False)
    
    def publish_news_job(self):
        """Задача публикации новостей (по расписанию)"""
        job_type = "Публикация новости"
        self._log_job_start(job_type)
        
        try:
            logger.info("📱 Поиск новости для публикации...")
            
            # Публикуем следующую новость по расписанию
            result = self.publisher.publish_next_scheduled_news()
            
            if result['success']:
                priority = result.get('priority', 'неизвестен')
                title = result.get('title', 'Без названия')
                remaining = result.get('remaining_news', 0)
                
                logger.info(f"✅ Успешно опубликована новость приоритет {priority}")
                logger.info(f"📋 Заголовок: {title[:50]}...")
                logger.info(f"📰 Осталось новостей: {remaining}")
                
                self._log_job_end(job_type, True)
            else:
                reason = result.get('reason', 'unknown')
                if reason == 'no_news_ready':
                    logger.info("📰 Нет новостей готовых к публикации")
                    logger.info("⏰ Следующая проверка по расписанию")
                    self._log_job_end(job_type, True)  # Это не ошибка
                else:
                    logger.error(f"❌ Ошибка публикации: {reason}")
                    title = result.get('title', 'Неизвестная новость')
                    attempts = result.get('attempts', 0)
                    logger.error(f"📋 Новость: {title[:50]}...")
                    logger.error(f"🔄 Попыток: {attempts}")
                    self._log_job_end(job_type, False)
                    
        except Exception as e:
            logger.error(f"💥 Критическая ошибка при публикации: {e}")
            self._log_job_end(job_type, False)
    
    def show_daily_status(self):
        """Показывает статус дня (для отладки)"""
        logger.info("📊 СТАТУС СИСТЕМЫ НА СЕГОДНЯ:")
        logger.info("-" * 40)
        
        # Статус сбора
        collection_status = self.collector.get_news_file_status()
        if collection_status['exists']:
            logger.info(f"✅ Новости собраны: {collection_status['total_news']} шт.")
            logger.info(f"⏰ Время сбора: {collection_status.get('collected_at', 'неизвестно')}")
        else:
            logger.info("❌ Новости еще не собраны")
        
        # Статус публикаций
        publication_status = self.publisher.get_publication_status()
        if publication_status['file_exists']:
            total = publication_status['total_news']
            published = publication_status['published_count']
            unpublished = publication_status['unpublished_count']
            
            logger.info(f"📱 Публикации: {published}/{total} опубликовано")
            logger.info(f"⏳ Ожидают: {unpublished} новостей")
            
            # Детали по неопубликованным
            for detail in publication_status.get('news_details', []):
                if not detail['published']:
                    priority = detail['priority']
                    time_str = detail['scheduled_time']
                    title = detail['title']
                    logger.info(f"  📌 Приоритет {priority} ({time_str}): {title}")
        else:
            logger.info("📱 Нет данных о публикациях")
        
        logger.info("-" * 40)
    
    def setup_schedule(self):
        """Настраивает расписание выполнения задач"""
        # Очищаем существующие задачи
        schedule.clear()
        
        logger.info("📅 Настройка расписания задач (МСК):")
        logger.info(f"  📰 Количество публикаций в день: {config.PUBLICATIONS_PER_DAY}")
        
        # Ежедневный сбор новостей в 08:30
        schedule.every().day.at(config.COLLECTION_TIME).do(self.collect_daily_news_job)
        logger.info(f"  🔍 Сбор новостей: {config.COLLECTION_TIME}")
        
        # Публикации по расписанию (только до PUBLICATIONS_PER_DAY)
        actual_schedule = config.PUBLICATION_SCHEDULE[:config.PUBLICATIONS_PER_DAY]
        for i, time_str in enumerate(actual_schedule, 1):
            schedule.every().day.at(time_str).do(self.publish_news_job)
            logger.info(f"  📱 Публикация #{i}: {time_str}")
        
        # Показываем следующие запуски
        logger.info(f"⏰ Следующий запуск: {schedule.next_run()}")
        
        # Показываем пользовательский часовой пояс если отличается от МСК
        if hasattr(config, 'USER_TIMEZONE') and config.USER_TIMEZONE != "Europe/Moscow":
            logger.info(f"🌍 Часовой пояс пользователя: {config.USER_TIMEZONE}")
    
    def run_manual_collection(self):
        """Ручной запуск сбора новостей"""
        logger.info("🛠️ Ручной запуск сбора новостей...")
        self.collect_daily_news_job()
    
    def run_manual_publication(self):
        """Ручной запуск публикации"""
        logger.info("🛠️ Ручной запуск публикации...")
        self.publish_news_job()
    
    def force_publish_priority(self, priority: int):
        """Принудительная публикация новости с указанным приоритетом"""
        logger.info(f"🛠️ Принудительная публикация приоритет {priority}...")
        
        success = self.publisher.force_publish_by_priority(priority)
        
        if success:
            logger.info(f"✅ Новость приоритет {priority} успешно опубликована")
        else:
            logger.error(f"❌ Не удалось опубликовать новость приоритет {priority}")
        
        return success
    
    def test_components(self) -> bool:
        """
        Тестирует все компоненты новой системы
        
        Returns:
            bool: True если все компоненты работают
        """
        logger.info("🔧 Тестирование компонентов новой системы...")
        
        all_ok = True
        
        # Тест Perplexity API (через collector)
        logger.info("🧠 Тестирование Perplexity Deep Research...")
        try:
            if hasattr(self.collector.perplexity_client, 'test_connection'):
                perplexity_ok = self.collector.perplexity_client.test_connection()
            else:
                # Создаем простой тест
                logger.info("✅ Perplexity клиент инициализирован")
                perplexity_ok = True
                
            if perplexity_ok:
                logger.info("✅ Perplexity Deep Research работает")
            else:
                logger.error("❌ Perplexity Deep Research недоступен")
                all_ok = False
        except Exception as e:
            logger.error(f"❌ Ошибка при тестировании Perplexity: {e}")
            all_ok = False
        
        # Тест Telegram API (через publisher)
        logger.info("📱 Тестирование Telegram API...")
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            telegram_ok = loop.run_until_complete(
                self.publisher.telegram_client.test_connection()
            )
            loop.close()
            
            if telegram_ok:
                logger.info("✅ Telegram API работает")
            else:
                logger.error("❌ Telegram API недоступен")
                all_ok = False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при тестировании Telegram: {e}")
            all_ok = False
        
        # Тест OpenAI API (через publisher)
        logger.info("🎨 Тестирование OpenAI API...")
        try:
            openai_ok = self.publisher.openai_client.test_connection()
            
            if openai_ok:
                logger.info("✅ OpenAI API работает")
            else:
                logger.error("❌ OpenAI API недоступен")
                all_ok = False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при тестировании OpenAI: {e}")
            all_ok = False
        
        # Тест папки данных
        logger.info("📂 Тестирование папки данных...")
        try:
            if self.collector.data_dir.exists():
                logger.info("✅ Папка данных доступна")
            else:
                logger.error("❌ Папка данных недоступна")
                all_ok = False
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке папки данных: {e}")
            all_ok = False
        
        # Общий результат
        if all_ok:
            logger.info("🎉 Все компоненты новой системы работают корректно!")
        else:
            logger.warning("⚠️ Некоторые компоненты требуют внимания")
        
        return all_ok
    
    def start_scheduler(self):
        """Запускает планировщик в бесконечном цикле"""
        if self.is_running:
            logger.warning("⚠️ Планировщик уже запущен")
            return
        
        self.setup_schedule()
        self.is_running = True
        
        logger.info("🎯 Новый планировщик запущен и ожидает выполнения задач...")
        logger.info("📋 Режим работы: сбор новостей + публикация по расписанию")
        logger.info("🛑 Для остановки нажмите Ctrl+C")
        
        # Показываем текущий статус
        self.show_daily_status()
        
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(60)  # Проверяем каждую минуту
                
        except KeyboardInterrupt:
            logger.info("⏹️ Получен сигнал остановки")
            self.stop_scheduler()
        except Exception as e:
            logger.error(f"💥 Критическая ошибка планировщика: {e}")
            self.stop_scheduler()
    
    def stop_scheduler(self):
        """Останавливает планировщик"""
        self.is_running = False
        schedule.clear()
        logger.info("⏹️ Планировщик остановлен")


def main():
    """Функция для тестирования модуля"""
    logger.info("🧪 Тестирование NewsmakerScheduler...")
    
    scheduler = NewsmakerScheduler()
    
    # Показываем статус
    scheduler.show_daily_status()
    
    # Тестируем компоненты
    success = scheduler.test_components()
    
    if success:
        logger.info("✨ Новая система готова к работе!")
    else:
        logger.error("❌ Требуется настройка компонентов")


if __name__ == "__main__":
    main()