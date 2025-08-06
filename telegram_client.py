import asyncio
import io
import re
import random
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path
from loguru import logger
import telegram
from telegram import Bot
from telegram.error import TelegramError
from telegram.request import HTTPXRequest
from difflib import SequenceMatcher

import config
from file_utils import safe_json_read, safe_json_write  # Используем безопасные операции с файлами
from types_models import TelegramMessage, MessageHistoryItem  # Используем типизацию


class TelegramClient:
    """Клиент для отправки сообщений в Telegram канал"""
    
    def __init__(self):
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.channel_id = config.TELEGRAM_CHANNEL_ID
        self.bot = None
        
        # Файл для хранения истории сообщений
        self.history_file = Path("logs/message_history.json")
        self.max_history_items = 15  # Храним последние 15 сообщений
        self.max_history_days = 7  # Удаляем сообщения старше 7 дней
        
        # Создаем папку logs если её нет
        self.history_file.parent.mkdir(exist_ok=True)
        
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN не установлен в переменных окружения")
        if not self.channel_id:
            logger.warning("TELEGRAM_CHANNEL_ID не установлен в переменных окружения")
    
    def _initialize_bot(self):
        """Инициализирует бота если ещё не инициализирован"""
        if self.bot is None:
            # Настраиваем HTTP клиент с таймаутами
            request = HTTPXRequest(
                connection_pool_size=1,
                read_timeout=60,
                write_timeout=60,
                connect_timeout=30,
                pool_timeout=30
            )
            self.bot = Bot(token=self.bot_token, request=request)
    
    def _get_content_hash(self, content: str) -> str:
        """
        Создает хеш очищенного контента для сравнения
        
        Args:
            content: Исходный контент
            
        Returns:
            str: SHA-256 хеш очищенного контента
        """
        cleaned = self._clean_content_for_comparison(content)
        return hashlib.sha256(cleaned.encode('utf-8')).hexdigest()
    
    def _load_message_history(self) -> List[MessageHistoryItem]:
        """
        Загружает историю сообщений из файла с блокировкой
        
        Returns:
            List[MessageHistoryItem]: Список сообщений с хешами и временными метками
        """
        history = safe_json_read(self.history_file, default=[])
        if history:
            logger.debug(f"Загружена история из {len(history)} сообщений")
        return history
    
    def _save_message_to_history(self, content: str) -> None:
        """
        Сохраняет новое сообщение в историю с блокировкой файла
        
        Args:
            content: Контент сообщения для сохранения
        """
        # Загружаем существующую историю
        history = self._load_message_history()
        
        # Создаем запись о новом сообщении
        message_record = MessageHistoryItem(
            hash=self._get_content_hash(content),
            timestamp=datetime.now().isoformat(),
            preview=self._clean_content_for_comparison(content)[:100]
        )
        
        # Добавляем в начало списка (новые сообщения первыми)
        history.insert(0, message_record)
        
        # Очищаем старые записи
        history = self._cleanup_history(history)
        
        # Сохраняем обновленную историю с блокировкой
        if safe_json_write(self.history_file, history):
            logger.debug(f"Сообщение сохранено в историю. Всего записей: {len(history)}")
        else:
            logger.error("Не удалось сохранить сообщение в историю")
    
    def _cleanup_history(self, history: List[Dict]) -> List[Dict]:
        """
        Очищает историю от старых сообщений
        
        Args:
            history: Текущая история сообщений
            
        Returns:
            List[Dict]: Очищенная история
        """
        try:
            # Удаляем записи старше max_history_days дней
            cutoff_date = datetime.now() - timedelta(days=self.max_history_days)
            
            filtered_history = []
            for record in history:
                try:
                    record_date = datetime.fromisoformat(record['timestamp'])
                    if record_date > cutoff_date:
                        filtered_history.append(record)
                except (ValueError, KeyError):
                    # Пропускаем некорректные записи
                    continue
            
            # Ограничиваем количество записей
            if len(filtered_history) > self.max_history_items:
                filtered_history = filtered_history[:self.max_history_items]
                
            logger.debug(f"История очищена: было {len(history)}, стало {len(filtered_history)}")
            return filtered_history
            
        except Exception as e:
            logger.error(f"Ошибка при очистке истории: {e}")
            return history[:self.max_history_items]  # Fallback: просто ограничиваем количество

    async def _check_for_duplicates(self, new_content: str, similarity_threshold: float = 0.7) -> bool:
        """
        Проверяет историю сообщений на дублирование контента
        
        Args:
            new_content: Новый контент для проверки
            similarity_threshold: Порог схожести (0.7 = 70% схожести)
            
        Returns:
            bool: True если найден дублированный контент
        """
        try:
            # Получаем хеш нового контента
            new_hash = self._get_content_hash(new_content)
            new_cleaned = self._clean_content_for_comparison(new_content)
            
            # Загружаем историю сообщений
            history = self._load_message_history()
            
            if not history:
                logger.debug("История сообщений пуста - дубликатов нет")
                return False
            
            logger.info(f"Проверяю на дубликаты среди {len(history)} сохраненных сообщений")
            
            # Проверяем точное совпадение по хешу
            for record in history:
                if record.get('hash') == new_hash:
                    logger.warning(f"Найден точный дубликат по хешу: {record.get('preview', '')[:50]}...")
                    return True
            
            # Проверяем схожесть текста с помощью SequenceMatcher
            for record in history:
                try:
                    # Восстанавливаем очищенный текст из preview (для совместимости)
                    # В реальности лучше хранить полный очищенный текст отдельно
                    old_preview = record.get('preview', '')
                    
                    # Если preview слишком короткий, пропускаем детальную проверку
                    if len(old_preview) < 50 or len(new_cleaned) < 50:
                        continue
                    
                    # Вычисляем схожесть
                    similarity = SequenceMatcher(None, new_cleaned, old_preview).ratio()
                    
                    if similarity >= similarity_threshold:
                        timestamp = record.get('timestamp', 'неизвестно')
                        logger.warning(f"Найден похожий контент (схожесть: {similarity:.2%}, порог: {similarity_threshold:.2%})")
                        logger.warning(f"Дата предыдущего сообщения: {timestamp}")
                        logger.warning(f"Превью: {old_preview[:100]}...")
                        return True
                        
                except Exception as e:
                    logger.error(f"Ошибка при сравнении с записью в истории: {e}")
                    continue
            
            logger.info("Дубликатов не найдено")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при проверке дубликатов: {e}")
            # В случае ошибки разрешаем публикацию (безопасный fallback)
            return False
    
    def _clean_content_for_comparison(self, content: str) -> str:
        """
        Очищает контент от форматирования для сравнения
        
        Args:
            content: Исходный контент
            
        Returns:
            str: Очищенный контент
        """
        # Убираем HTML теги
        clean = re.sub(r'<[^>]+>', '', content)
        # Убираем эмодзи и специальные символы
        clean = re.sub(r'[🎭📅💬📜🔗🤖🕐]', '', clean)
        # Убираем даты и время
        clean = re.sub(r'\d{2}\.\d{2}\.\d{4}', '', clean)
        clean = re.sub(r'\d{2}:\d{2}', '', clean)
        # Убираем ссылки
        clean = re.sub(r'https?://[^\s]+', '', clean)
        # Убираем лишние пробелы
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        return clean.lower()
    
    def _generate_ironic_title(self, content: str) -> str:
        """
        Генерирует ироничный заголовок на основе контента
        
        Args:
            content: Контент новости
            
        Returns:
            str: Ироничный заголовок
        """
        # Извлекаем ключевые слова из контента
        keywords = []
        if 'штраф' in content.lower():
            keywords.extend(['штрафы', 'кошелёк'])
        if 'налог' in content.lower():
            keywords.extend(['налоги', 'бюджет'])
        if 'пособие' in content.lower() or 'выплата' in content.lower():
            keywords.extend(['пособия', 'выплаты'])
        if 'закон' in content.lower():
            keywords.extend(['законов', 'нормы'])
        if 'цифров' in content.lower():
            keywords.extend(['цифра', 'технологии'])
        
        # Базовые ироничные заголовки
        templates = [
            f"🎭 Сводка дня: что нового в мире {random.choice(keywords) if keywords else 'юриспруденции'}",
            f"🎪 Цирк продолжается: свежие новости права",
            f"🎯 В мире {random.choice(keywords) if keywords else 'законов'}: что на этот раз?",
            f"🎨 Арт-сводка: творчество законодателей",
            f"🎬 Сегодня в эфире: {random.choice(keywords) if keywords else 'правовые'} новости",
            f"🎪 Шоу продолжается: обзор дня",
            f"🎭 Театр абсурда: что нового в законах"
        ]
        
        return random.choice(templates)
    
    def _format_legal_message(self, data: dict) -> str:
        """
        Форматирует сообщение о законодательных изменениях для Telegram
        
        Args:
            data: Словарь с 'content' (текст) и 'sources' (список ссылок)
            
        Returns:
            str: Отформатированное сообщение
        """
        content = data.get('content', '')
        sources = data.get('sources', [])

        # Удаляем все маркеры ссылок из текста (если они остались)
        content = re.sub(r'\s*\[\d+\]', '', content)

        # Если текст пришел без переносов строк (все в одной строке),
        # то нужно восстановить структуру
        if '\n' not in content and len(content) > 200:
            # Разбиваем по известным маркерам
            content = content.replace('💬 КОММЕНТАРИЙ', '\n\n💬 КОММЕНТАРИЙ')
            content = content.replace('ИСТОЧНИКИ:', '\n\nИСТОЧНИКИ:')
            
            # ВАЖНО: Добавляем перенос после "КОНСУЛЬТАНТА:"
            content = content.replace('КОНСУЛЬТАНТА:', 'КОНСУЛЬТАНТА:\n\n')
            content = content.replace('ЮРИСТА:', 'ЮРИСТА:\n\n')
            
            # Разбиваем длинные абзацы по точкам (после точки + пробел + заглавная буква)
            # Ищем точку + пробел + заглавная буква, но не внутри скобок и кавычек
            content = re.sub(r'(\.) ([А-ЯЁ])', r'\1\n\n\2', content)
            
            # Убираем лишние пробелы в начале строк
            content = '\n'.join(line.strip() for line in content.split('\n'))

        # Форматирование строк
        lines = content.split('\n')
        formatted_lines = []
        
        for i, line in enumerate(lines):
            # Сохраняем пустые строки для абзацев
            if not line.strip():
                formatted_lines.append('')
            # Обрабатываем заголовок и добавляем ссылку на источник
            elif line.strip().startswith('📜'):
                # Добавляем ссылку [источник] в конец заголовка
                if sources:
                    formatted_line = f"<b>{line.strip()}</b> <a href=\"{sources[0]}\">[источник]</a>"
                else:
                    formatted_line = f"<b>{line.strip()}</b>"
                formatted_lines.append(formatted_line)
            # Для строк с 💬 делаем жирным только заголовок до двоеточия
            elif line.strip().startswith('💬'):
                if ':' in line:
                    # Разделяем по первому двоеточию
                    parts = line.strip().split(':', 1)
                    formatted_lines.append(f"<b>{parts[0]}:</b>")
                    # Если есть текст после двоеточия в той же строке, добавляем его отдельно
                    if len(parts) > 1 and parts[1].strip():
                        formatted_lines.append(parts[1].strip())
                else:
                    # Если нет двоеточия, делаем всю строку жирной
                    formatted_lines.append(f"<b>{line.strip()}</b>")
            else:
                # Обычный текст без форматирования
                formatted_lines.append(line.strip())
                
        # Объединяем строки, сохраняя переносы
        formatted_content = '\n'.join(formatted_lines)
        
        # Заменяем старый текст на новый, если AI его вернул
        formatted_content = formatted_content.replace(
            "КОММЕНТАРИЙ ЮРИСТА:", 
            "КОММЕНТАРИЙ КАРМАННОГО КОНСУЛЬТАНТА:"
        )
        
        # Возвращаем отформатированный контент
        return formatted_content
    
    def _split_long_message(self, message: str, max_length: int = 4000) -> list[str]:
        """
        Разбивает длинное сообщение на части для Telegram
        
        Args:
            message: Исходное сообщение
            max_length: Максимальная длина одной части
            
        Returns:
            list[str]: Список частей сообщения
        """
        if len(message) <= max_length:
            return [message]
        
        parts = []
        current_part = ""
        
        # Разбиваем по абзацам
        paragraphs = message.split('\n\n')
        
        for paragraph in paragraphs:
            # Если добавление абзаца превысит лимит
            if len(current_part + paragraph + '\n\n') > max_length:
                if current_part:
                    parts.append(current_part.strip())
                    current_part = paragraph + '\n\n'
                else:
                    # Если один абзац слишком длинный, разбиваем по предложениям
                    sentences = paragraph.split('. ')
                    for sentence in sentences:
                        if len(current_part + sentence + '. ') > max_length:
                            if current_part:
                                parts.append(current_part.strip())
                                current_part = sentence + '. '
                            else:
                                # Если даже предложение слишком длинное, обрезаем
                                parts.append(sentence[:max_length-3] + "...")
                        else:
                            current_part += sentence + '. '
            else:
                current_part += paragraph + '\n\n'
        
        if current_part:
            parts.append(current_part.strip())
        
        return parts
    
    async def send_message(self, message: dict) -> bool:
        """
        Отправляет сообщение в Telegram канал
        
        Args:
            message: Словарь с данными для отправки
            
        Returns:
            bool: True если отправка прошла успешно
        """
        try:
            self._initialize_bot()
            
            if not self.bot_token or not self.channel_id:
                logger.error("Не установлены токен бота или ID канала")
                return False
            
            # Форматируем сообщение
            formatted_message = self._format_legal_message(message)
            
            # Проверяем на дублирование
            if await self._check_for_duplicates(formatted_message):
                logger.warning("Контент дублируется с недавними сообщениями - пропускаю отправку")
                return True  # Возвращаем True, так как это не ошибка, а валидная причина пропуска
            
            # Разбиваем на части если нужно
            message_parts = self._split_long_message(formatted_message)
            
            logger.info(f"Отправляю сообщение в канал {self.channel_id}")
            logger.info(f"Сообщение разбито на {len(message_parts)} частей")
            
            # Отправляем все части
            for i, part in enumerate(message_parts):
                try:
                    await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=part,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                    
                    logger.info(f"Часть {i+1}/{len(message_parts)} отправлена успешно")
                    
                    # Небольшая пауза между частями
                    if i < len(message_parts) - 1:
                        await asyncio.sleep(1)
                        
                except TelegramError as e:
                    logger.error(f"Ошибка при отправке части {i+1}: {e}")
                    return False
            
            logger.info("Все части сообщения отправлены успешно")
            
            # Сохраняем сообщение в историю после успешной отправки
            self._save_message_to_history(formatted_message)
            
            return True
            
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке сообщения: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """
        Тестирует подключение к Telegram API
        
        Returns:
            bool: True если подключение работает
        """
        try:
            self._initialize_bot()
            
            if not self.bot_token:
                logger.error("Токен бота не установлен")
                return False
            
            # Получаем информацию о боте
            bot_info = await self.bot.get_me()
            logger.info(f"Подключение к Telegram успешно. Бот: @{bot_info.username}")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при тестировании Telegram подключения: {e}")
            return False
    
    async def send_message_with_image(self, message: dict, image_bytes: bytes) -> bool:
        """
        Отправляет сообщение с изображением в Telegram канал
        
        Args:
            message: Словарь с данными для отправки
            image_bytes: Данные изображения в байтах
            
        Returns:
            bool: True если отправка прошла успешно
        """
        try:
            self._initialize_bot()
            
            if not self.bot_token or not self.channel_id:
                logger.error("Не установлены токен бота или ID канала")
                return False
            
            # Форматируем сообщение
            formatted_message = self._format_legal_message(message)
            
            # Проверяем на дублирование
            if await self._check_for_duplicates(formatted_message):
                logger.warning("Контент дублируется с недавними сообщениями - пропускаю отправку")
                return True  # Возвращаем True, так как это не ошибка, а валидная причина пропуска
            
            logger.info(f"Отправляю сообщение с комиксом в канал {self.channel_id}")
            
            # Создаем объект файла из байтов
            image_file = io.BytesIO(image_bytes)
            image_file.name = "legal_comic.png"
            
            # Telegram лимит caption для фото: 1024 символа
            if len(formatted_message) <= 1000:
                # Отправляем изображение с подписью
                await self.bot.send_photo(
                    chat_id=self.channel_id,
                    photo=image_file,
                    caption=formatted_message,
                    parse_mode='HTML'
                )
                logger.info("Сообщение с комиксом отправлено одним сообщением")
            else:
                # Сначала отправляем изображение без подписи
                await self.bot.send_photo(
                    chat_id=self.channel_id,
                    photo=image_file
                )
                
                # Затем отправляем полный текст отдельным сообщением
                await asyncio.sleep(1)
                message_parts = self._split_long_message(formatted_message)
                
                for i, part in enumerate(message_parts):
                    await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=part,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                    
                    if i < len(message_parts) - 1:
                        await asyncio.sleep(1)
                
                logger.info(f"Сообщение с комиксом отправлено: фото + {len(message_parts)} текстовых частей")
            
            logger.info("Сообщение с комиксом отправлено успешно")
            
            # Сохраняем сообщение в историю после успешной отправки
            self._save_message_to_history(formatted_message)
            
            return True
            
        except TelegramError as e:
            logger.error(f"Ошибка при отправке сообщения с изображением: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке с изображением: {e}")
            return False

    def send_legal_update(self, content: TelegramMessage) -> bool:
        """
        Синхронная обёртка для отправки законодательных обновлений
        
        Args:
            content: Словарь с данными от AI о законодательных изменениях
            
        Returns:
            bool: True если отправка прошла успешно
        """
        return asyncio.run(self.send_message(content))
    
    def send_legal_update_with_comic(self, content: TelegramMessage, image_bytes: bytes) -> bool:
        """
        Синхронная обёртка для отправки законодательных обновлений с комиксом
        
        Args:
            content: Словарь с данными от AI о законодательных изменениях
            image_bytes: Данные изображения комикса
            
        Returns:
            bool: True если отправка прошла успешно
        """
        return asyncio.run(self.send_message_with_image(content, image_bytes))

 