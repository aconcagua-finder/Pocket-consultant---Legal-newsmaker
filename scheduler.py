import schedule
import time
from datetime import datetime
from typing import Optional
from loguru import logger

from perplexity_client import PerplexityClient
from telegram_client import TelegramClient
from openai_client import OpenAIClient
from news_scheduler import NewsmakerScheduler as NewNewsmakerScheduler
import config


class LegacyNewsmakerScheduler:
    """LEGACY: Старый планировщик для автоматического получения и отправки законодательных новостей"""
    
    def __init__(self):
        self.perplexity_client = PerplexityClient()
        self.telegram_client = TelegramClient()
        self.openai_client = OpenAIClient()
        self.is_running = False
        
        # Настройки повторных попыток
        self.max_retries = 3
        self.retry_delay = 30  # 30 секунд между попытками
    
    def _log_job_start(self):
        """Логирует начало выполнения задачи"""
        now = datetime.now()
        logger.info("=" * 50)
        logger.info(f"🚀 Запуск ежедневной задачи: {now.strftime('%d.%m.%Y %H:%M:%S')}")
        logger.info("=" * 50)
    
    def _log_job_end(self, success: bool):
        """Логирует завершение выполнения задачи"""
        now = datetime.now()
        status = "✅ УСПЕШНО" if success else "❌ ОШИБКА"
        logger.info("=" * 50)
        logger.info(f"{status} Задача завершена: {now.strftime('%d.%m.%Y %H:%M:%S')}")
        logger.info("=" * 50)
    
    def _get_legal_updates_with_retry(self) -> Optional[dict]:
        """
        Получает законодательные обновления с повторными попытками
        
        Returns:
            dict: Полученные обновления с источниками или None при ошибке
        """
        for attempt in range(1, self.max_retries + 1):
            logger.info(f"Попытка получения обновлений #{attempt}/{self.max_retries}")
            
            try:
                updates = self.perplexity_client.get_legal_updates()
                
                if updates:
                    logger.info("Успешно получены законодательные обновления")
                    return updates
                else:
                    logger.warning(f"Попытка #{attempt} неудачна - пустой ответ от API")
                    
            except Exception as e:
                logger.error(f"Ошибка при попытке #{attempt}: {e}")
            
            # Ждём перед следующей попыткой (кроме последней)
            if attempt < self.max_retries:
                logger.info(f"Ожидание {self.retry_delay} секунд перед следующей попыткой...")
                time.sleep(self.retry_delay)
        
        logger.error("Все попытки получения обновлений исчерпаны")
        return None
    
    def _send_to_telegram_with_retry(self, data: dict) -> bool:
        """
        Отправляет сообщение в Telegram с повторными попытками
        
        Args:
            data: Данные с контентом и источниками для отправки
            
        Returns:
            bool: True если отправка успешна
        """
        for attempt in range(1, self.max_retries + 1):
            logger.info(f"Попытка отправки в Telegram #{attempt}/{self.max_retries}")
            
            try:
                success = self.telegram_client.send_legal_update(data)
                
                if success:
                    logger.info("Сообщение успешно отправлено в Telegram")
                    return True
                else:
                    logger.warning(f"Попытка отправки #{attempt} неудачна")
                    
            except Exception as e:
                logger.error(f"Ошибка при отправке попытка #{attempt}: {e}")
            
            # Ждём перед следующей попыткой (кроме последней)
            if attempt < self.max_retries:
                logger.info(f"Ожидание {self.retry_delay} секунд перед следующей попыткой...")
                time.sleep(self.retry_delay)
        
        logger.error("Все попытки отправки в Telegram исчерпаны")
        return False
    
    def _send_to_telegram_with_comic_retry(self, data: dict, image_bytes: bytes) -> bool:
        """
        Отправляет сообщение с комиксом в Telegram с повторными попытками
        
        Args:
            data: Данные с контентом и источниками для отправки
            image_bytes: Данные изображения комикса
            
        Returns:
            bool: True если отправка успешна
        """
        for attempt in range(1, self.max_retries + 1):
            logger.info(f"Попытка отправки с комиксом в Telegram #{attempt}/{self.max_retries}")
            
            try:
                success = self.telegram_client.send_legal_update_with_comic(data, image_bytes)
                
                if success:
                    logger.info("Сообщение с комиксом успешно отправлено в Telegram")
                    return True
                else:
                    logger.warning(f"Попытка отправки с комиксом #{attempt} неудачна")
                    
            except Exception as e:
                logger.error(f"Ошибка при отправке с комиксом попытка #{attempt}: {e}")
            
            # Ждём перед следующей попыткой (кроме последней)
            if attempt < self.max_retries:
                logger.info(f"Ожидание {self.retry_delay} секунд перед следующей попыткой...")
                time.sleep(self.retry_delay)
        
        logger.error("Все попытки отправки с комиксом в Telegram исчерпаны")
        return False
    
    def run_daily_job(self):
        """Выполняет основную ежедневную задачу"""
        self._log_job_start()
        
        try:
            # Шаг 1: Получаем обновления от Perplexity
            logger.info("📡 Шаг 1: Получение законодательных обновлений...")
            updates = self._get_legal_updates_with_retry()
            
            if not updates:
                logger.error("Не удалось получить обновления от Perplexity API")
                self._log_job_end(False)
                return
            
            content = updates.get('content', '')
            sources = updates.get('sources', [])
            logger.info(f"Получен контент длиной {len(content)} символов, источников: {len(sources)}")
            
            # Шаг 2: Генерируем комикс
            logger.info("🎨 Шаг 2: Генерация комикса...")
            comic_image = self.openai_client.generate_comic_image(content)
            
            # Шаг 3: Отправляем в Telegram
            logger.info("📱 Шаг 3: Отправка в Telegram канал...")
            if comic_image:
                logger.info("Отправляю с комиксом")
                success = self._send_to_telegram_with_comic_retry(updates, comic_image)
            else:
                logger.warning("Комикс не сгенерирован, отправляю только текст")
                success = self._send_to_telegram_with_retry(updates)
            
            if success:
                logger.info("🎉 Ежедневная задача выполнена успешно!")
                self._log_job_end(True)
            else:
                logger.error("Не удалось отправить сообщение в Telegram")
                self._log_job_end(False)
                
        except Exception as e:
            logger.error(f"Критическая ошибка при выполнении ежедневной задачи: {e}")
            self._log_job_end(False)
    
    def test_components(self) -> bool:
        """
        Тестирует все компоненты системы
        
        Returns:
            bool: True если все компоненты работают
        """
        logger.info("🔧 Тестирование компонентов системы...")
        
        # Тест Perplexity API
        logger.info("Тестирование Perplexity API...")
        perplexity_ok = self.perplexity_client.test_connection()
        
        if perplexity_ok:
            logger.info("✅ Perplexity API работает")
        else:
            logger.error("❌ Perplexity API недоступен")
        
        # Тест Telegram API (асинхронный)
        logger.info("Тестирование Telegram API...")
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            telegram_ok = loop.run_until_complete(self.telegram_client.test_connection())
            loop.close()
            
            if telegram_ok:
                logger.info("✅ Telegram API работает")
            else:
                logger.error("❌ Telegram API недоступен")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при тестировании Telegram: {e}")
            telegram_ok = False
        
        # Общий результат
        all_ok = perplexity_ok and telegram_ok
        
        if all_ok:
            logger.info("🎉 Все компоненты работают корректно!")
        else:
            logger.warning("⚠️ Некоторые компоненты требуют внимания")
        
        return all_ok
    
    def setup_schedule(self):
        """Настраивает расписание выполнения задач"""
        # Очищаем существующие задачи
        schedule.clear()
        
        # Планируем запуск каждые 3 часа
        schedule.every(config.HOURLY_INTERVAL).hours.do(self.run_daily_job)
        
        logger.info(f"📅 Задача запланирована каждые {config.HOURLY_INTERVAL} часа")
        logger.info(f"⏰ Следующий запуск: {schedule.next_run()}")
    
    def run_once_now(self):
        """Запускает задачу немедленно (для тестирования)"""
        logger.info("🚀 Ручной запуск задачи...")
        self.run_daily_job()
    
    def start_scheduler(self):
        """Запускает планировщик в бесконечном цикле"""
        if self.is_running:
            logger.warning("Планировщик уже запущен")
            return
        
        self.setup_schedule()
        self.is_running = True
        
        logger.info("🎯 Планировщик запущен и ожидает выполнения задач...")
        logger.info("Для остановки нажмите Ctrl+C")
        
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(60)  # Проверяем каждую минуту
                
        except KeyboardInterrupt:
            logger.info("⏹️ Получен сигнал остановки")
            self.stop_scheduler()
        except Exception as e:
            logger.error(f"Критическая ошибка планировщика: {e}")
            self.stop_scheduler()
    
    def stop_scheduler(self):
        """Останавливает планировщик"""
        self.is_running = False
        schedule.clear()
        logger.info("⏹️ Планировщик остановлен")


# =============================================================================
# НОВАЯ АРХИТЕКТУРА - Wrapper для совместимости
# =============================================================================

class NewsmakerSchedulerWrapper:
    """
    Wrapper для новой архитектуры планировщика
    Обеспечивает совместимость с существующим интерфейсом
    """
    
    def __init__(self, use_new_architecture: bool = True):
        self.use_new_architecture = use_new_architecture
        
        if use_new_architecture:
            logger.info("🆕 Используется новая архитектура планировщика")
            self.scheduler = NewNewsmakerScheduler()
        else:
            logger.info("🔄 Используется legacy архитектура планировщика")
            self.scheduler = LegacyNewsmakerScheduler()
    
    def test_components(self) -> bool:
        """Тестирует компоненты системы"""
        return self.scheduler.test_components()
    
    def start_scheduler(self):
        """Запускает планировщик"""
        if self.use_new_architecture:
            logger.info("🚀 Запуск новой системы сбора и публикации")
            logger.info("📋 Режим: сбор утром + публикации по расписанию")
        
        self.scheduler.start_scheduler()
    
    def run_once_now(self):
        """Запускает задачу один раз"""
        if self.use_new_architecture:
            logger.info("🛠️ Ручной запуск новой системы")
            # В новой архитектуре можем выбрать что запускать
            self.scheduler.run_manual_publication()
        else:
            self.scheduler.run_once_now()
    
    def stop_scheduler(self):
        """Останавливает планировщик"""
        self.scheduler.stop_scheduler()


# Для обратной совместимости экспортируем wrapper как основной класс
NewsmakerScheduler = NewsmakerSchedulerWrapper 