#!/usr/bin/env python3
"""
News Collector для NEWSMAKER

Модуль для ежедневного сбора законодательных новостей через Perplexity Deep Research
и сохранения их в структурированном виде для последующей публикации.
"""

import json
import os
import asyncio
import requests  # Добавлен отсутствующий импорт
import time  # Добавлен импорт time в начало
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from loguru import logger

import config
from perplexity_client import PerplexityClient
from openai_client import OpenAIClient
from prompts import (
    get_perplexity_daily_collection_prompt,
    get_perplexity_system_prompt,
    parse_collected_news,
    PromptConfig
)
from retry_handler import retry_with_exponential_backoff, PerplexityRetryHandler
from cache_manager import cache_news_data, cache_api_response, cache_manager
from async_handler import batch_generate_images, run_async
from monitoring import monitor_performance, metrics_collector
from file_utils import safe_json_write, safe_json_read, create_backup, FileLock
from timezone_utils import now_msk, yesterday_msk, format_date_russian


class NewsCollector:
    """Коллектор новостей для ежедневного сбора законодательных изменений"""
    
    def __init__(self):
        self.perplexity_client = PerplexityClient()
        self.openai_client = OpenAIClient()
        self.data_dir = Path(config.DATA_DIR)
        self.data_dir.mkdir(exist_ok=True)
        
        # Создаем папку для изображений
        self.images_dir = self.data_dir / "images"
        self.images_dir.mkdir(exist_ok=True)
        
        # Инициализируем retry handler
        self.perplexity_retry = PerplexityRetryHandler()
        
        # Настройки для сбора
        self.max_retries = 3
        self.retry_delay = 60  # 1 минута между попытками
    
    def _get_news_file_path(self, date: datetime) -> Path:
        """
        Получает путь к файлу новостей для указанной даты
        
        Args:
            date: Дата для файла новостей
            
        Returns:
            Path: Путь к файлу
        """
        date_str = date.strftime('%Y-%m-%d')
        filename = config.NEWS_FILE_PATTERN.format(date=date_str)
        return self.data_dir / filename
    
    def _get_image_file_path(self, date: datetime, news_id: str) -> Path:
        """
        Получает путь к файлу изображения для новости
        
        Args:
            date: Дата новости
            news_id: ID новости
            
        Returns:
            Path: Путь к файлу изображения
        """
        date_str = date.strftime('%Y-%m-%d')
        date_images_dir = self.images_dir / date_str
        date_images_dir.mkdir(exist_ok=True)
        return date_images_dir / f"{news_id}.png"
    
    @monitor_performance("image_generation_batch")
    async def _generate_images_async(self, news_list: List[Dict], target_date: datetime) -> List[Dict]:
        """
        Асинхронно генерирует изображения для всех новостей параллельно
        
        Args:
            news_list: Список новостей
            target_date: Дата для названия папки изображений
            
        Returns:
            List[Dict]: Обновленный список новостей с информацией об изображениях
        """
        logger.info("🎨 Начинаем параллельную генерацию изображений...")
        
        # Подготавливаем промпты для всех новостей
        prompts = []
        for news_item in news_list:
            content = news_item.get('content', '')
            prompts.append(content)
        
        # Генерируем изображения параллельно (максимум 3 одновременно)
        images = await batch_generate_images(prompts, max_concurrent=3)
        
        # Обновляем новости с изображениями
        updated_news_list = []
        successful_images = 0
        
        for i, (news_item, image_bytes) in enumerate(zip(news_list, images), 1):
            news_id = news_item.get('id', f'news_{i}')
            title = news_item.get('title', 'Без названия')
            
            if image_bytes:
                try:
                    # Сохраняем изображение
                    image_path = self._get_image_file_path(target_date, news_id)
                    
                    with FileLock(image_path):
                        with open(image_path, 'wb') as f:
                            f.write(image_bytes)
                    
                    # Относительный путь для JSON
                    relative_image_path = str(image_path.relative_to(Path.cwd()))
                    
                    logger.info(f"✅ Изображение {i}/{len(news_list)} сохранено: {image_path.name}")
                    
                    news_item.update({
                        'image_path': relative_image_path,
                        'image_generated': True,
                        'image_size': len(image_bytes)
                    })
                    successful_images += 1
                    
                    # Записываем метрику
                    metrics_collector.counters['image_generation_success'] += 1
                    
                except Exception as e:
                    logger.error(f"💥 Ошибка сохранения изображения {i}: {e}")
                    news_item.update({
                        'image_path': None,
                        'image_generated': False,
                        'image_error': str(e)
                    })
                    metrics_collector.counters['image_generation_failed'] += 1
            else:
                logger.warning(f"⚠️ Не удалось сгенерировать изображение {i}")
                news_item.update({
                    'image_path': None,
                    'image_generated': False,
                    'image_error': 'Генерация не удалась'
                })
                metrics_collector.counters['image_generation_failed'] += 1
            
            updated_news_list.append(news_item)
        
        logger.info(f"🎉 Генерация завершена: {successful_images}/{len(news_list)} изображений успешно")
        
        return updated_news_list
    
    def _generate_images_for_news(self, news_list: List[Dict], target_date: datetime) -> List[Dict]:
        """
        Wrapper для обратной совместимости - вызывает асинхронную версию
        """
        return run_async(self._generate_images_async(news_list, target_date))
    
    def _cleanup_old_files(self):
        """Удаляет старые файлы новостей и очищает кеш"""
        try:
            cutoff_date = now_msk() - timedelta(days=config.MAX_NEWS_FILES)
            
            for file_path in self.data_dir.glob("daily_news_*.json"):
                try:
                    # Извлекаем дату из имени файла
                    date_part = file_path.stem.replace('daily_news_', '')
                    file_date = datetime.strptime(date_part, '%Y-%m-%d')
                    
                    if file_date < cutoff_date:
                        file_path.unlink()
                        logger.info(f"Удален старый файл новостей: {file_path.name}")
                        
                except (ValueError, OSError) as e:
                    logger.warning(f"Ошибка при обработке файла {file_path}: {e}")
            
            # Очищаем старый кеш
            cache_manager.cleanup(max_age_days=7)
                    
        except Exception as e:
            logger.error(f"Ошибка при очистке старых файлов: {e}")
    
    @monitor_performance("news_collection")
    @retry_with_exponential_backoff(max_attempts=3)
    @cache_api_response(ttl=300)  # Кешируем на 5 минут
    def _collect_raw_news(self) -> Optional[str]:
        """
        Собирает сырые новости через Perplexity Deep Research
        
        Returns:
            str: Сырой контент от API или None при ошибке
        """
        try:
            prompt = get_perplexity_daily_collection_prompt()
            
            logger.info("🔍 Запускаю глубокий анализ законодательных изменений...")
            logger.info("📊 Максимальный размер ответа: 8192 токена")
            
            payload = {
                "model": "sonar-deep-research",
                "messages": [
                    {
                        "role": "system",
                        "content": get_perplexity_system_prompt()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "max_tokens": PromptConfig.PERPLEXITY_COLLECTION_MAX_TOKENS,
                "temperature": PromptConfig.PERPLEXITY_TEMPERATURE,
                "top_p": PromptConfig.PERPLEXITY_TOP_P
            }
            
            # Используем retry handler для надежности
            response = self.perplexity_retry.make_request(
                url=config.PERPLEXITY_API_URL,
                headers={
                    "Authorization": f"Bearer {config.PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json"
                },
                json_data=payload,
                timeout=config.REQUEST_TIMEOUT
            )
            
            data = response.json()
            raw_content = data['choices'][0]['message']['content']
            
            logger.info("✅ Успешно получен ответ от Perplexity Deep Research")
            logger.info(f"📏 Размер ответа: {len(raw_content)} символов")
            
            # Записываем метрику
            metrics_collector.counters['news_collection_success'] += 1
            
            return raw_content
            
        except requests.exceptions.Timeout:
            logger.error("⏰ Превышен таймаут запроса к Perplexity API")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"🌐 Ошибка при запросе к Perplexity API: {e}")
            return None
        except Exception as e:
            logger.error(f"💥 Неожиданная ошибка при сборе новостей: {e}")
            metrics_collector.record_error('news_collection', str(e))
            return None
    
    @cache_news_data(ttl=86400)  # Кешируем на 24 часа
    def _process_raw_content(self, raw_content: str) -> List[Dict]:
        """
        Обрабатывает сырой контент и извлекает структурированные новости
        
        Args:
            raw_content: Сырой ответ от Deep Research
            
        Returns:
            List[Dict]: Список обработанных новостей
        """
        try:
            # Очищаем от тегов рассуждений
            if hasattr(self.perplexity_client, '_clean_deep_research_content'):
                cleaned_content = self.perplexity_client._clean_deep_research_content(raw_content)
            else:
                import re
                cleaned_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL)
                cleaned_content = re.sub(r'</?think>', '', cleaned_content)
            
            logger.debug(f"📋 Очищенный контент:\n{cleaned_content[:500]}...")
            
            # Парсим новости
            news_list = parse_collected_news(cleaned_content)
            
            logger.info(f"📰 Извлечено {len(news_list)} новостей")
            
            # Добавляем метаданные к каждой новости
            current_time = now_msk()
            schedule = config.PUBLICATION_SCHEDULE
            
            for i, news_item in enumerate(news_list):
                # Назначаем время публикации
                if i < len(schedule):
                    news_item['scheduled_time'] = schedule[i]
                else:
                    # Если новостей больше чем времен в расписании
                    news_item['scheduled_time'] = schedule[-1]  # Последнее время
                
                # Добавляем метаданные
                news_item.update({
                    'id': f"news_{current_time.strftime('%Y%m%d')}_{i+1}",
                    'collected_at': current_time.isoformat(),
                    'published': False,
                    'publication_attempts': 0
                })
            
            return news_list
            
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке контента: {e}")
            metrics_collector.record_error('content_processing', str(e))
            return []
    
    @monitor_performance("save_news_file")
    def _save_news_to_file(self, news_list: List[Dict], date: datetime) -> bool:
        """
        Сохраняет новости в JSON файл
        
        Args:
            news_list: Список новостей для сохранения
            date: Дата для которой сохраняются новости
            
        Returns:
            bool: True если сохранение прошло успешно
        """
        try:
            file_path = self._get_news_file_path(date)
            
            # Создаем резервную копию если файл существует
            if file_path.exists():
                create_backup(file_path)
            
            news_data = {
                'date': date.strftime('%Y-%m-%d'),
                'collected_at': now_msk().isoformat(),
                'total_news': len(news_list),
                'news': news_list
            }
            
            # Сохраняем с блокировкой
            success = safe_json_write(file_path, news_data)
            
            if success:
                logger.info(f"💾 Новости сохранены в файл: {file_path.name}")
                logger.info(f"📊 Статистика: {len(news_list)} новостей")
                
                # Выводим краткую сводку
                for news in news_list:
                    priority = news.get('priority', 0)
                    title = news.get('title', 'Без названия')[:50]
                    time = news.get('scheduled_time', 'Не назначено')
                    logger.info(f"  📌 Приоритет {priority} ({time}): {title}...")
            
            return success
            
        except Exception as e:
            logger.error(f"💾 Ошибка при сохранении файла: {e}")
            metrics_collector.record_error('file_save', str(e))
            return False
    
    @monitor_performance("daily_collection")
    def collect_daily_news(self, target_date: Optional[datetime] = None) -> bool:
        """
        Выполняет полный цикл сбора новостей за указанную дату
        
        Args:
            target_date: Дата для сбора новостей (по умолчанию вчера)
            
        Returns:
            bool: True если сбор прошел успешно
        """
        if target_date is None:
            target_date = yesterday_msk()
        
        logger.info("=" * 60)
        logger.info(f"🚀 Запуск сбора новостей за {format_date_russian(target_date)}")
        logger.info(f"📊 Системное здоровье: {metrics_collector.collect_system_metrics().cpu_percent:.1f}% CPU")
        logger.info("=" * 60)
        
        # Проверяем, не собирали ли уже новости за эту дату
        file_path = self._get_news_file_path(target_date)
        if file_path.exists():
            logger.warning(f"⚠️ Файл новостей уже существует: {file_path.name}")
            
            # Проверяем кеш
            cached_data = safe_json_read(file_path)
            if cached_data and cached_data.get('total_news', 0) > 0:
                logger.info("📦 Используем существующие новости из файла")
                return True
        
        # Очищаем старые файлы
        self._cleanup_old_files()
        
        # Пытаемся собрать новости с повторными попытками
        for attempt in range(1, self.max_retries + 1):
            logger.info(f"🎯 Попытка сбора #{attempt}/{self.max_retries}")
            
            # Собираем сырые данные
            raw_content = self._collect_raw_news()
            if not raw_content:
                if attempt < self.max_retries:
                    logger.info(f"⏱️ Ожидание {self.retry_delay} секунд перед следующей попыткой...")
                    time.sleep(self.retry_delay)
                continue
            
            # Обрабатываем данные
            news_list = self._process_raw_content(raw_content)
            if not news_list:
                logger.warning("📰 Не удалось извлечь новости из ответа")
                if attempt < self.max_retries:
                    logger.info(f"⏱️ Ожидание {self.retry_delay} секунд перед следующей попыткой...")
                    time.sleep(self.retry_delay)
                continue
            
            # Генерируем изображения параллельно для всех новостей
            logger.info("🎨 Переходим к параллельной генерации изображений...")
            news_list_with_images = self._generate_images_for_news(news_list, target_date)
            
            # Сохраняем в файл
            if self._save_news_to_file(news_list_with_images, target_date):
                logger.info("🎉 Сбор новостей завершен успешно!")
                
                # Сохраняем метрики
                metrics_collector.save_metrics()
                
                # Генерируем статистику
                stats = metrics_collector.generate_daily_stats()
                logger.info(f"📊 Статистика дня: {stats.news_collected} новостей собрано")
                
                logger.info("=" * 60)
                return True
            else:
                logger.error("💾 Ошибка при сохранении файла")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                continue
        
        logger.error("❌ Все попытки сбора исчерпаны")
        metrics_collector.counters['news_collection_failed'] += 1
        logger.info("=" * 60)
        return False
    
    def get_news_file_status(self, date: Optional[datetime] = None) -> Dict:
        """
        Получает статус файла новостей за указанную дату
        
        Args:
            date: Дата для проверки (по умолчанию вчера)
            
        Returns:
            Dict: Информация о статусе файла
        """
        if date is None:
            date = yesterday_msk()
        
        file_path = self._get_news_file_path(date)
        
        if not file_path.exists():
            return {
                'exists': False,
                'date': date.strftime('%Y-%m-%d'),
                'file_path': str(file_path)
            }
        
        try:
            data = safe_json_read(file_path)
            
            if data:
                return {
                    'exists': True,
                    'date': date.strftime('%Y-%m-%d'),
                    'file_path': str(file_path),
                    'collected_at': data.get('collected_at'),
                    'total_news': data.get('total_news', 0),
                    'news_count': len(data.get('news', [])),
                    'published_count': sum(1 for news in data.get('news', []) if news.get('published', False))
                }
            else:
                return {
                    'exists': True,
                    'date': date.strftime('%Y-%m-%d'),
                    'file_path': str(file_path),
                    'error': 'Не удалось прочитать файл'
                }
            
        except Exception as e:
            logger.error(f"Ошибка при чтении файла {file_path}: {e}")
            return {
                'exists': True,
                'date': date.strftime('%Y-%m-%d'),
                'file_path': str(file_path),
                'error': str(e)
            }


def main():
    """Функция для тестирования модуля"""
    logger.info("🧪 Тестирование NewsCollector...")
    
    collector = NewsCollector()
    
    # Тестируем сбор новостей
    success = collector.collect_daily_news()
    
    if success:
        # Показываем статус
        status = collector.get_news_file_status()
        logger.info(f"📊 Статус: {status}")
        
        # Показываем метрики
        summary = metrics_collector.get_summary()
        logger.info(f"📈 Метрики: {summary}")
    else:
        logger.error("❌ Тест не прошел")


if __name__ == "__main__":
    main()