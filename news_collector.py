#!/usr/bin/env python3
"""
News Collector для NEWSMAKER

Модуль для ежедневного сбора законодательных новостей через Perplexity Deep Research
и сохранения их в структурированном виде для последующей публикации.
"""

import json
import os
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
    
    def _generate_images_for_news(self, news_list: List[Dict], target_date: datetime) -> List[Dict]:
        """
        Генерирует изображения для всех новостей и добавляет информацию в данные новостей
        
        Args:
            news_list: Список новостей
            target_date: Дата для названия папки изображений
            
        Returns:
            List[Dict]: Обновленный список новостей с информацией об изображениях
        """
        if not self.openai_client or not self.openai_client.client:
            logger.warning("🎨 OpenAI клиент недоступен, пропускаем генерацию изображений")
            return news_list
        
        logger.info("🎨 Начинаем генерацию изображений для всех новостей...")
        
        updated_news_list = []
        total_news = len(news_list)
        
        for i, news_item in enumerate(news_list, 1):
            news_id = news_item.get('id', f'news_{i}')
            title = news_item.get('title', 'Без названия')
            content = news_item.get('content', '')
            
            logger.info(f"🖼️ Генерация изображения {i}/{total_news}: {title[:50]}...")
            
            try:
                # Генерируем изображение
                image_bytes = self.openai_client.generate_comic_image(content)
                
                if image_bytes:
                    # Сохраняем изображение в файл
                    image_path = self._get_image_file_path(target_date, news_id)
                    
                    with open(image_path, 'wb') as f:
                        f.write(image_bytes)
                    
                    # Относительный путь для JSON
                    relative_image_path = str(image_path.relative_to(Path.cwd()))
                    
                    logger.info(f"✅ Изображение сохранено: {image_path.name}")
                    
                    # Добавляем информацию об изображении в новость
                    news_item.update({
                        'image_path': relative_image_path,
                        'image_generated': True,
                        'image_size': len(image_bytes)
                    })
                else:
                    logger.warning(f"⚠️ Не удалось сгенерировать изображение для: {title[:30]}...")
                    news_item.update({
                        'image_path': None,
                        'image_generated': False,
                        'image_error': 'Генерация не удалась'
                    })
                    
            except Exception as e:
                logger.error(f"💥 Ошибка при генерации изображения для {title[:30]}...: {e}")
                news_item.update({
                    'image_path': None,
                    'image_generated': False,
                    'image_error': str(e)
                })
            
            updated_news_list.append(news_item)
        
        successful_images = sum(1 for news in updated_news_list if news.get('image_generated', False))
        logger.info(f"🎉 Генерация завершена: {successful_images}/{total_news} изображений успешно")
        
        return updated_news_list
    
    def _cleanup_old_files(self):
        """Удаляет старые файлы новостей"""
        try:
            cutoff_date = datetime.now() - timedelta(days=config.MAX_NEWS_FILES)
            
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
                    
        except Exception as e:
            logger.error(f"Ошибка при очистке старых файлов: {e}")
    
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
            
            import requests
            response = requests.post(
                config.PERPLEXITY_API_URL,
                headers={
                    "Authorization": f"Bearer {config.PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=config.REQUEST_TIMEOUT
            )
            
            response.raise_for_status()
            
            data = response.json()
            raw_content = data['choices'][0]['message']['content']
            
            logger.info("✅ Успешно получен ответ от Perplexity Deep Research")
            logger.info(f"📏 Размер ответа: {len(raw_content)} символов")
            
            return raw_content
            
        except requests.exceptions.Timeout:
            logger.error("⏰ Превышен таймаут запроса к Perplexity API")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"🌐 Ошибка при запросе к Perplexity API: {e}")
            return None
        except Exception as e:
            logger.error(f"💥 Неожиданная ошибка при сборе новостей: {e}")
            return None
    
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
            current_time = datetime.now()
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
            return []
    
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
            
            news_data = {
                'date': date.strftime('%Y-%m-%d'),
                'collected_at': datetime.now().isoformat(),
                'total_news': len(news_list),
                'news': news_list
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(news_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 Новости сохранены в файл: {file_path.name}")
            logger.info(f"📊 Статистика: {len(news_list)} новостей")
            
            # Выводим краткую сводку
            for news in news_list:
                priority = news.get('priority', 0)
                title = news.get('title', 'Без названия')[:50]
                time = news.get('scheduled_time', 'Не назначено')
                logger.info(f"  📌 Приоритет {priority} ({time}): {title}...")
            
            return True
            
        except Exception as e:
            logger.error(f"💾 Ошибка при сохранении файла: {e}")
            return False
    
    def collect_daily_news(self, target_date: Optional[datetime] = None) -> bool:
        """
        Выполняет полный цикл сбора новостей за указанную дату
        
        Args:
            target_date: Дата для сбора новостей (по умолчанию вчера)
            
        Returns:
            bool: True если сбор прошел успешно
        """
        if target_date is None:
            target_date = datetime.now() - timedelta(days=1)  # Вчера
        
        logger.info("=" * 60)
        logger.info(f"🚀 Запуск сбора новостей за {target_date.strftime('%d.%m.%Y')}")
        logger.info("=" * 60)
        
        # Проверяем, не собирали ли уже новости за эту дату
        file_path = self._get_news_file_path(target_date)
        if file_path.exists():
            logger.warning(f"⚠️ Файл новостей уже существует: {file_path.name}")
            logger.info("Для пересбора удалите файл вручную")
            return False
        
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
                    import time
                    time.sleep(self.retry_delay)
                continue
            
            # Обрабатываем данные
            news_list = self._process_raw_content(raw_content)
            if not news_list:
                logger.warning("📰 Не удалось извлечь новости из ответа")
                if attempt < self.max_retries:
                    logger.info(f"⏱️ Ожидание {self.retry_delay} секунд перед следующей попыткой...")
                    import time
                    time.sleep(self.retry_delay)
                continue
            
            # Генерируем изображения для всех новостей
            logger.info("🎨 Переходим к генерации изображений...")
            news_list_with_images = self._generate_images_for_news(news_list, target_date)
            
            # Сохраняем в файл
            if self._save_news_to_file(news_list_with_images, target_date):
                logger.info("🎉 Сбор новостей завершен успешно!")
                logger.info("=" * 60)
                return True
            else:
                logger.error("💾 Ошибка при сохранении файла")
                if attempt < self.max_retries:
                    import time
                    time.sleep(self.retry_delay)
                continue
        
        logger.error("❌ Все попытки сбора исчерпаны")
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
            date = datetime.now() - timedelta(days=1)
        
        file_path = self._get_news_file_path(date)
        
        if not file_path.exists():
            return {
                'exists': False,
                'date': date.strftime('%Y-%m-%d'),
                'file_path': str(file_path)
            }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return {
                'exists': True,
                'date': date.strftime('%Y-%m-%d'),
                'file_path': str(file_path),
                'collected_at': data.get('collected_at'),
                'total_news': data.get('total_news', 0),
                'news_count': len(data.get('news', [])),
                'published_count': sum(1 for news in data.get('news', []) if news.get('published', False))
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
    else:
        logger.error("❌ Тест не прошел")


if __name__ == "__main__":
    main()