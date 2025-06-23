#!/usr/bin/env python3
"""
OpenAI клиент для генерации комиксов к юридическим новостям
"""

import io
import base64
from typing import Optional
from loguru import logger
from openai import OpenAI

import config


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
        # Извлекаем  факты из новостей для более точного комикса
        key_points = []
        lines = news_content.split('\n')
        for line in lines:
            if '📜' in line:
                # Извлекаем название документа
                key_points.append(f"Legal document: {line.replace('📜', '').strip()}")
            elif any(keyword in line.lower() for keyword in ['штраф', 'налог', 'закон', 'запрет', 'льгота', 'пособие']):
                # Важные юридические термины
                key_points.append(line.strip())
        
        context = ' '.join(key_points[:3])  # Берем первые 3 ключевых момента
        
        # Выбираем случайный стиль для вариативности
        import random
        styles = [
            "photorealistic digital art, dramatic lighting, meme-worthy composition",
            "modern illustration style, flat design with depth, vibrant colors",
            "editorial cartoon style, satirical but respectful, clean lines",
            "realistic 3D render, Pixar-like quality, expressive characters",
            "minimalist vector art, bold colors, simple but impactful"
        ]
        chosen_style = random.choice(styles)
        
        prompt = f"""
Create a witty single-panel illustration about Russian legal news:

TOPIC: {context}

STYLE: {chosen_style}

SCENE REQUIREMENTS:
- 1-2 modern Russian characters in everyday situations
- Contemporary setting (office, street, home, cafe)
- One speech bubble with short, witty Russian text
- Clear visual metaphor for the legal change
- Relatable, everyday scenario

CHARACTER REACTIONS (choose one):
😅 Confused but amused
🤔 Deeply contemplating
😱 Mildly shocked
🙄 Sarcastically accepting
💭 Lost in thought

SPEECH BUBBLE IDEAS (adapt to topic):
"Так, что там опять придумали?"
"Ну вот, теперь и это..."
"А можно проще было?"
"Интересненько..."
"Это точно поможет?"

VISUAL APPROACH:
- Clean, modern composition
- Good contrast and readability
- Subtle humor without being offensive
- Professional but approachable
- Focus on human reactions and emotions

The image should be immediately understandable and shareable, capturing the essence of how regular people react to legal changes.
"""
        
        return prompt.strip()
    
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
                model="gpt-image-1",
                prompt=prompt,
                size="1024x1024",
                quality="medium",  # Для gpt-image-1: low, medium, high, auto
                n=1
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
                model="gpt-image-1",
                prompt="Simple test image: a small blue circle on white background",
                size="1024x1024",
                quality="low",
                n=1
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