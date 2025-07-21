#!/usr/bin/env python3
"""
News Publisher для NEWSMAKER

Модуль для публикации отдельных новостей из сохраненных файлов.
Читает структурированные данные и публикует их в Telegram в нужное время.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from loguru import logger

import config
from telegram_client import TelegramClient
from openai_client import OpenAIClient


class NewsPublisher:
    """Публикатор новостей из сохраненных файлов"""
    
    def __init__(self):
        self.telegram_client = TelegramClient()
        self.openai_client = OpenAIClient()
        self.data_dir = Path(config.DATA_DIR)
        
        # Настройки публикации
        self.max_publication_attempts = 3
        
    def _get_news_file_path(self, date: datetime) -> Path:
        """
        Получает путь к файлу новостей для указанной даты
        
        Args:
            date: Дата файла новостей
            
        Returns:
            Path: Путь к файлу
        """
        date_str = date.strftime('%Y-%m-%d')
        filename = config.NEWS_FILE_PATTERN.format(date=date_str)
        return self.data_dir / filename
    
    def _load_news_file(self, date: datetime) -> Optional[Dict]:
        """
        Загружает файл новостей за указанную дату
        
        Args:
            date: Дата файла для загрузки
            
        Returns:
            Dict: Данные новостей или None при ошибке
        """
        file_path = self._get_news_file_path(date)
        
        if not file_path.exists():
            logger.error(f"📂 Файл новостей не найден: {file_path.name}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.debug(f"📰 Загружен файл: {file_path.name}")
            logger.debug(f"📊 Новостей в файле: {len(data.get('news', []))}")
            
            return data
            
        except Exception as e:
            logger.error(f"💥 Ошибка при загрузке файла {file_path}: {e}")
            return None
    
    def _save_news_file(self, data: Dict, date: datetime) -> bool:
        """
        Сохраняет обновленные данные новостей в файл
        
        Args:
            data: Данные для сохранения
            date: Дата файла
            
        Returns:
            bool: True если сохранение успешно
        """
        file_path = self._get_news_file_path(date)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"💾 Файл обновлен: {file_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"💾 Ошибка при сохранении файла: {e}")
            return False
    
    def _format_news_for_telegram(self, news_item: Dict) -> Dict:
        """
        Форматирует новость для отправки в Telegram
        
        Args:
            news_item: Данные новости
            
        Returns:
            Dict: Отформатированные данные для telegram_client
        """
        title = news_item.get('title', '')
        content = news_item.get('content', '')
        sources = news_item.get('sources', [])
        
        # Очищаем контент от markdown и артефактов Deep Research
        cleaned_content = self._clean_deep_research_formatting(content)
        
        # Проверяем, есть ли уже 📜 в контенте
        if '📜' in cleaned_content:
            # Контент уже содержит заголовок с эмодзи
            formatted_content = cleaned_content
        else:
            # Добавляем заголовок если его нет
            if title.startswith('📜'):
                formatted_content = f"{title}\n\n{cleaned_content}"
            else:
                formatted_content = f"📜 {title}\n\n{cleaned_content}"
        
        return {
            'content': formatted_content,
            'sources': sources
        }
    
    def _clean_deep_research_formatting(self, content: str) -> str:
        """
        Очищает контент от markdown форматирования Deep Research
        
        Args:
            content: Сырой контент с форматированием
            
        Returns:
            str: Очищенный контент
        """
        import re
        
        # Убираем лишние звездочки в заголовках
        content = re.sub(r'\*\*КОММЕНТАРИЙ КАРМАННОГО КОНСУЛЬТАНТА:\*\*', 'КОММЕНТАРИЙ КАРМАННОГО КОНСУЛЬТАНТА:', content)
        
        # Убираем *Ирония:*, *Наблюдение:* и подобные маркеры
        content = re.sub(r'\*[А-Я][а-я]+:\*\s*', '', content)
        
        # Убираем лишние звездочки в конце и начале
        content = re.sub(r'\*\*\s*$', '', content)
        content = re.sub(r'^\*\*\s*', '', content)
        
        # Убираем двойные переносы строк
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        # Убираем trailing пробелы в строках
        content = '\n'.join(line.rstrip() for line in content.split('\n'))
        
        return content.strip()
    
    def _load_image_for_news(self, news_item: Dict) -> Optional[bytes]:
        """
        Загружает готовое изображение для новости из файла
        
        Args:
            news_item: Данные новости с информацией об изображении
            
        Returns:
            bytes: Данные изображения или None если изображение недоступно
        """
        image_path_str = news_item.get('image_path')
        if not image_path_str:
            logger.warning("📷 Путь к изображению не указан в новости")
            return None
        
        if not news_item.get('image_generated', False):
            logger.warning("📷 Изображение не было сгенерировано")
            return None
        
        image_path = Path(image_path_str)
        
        if not image_path.exists():
            logger.error(f"📷 Файл изображения не найден: {image_path}")
            return None
        
        try:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            
            logger.info(f"📷 Изображение загружено: {image_path.name} ({len(image_bytes)} байт)")
            return image_bytes
            
        except Exception as e:
            logger.error(f"📷 Ошибка при загрузке изображения {image_path}: {e}")
            return None
    
    def _update_news_status(self, data: Dict, news_id: str, published: bool, 
                           attempt_count: Optional[int] = None) -> Dict:
        """
        Обновляет статус публикации новости
        
        Args:
            data: Данные файла новостей
            news_id: ID новости для обновления
            published: Статус публикации
            attempt_count: Количество попыток (опционально)
            
        Returns:
            Dict: Обновленные данные
        """
        for news_item in data.get('news', []):
            if news_item.get('id') == news_id:
                news_item['published'] = published
                if published:
                    news_item['published_at'] = datetime.now().isoformat()
                
                if attempt_count is not None:
                    news_item['publication_attempts'] = attempt_count
                    
                break
        
        return data
    
    def get_next_unpublished_news(self, date: Optional[datetime] = None) -> Optional[Dict]:
        """
        Получает следующую неопубликованную новость по расписанию
        
        Args:
            date: Дата для поиска новостей (по умолчанию вчера)
            
        Returns:
            Dict: Данные новости или None если нет подходящих
        """
        if date is None:
            date = datetime.now() - timedelta(days=1)
        
        data = self._load_news_file(date)
        if not data:
            return None
        
        current_time = datetime.now()
        current_time_str = current_time.strftime('%H:%M')
        
        # Ищем новости, которые пора публиковать
        unpublished_news = []
        for news_item in data.get('news', []):
            if not news_item.get('published', False):
                scheduled_time = news_item.get('scheduled_time')
                if scheduled_time and scheduled_time <= current_time_str:
                    unpublished_news.append(news_item)
        
        if not unpublished_news:
            return None
        
        # Сортируем по приоритету и времени
        unpublished_news.sort(key=lambda x: (
            x.get('priority', 999),
            x.get('scheduled_time', '99:99')
        ))
        
        return {
            'file_date': date,
            'news_item': unpublished_news[0],
            'total_unpublished': len(unpublished_news)
        }
    
    def publish_news_item(self, news_data: Dict) -> bool:
        """
        Публикует одну новость в Telegram
        
        Args:
            news_data: Данные новости с метаинформацией
            
        Returns:
            bool: True если публикация успешна
        """
        file_date = news_data['file_date']
        news_item = news_data['news_item']
        news_id = news_item.get('id', 'unknown')
        
        logger.info("=" * 50)
        logger.info(f"📱 Публикация новости: {news_id}")
        logger.info(f"🎯 Приоритет: {news_item.get('priority', 'не указан')}")
        logger.info(f"⏰ Время: {news_item.get('scheduled_time', 'не указано')}")
        logger.info("=" * 50)
        
        # Загружаем актуальные данные файла
        data = self._load_news_file(file_date)
        if not data:
            logger.error("📂 Не удалось загрузить файл новостей")
            return False
        
        # Увеличиваем счетчик попыток
        current_attempts = news_item.get('publication_attempts', 0) + 1
        
        try:
            # Форматируем для Telegram
            telegram_data = self._format_news_for_telegram(news_item)
            
            # Загружаем готовое изображение
            logger.info("📷 Загрузка готового изображения...")
            comic_image = self._load_image_for_news(news_item)
            
            # Публикуем
            logger.info("📱 Отправка в Telegram...")
            if comic_image:
                success = self.telegram_client.send_legal_update_with_comic(
                    telegram_data, comic_image
                )
            else:
                logger.warning("📷 Изображение недоступно, отправляю только текст")
                success = self.telegram_client.send_legal_update(telegram_data)
            
            if success:
                logger.info("✅ Новость успешно опубликована!")
                
                # Обновляем статус в файле
                data = self._update_news_status(data, news_id, True, current_attempts)
                self._save_news_file(data, file_date)
                
                return True
            else:
                logger.error("❌ Ошибка при публикации")
                
                # Обновляем счетчик попыток
                data = self._update_news_status(data, news_id, False, current_attempts)
                self._save_news_file(data, file_date)
                
                return False
                
        except Exception as e:
            logger.error(f"💥 Неожиданная ошибка при публикации: {e}")
            
            # Обновляем счетчик попыток
            data = self._update_news_status(data, news_id, False, current_attempts)
            self._save_news_file(data, file_date)
            
            return False
        
        finally:
            logger.info("=" * 50)
    
    def publish_next_scheduled_news(self) -> Dict:
        """
        Публикует следующую новость по расписанию
        
        Returns:
            Dict: Результат публикации с деталями
        """
        logger.info("🔍 Поиск следующей новости для публикации...")
        
        # Ищем новость для публикации
        news_data = self.get_next_unpublished_news()
        
        if not news_data:
            logger.info("📰 Нет новостей для публикации в данный момент")
            return {
                'success': False,
                'reason': 'no_news_ready',
                'message': 'Нет новостей готовых к публикации'
            }
        
        news_item = news_data['news_item']
        scheduled_time = news_item.get('scheduled_time', 'не указано')
        priority = news_item.get('priority', 'не указан')
        title = news_item.get('title', 'Без названия')
        
        logger.info(f"📰 Найдена новость для публикации:")
        logger.info(f"  🎯 Приоритет: {priority}")
        logger.info(f"  ⏰ Время: {scheduled_time}")
        logger.info(f"  📋 Заголовок: {title[:50]}...")
        
        # Публикуем
        success = self.publish_news_item(news_data)
        
        if success:
            return {
                'success': True,
                'news_id': news_item.get('id'),
                'priority': priority,
                'scheduled_time': scheduled_time,
                'title': title,
                'remaining_news': news_data['total_unpublished'] - 1
            }
        else:
            return {
                'success': False,
                'reason': 'publication_failed',
                'news_id': news_item.get('id'),
                'attempts': news_item.get('publication_attempts', 0) + 1,
                'title': title
            }
    
    def get_publication_status(self, date: Optional[datetime] = None) -> Dict:
        """
        Получает статус публикаций за указанную дату
        
        Args:
            date: Дата для проверки (по умолчанию вчера)
            
        Returns:
            Dict: Статус публикаций
        """
        if date is None:
            date = datetime.now() - timedelta(days=1)
        
        data = self._load_news_file(date)
        if not data:
            return {
                'date': date.strftime('%Y-%m-%d'),
                'file_exists': False,
                'error': 'Файл новостей не найден'
            }
        
        news_list = data.get('news', [])
        published_count = sum(1 for news in news_list if news.get('published', False))
        
        status = {
            'date': date.strftime('%Y-%m-%d'),
            'file_exists': True,
            'total_news': len(news_list),
            'published_count': published_count,
            'unpublished_count': len(news_list) - published_count,
            'collection_time': data.get('collected_at', 'неизвестно'),
            'news_details': []
        }
        
        # Добавляем детали по каждой новости
        for i, news in enumerate(news_list, 1):
            detail = {
                'id': news.get('id', f'news_{i}'),
                'priority': news.get('priority', i),
                'scheduled_time': news.get('scheduled_time', 'не указано'),
                'published': news.get('published', False),
                'title': news.get('title', 'Без названия')[:50],
                'attempts': news.get('publication_attempts', 0)
            }
            
            if news.get('published'):
                detail['published_at'] = news.get('published_at', 'неизвестно')
            
            status['news_details'].append(detail)
        
        return status
    
    def force_publish_by_priority(self, priority: int, 
                                 date: Optional[datetime] = None) -> bool:
        """
        Принудительно публикует новость с указанным приоритетом
        
        Args:
            priority: Приоритет новости (1-5)
            date: Дата файла новостей (по умолчанию вчера)
            
        Returns:
            bool: True если публикация успешна
        """
        if date is None:
            date = datetime.now() - timedelta(days=1)
        
        data = self._load_news_file(date)
        if not data:
            logger.error("📂 Файл новостей не найден")
            return False
        
        # Ищем новость с указанным приоритетом
        target_news = None
        for news_item in data.get('news', []):
            if news_item.get('priority') == priority:
                target_news = news_item
                break
        
        if not target_news:
            logger.error(f"📰 Новость с приоритетом {priority} не найдена")
            return False
        
        if target_news.get('published', False):
            logger.warning(f"📰 Новость с приоритетом {priority} уже опубликована")
            return False
        
        logger.info(f"🚀 Принудительная публикация новости приоритет {priority}")
        
        news_data = {
            'file_date': date,
            'news_item': target_news,
            'total_unpublished': 1
        }
        
        return self.publish_news_item(news_data)
    
    def publish_all_news_for_testing(self, date: Optional[datetime] = None, interval: int = 6) -> Dict:
        """
        Публикует ВСЕ неопубликованные новости подряд для тестирования
        
        Args:
            date: Дата файла новостей (по умолчанию вчера)
            interval: Интервал между публикациями в секундах
            
        Returns:
            Dict: Результат пакетной публикации
        """
        if date is None:
            date = datetime.now() - timedelta(days=1)
        
        data = self._load_news_file(date)
        if not data:
            return {
                'success': False,
                'reason': 'file_not_found',
                'message': 'Файл новостей не найден'
            }
        
        # Получаем все неопубликованные новости
        unpublished_news = []
        for news_item in data.get('news', []):
            if not news_item.get('published', False):
                unpublished_news.append(news_item)
        
        if not unpublished_news:
            return {
                'success': False,
                'reason': 'no_unpublished_news',
                'message': 'Нет неопубликованных новостей'
            }
        
        # Сортируем по приоритету
        unpublished_news.sort(key=lambda x: x.get('priority', 999))
        
        logger.info("🧪 ТЕСТОВЫЙ РЕЖИМ: Публикация всех новостей подряд")
        logger.info(f"📰 Новостей к публикации: {len(unpublished_news)}")
        logger.info(f"⏱️ Интервал между публикациями: {interval} сек")
        logger.info("=" * 60)
        
        results = []
        successful_count = 0
        
        for i, news_item in enumerate(unpublished_news, 1):
            priority = news_item.get('priority', 'неизвестен')
            title = news_item.get('title', 'Без названия')
            
            logger.info(f"📱 Публикация {i}/{len(unpublished_news)}: Приоритет {priority}")
            logger.info(f"📋 {title[:60]}...")
            
            # Публикуем новость
            news_data = {
                'file_date': date,
                'news_item': news_item,
                'total_unpublished': len(unpublished_news)
            }
            
            success = self.publish_news_item(news_data)
            
            result = {
                'index': i,
                'priority': priority,
                'title': title,
                'success': success
            }
            results.append(result)
            
            if success:
                successful_count += 1
                logger.info(f"✅ Публикация {i}/{len(unpublished_news)} успешна")
            else:
                logger.error(f"❌ Публикация {i}/{len(unpublished_news)} неудачна")
            
            # Пауза между публикациями (кроме последней)
            if i < len(unpublished_news):
                logger.info(f"⏳ Пауза {interval} секунд...")
                import time
                time.sleep(interval)
        
        logger.info("=" * 60)
        logger.info(f"🏁 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО:")
        logger.info(f"   ✅ Успешно: {successful_count}")
        logger.info(f"   ❌ Неудачно: {len(unpublished_news) - successful_count}")
        logger.info(f"   📊 Процент успеха: {(successful_count/len(unpublished_news)*100):.1f}%")
        
        return {
            'success': True,
            'total_news': len(unpublished_news),
            'successful_count': successful_count,
            'failed_count': len(unpublished_news) - successful_count,
            'success_rate': successful_count / len(unpublished_news) if unpublished_news else 0,
            'results': results
        }


def main():
    """Функция для тестирования модуля"""
    logger.info("🧪 Тестирование NewsPublisher...")
    
    publisher = NewsPublisher()
    
    # Показываем статус
    status = publisher.get_publication_status()
    logger.info(f"📊 Статус публикаций: {status}")
    
    # Пытаемся опубликовать следующую новость
    result = publisher.publish_next_scheduled_news()
    logger.info(f"📰 Результат публикации: {result}")


if __name__ == "__main__":
    main()