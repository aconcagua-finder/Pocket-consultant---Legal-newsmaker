#!/usr/bin/env python3
"""
OpenAI клиент для генерации комиксов к юридическим новостям
"""

import io
import base64
import random
from typing import Optional
from loguru import logger
from openai import OpenAI

import config
from prompts import (
    get_openai_comic_styles,
    get_openai_comic_prompt,
    get_openai_test_prompt,
    get_comic_context_from_news,
    PromptConfig
)


class OpenAIClient:
    """Клиент для работы с OpenAI API для генерации изображений"""
    
    def __init__(self, web_config=None):
        """
        Инициализация клиента OpenAI
        
        Args:
            web_config: Опциональная конфигурация из веб-интерфейса
        """
        self.api_key = config.OPENAI_API_KEY
        self.client = None
        
        # Используем настройки из веб-конфига если они переданы
        if web_config and 'api_models' in web_config:
            openai_config = web_config['api_models'].get('openai', {})
            self.model = openai_config.get('model', 'dall-e-3')
            self.image_quality = openai_config.get('image_quality', 'standard')
            self.image_style = openai_config.get('image_style', 'vivid')
            self.image_size = openai_config.get('image_size', '1024x1024')
            self.response_format = openai_config.get('response_format', 'url')
            self.n_images = openai_config.get('n_images', 1)
            self.moderation = openai_config.get('moderation', 'auto')  # Для gpt-image-1
        else:
            # Дефолтные значения
            self.model = 'dall-e-3'
            self.image_quality = 'standard'
            self.image_style = 'vivid'
            self.image_size = '1024x1024'
            self.response_format = 'url'
            self.n_images = 1
            self.moderation = 'auto'
        
        if not self.api_key:
            logger.warning("OPENAI_API_KEY не установлен")
        else:
            self.client = OpenAI(api_key=self.api_key)
    
    def _create_comic_prompt(self, news_content: str) -> str:
        """
        Создает промпт для генерации комикса на основе новостей
        
        Args:
            news_content: Текст новостей о законодательных изменениях
            
        Returns:
            str: Промпт для модели генерации изображений OpenAI
        """
        # Извлекаем контекст из новостей
        context = get_comic_context_from_news(news_content)
        
        # Выбираем случайный стиль для вариативности
        styles = get_openai_comic_styles()
        chosen_style = random.choice(styles)
        
        # Создаем промпт
        return get_openai_comic_prompt(context, chosen_style)
    
    def generate_comic_image(self, news_content: str) -> Optional[bytes]:
        """
        Генерирует комикс-изображение на основе новостей
        
        Args:
            news_content: Текст новостей для создания комикса
            
        Returns:
            bytes: Данные изображения в формате PNG или None при ошибке
        """
        if not self.client:
            logger.error("OpenAI клиент не инициализирован")
            return None
        
        try:
            prompt = self._create_comic_prompt(news_content)
            logger.info("Генерирую комикс с помощью OpenAI Image Generation...")
            logger.debug(f"Промпт: {prompt[:100]}...")
            
            # Формируем параметры в зависимости от модели
            params = {
                "model": self.model,
                "prompt": prompt,
                "size": self.image_size,
                "n": self.n_images,
                "response_format": self.response_format
            }
            
            # Добавляем параметры в зависимости от модели
            if self.model == 'dall-e-3':
                # DALL-E 3 поддерживает quality и style
                params["quality"] = self.image_quality  # standard или hd
                if self.image_style:  # vivid или natural
                    params["style"] = self.image_style
            elif self.model == 'gpt-image-1':
                # gpt-image-1 использует quality по-другому
                quality_map = {'low': 'low', 'medium': 'medium', 'high': 'high'}
                params["quality"] = quality_map.get(self.image_quality, 'high')
                # Добавляем moderation для gpt-image-1
                params["moderation"] = self.moderation
            elif self.model == 'dall-e-2':
                # DALL-E 2 не поддерживает quality и style
                pass
            
            response = self.client.images.generate(**params)
            
            # Проверяем, есть ли URL или base64
            if hasattr(response.data[0], 'url') and response.data[0].url:
                # Если есть URL, загружаем изображение
                image_url = response.data[0].url
                import requests
                image_response = requests.get(image_url, timeout=30)
                image_response.raise_for_status()
                image_bytes = image_response.content
            elif hasattr(response.data[0], 'b64_json') and response.data[0].b64_json:
                # Если есть base64, декодируем
                image_bytes = base64.b64decode(response.data[0].b64_json)
            else:
                raise ValueError("Ответ не содержит ни URL, ни base64 данных")
            
            logger.info(f"Комикс сгенерирован успешно, размер: {len(image_bytes)} байт")
            return image_bytes
            
        except Exception as e:
            logger.error(f"Ошибка при генерации комикса: {e}")
            return None
    
    def test_connection(self) -> bool:
        """
        Тестирует подключение к OpenAI API
        
        Returns:
            bool: True если подключение работает
        """
        if not self.client:
            logger.error("OpenAI клиент не инициализирован")
            return False
        
        try:
            # Пробуем сгенерировать простое изображение
            response = self.client.images.generate(
                model=config.OPENAI_IMAGE_MODEL,  # Используем модель из конфига
                prompt=get_openai_test_prompt(),
                size=PromptConfig.OPENAI_IMAGE_SIZE,
                quality=PromptConfig.OPENAI_IMAGE_QUALITY,
                n=PromptConfig.OPENAI_IMAGE_COUNT
            )
            
            if response.data and len(response.data) > 0:
                logger.info("Подключение к OpenAI API успешно")
                return True
            else:
                logger.error("OpenAI API вернул пустой ответ")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при тестировании OpenAI API: {e}")
            return False 