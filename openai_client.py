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
    
    def __init__(self):
        self.api_key = config.OPENAI_API_KEY
        self.client = None
        
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
            
            response = self.client.images.generate(
                model=config.OPENAI_IMAGE_MODEL,  # Используем модель из конфига
                prompt=prompt,
                size=PromptConfig.OPENAI_IMAGE_SIZE,
                quality=PromptConfig.OPENAI_IMAGE_QUALITY,
                n=PromptConfig.OPENAI_IMAGE_COUNT
            )
            
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