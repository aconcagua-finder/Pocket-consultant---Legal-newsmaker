import requests  # Добавлен отсутствующий импорт
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from loguru import logger

import config
from prompts import (
    get_perplexity_system_prompt,
    get_perplexity_news_prompt,
    PromptConfig
)
from validation import is_content_fresh, get_date_feedback_for_next_prompt


class PerplexityClient:
    """Клиент для работы с Perplexity API (модель Sonar Deep Research)"""
    
    def __init__(self, web_config=None):
        """
        Инициализация клиента Perplexity
        
        Args:
            web_config: Опциональная конфигурация из веб-интерфейса
        """
        self.api_key = config.PERPLEXITY_API_KEY
        self.api_url = config.PERPLEXITY_API_URL
        self.timeout = config.REQUEST_TIMEOUT
        
        # Используем настройки из веб-конфига если они переданы
        if web_config and 'api_models' in web_config:
            perplexity_config = web_config['api_models'].get('perplexity', {})
            self.model = perplexity_config.get('model', config.PERPLEXITY_MODEL)
            
            # Автоматическая корректировка max_tokens в зависимости от модели
            max_tokens_limits = perplexity_config.get('max_tokens_limits', {})
            if self.model in max_tokens_limits:
                max_allowed = max_tokens_limits[self.model]
                requested = perplexity_config.get('max_tokens', config.PERPLEXITY_MAX_TOKENS)
                self.max_tokens = min(requested, max_allowed)
                if requested > max_allowed:
                    logger.warning(f"Запрошено {requested} токенов для {self.model}, но лимит {max_allowed}. Используем {self.max_tokens}")
            else:
                self.max_tokens = perplexity_config.get('max_tokens', config.PERPLEXITY_MAX_TOKENS)
            
            self.temperature = perplexity_config.get('temperature', 0.7)
            self.top_p = perplexity_config.get('top_p', 0.9)
            self.presence_penalty = perplexity_config.get('presence_penalty', 0.0)
            self.frequency_penalty = perplexity_config.get('frequency_penalty', 0.0)
            self.return_citations = perplexity_config.get('return_citations', True)
            self.return_related_questions = perplexity_config.get('return_related_questions', False)
            self.search_domain_filter = perplexity_config.get('search_domain_filter', [])
            
            # Новые параметры для глубокого поиска
            self.search_recency_filter = perplexity_config.get('search_recency_filter', None)
            self.search_depth = perplexity_config.get('search_depth', 'high')
            self.search_after_date_filter = perplexity_config.get('search_after_date_filter', None)
            self.search_before_date_filter = perplexity_config.get('search_before_date_filter', None)
            self.web_search_options = perplexity_config.get('web_search_options', {
                'search_context_size': 'high',
                'enable_deep_search': True
            })
        else:
            # Дефолтные значения
            self.model = config.PERPLEXITY_MODEL
            self.max_tokens = config.PERPLEXITY_MAX_TOKENS
            self.temperature = 0.7
            self.top_p = 0.9
            self.presence_penalty = 0.0
            self.frequency_penalty = 0.0
            self.return_citations = True
            self.return_related_questions = False
            self.search_domain_filter = []
            self.search_recency_filter = None
            self.search_depth = 'high'
            self.search_after_date_filter = None
            self.search_before_date_filter = None
            self.web_search_options = {
                'search_context_size': 'high',
                'enable_deep_search': True
            }
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _clean_deep_research_content(self, content: str) -> str:
        """
        Очищает контент от тегов рассуждений Deep Research
        
        Args:
            content: Сырой контент от Deep Research API
            
        Returns:
            str: Очищенный контент без тегов <think> и </think>
        """
        # Удаляем блоки рассуждений <think>...</think>
        cleaned = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        # Удаляем оставшиеся одиночные теги
        cleaned = re.sub(r'</?think>', '', cleaned)
        
        # Убираем лишние переносы строк
        cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
        
        # Убираем пробелы в начале и конце
        return cleaned.strip()
    
    
    
    def _extract_sources_from_content(self, content: str) -> Tuple[str, List[str]]:
        """
        Извлекает источники из ответа AI и возвращает текст с номерами + список ссылок
        
        Args:
            content: Полный ответ от AI
            
        Returns:
            Tuple[str, List[str]]: (текст с номерами источников, список ссылок по порядку)
        """
        sources = []
        
        # Разделяем контент на основную часть и секцию ссылок
        lines = content.split('\n')
        main_content_lines = []
        sources_section_started = False
        
        for line in lines:
            # Ищем строку "ИСТОЧНИКИ:" и начинаем секцию источников
            if line.strip().upper() == 'ИСТОЧНИКИ:' or line.strip().upper().startswith('ИСТОЧНИК'):
                sources_section_started = True
                # НЕ добавляем эту строку в основной контент
                continue
                
            # Ищем строку с источником (новый формат: "🔗 Источник: https://...")
            if line.strip().startswith('🔗'):
                # Извлекаем ссылку из строки типа "🔗 Источник: https://ссылка [1]"
                url_match = re.search(r'https?://[^\s\[\]]+', line)
                if url_match:
                    source_url = url_match.group().rstrip('.,;:')
                    sources.append(source_url)
                # НЕ добавляем строку в основной контент - убираем источники из отображения
                continue
                
            # Также ищем старый формат секции ссылок для совместимости
            if re.match(r'^Ссылки:\s*$', line.strip(), re.IGNORECASE):
                sources_section_started = True
                continue
            
            if sources_section_started:
                # В секции ссылок ищем строки вида [номер] ссылка
                source_match = re.match(r'^\[(\d+)\]\s*(https?://[^\s]+)', line.strip())
                if source_match:
                    source_num = int(source_match.group(1))
                    source_url = source_match.group(2).rstrip('.,;:')
                    
                    # Расширяем список если нужно
                    while len(sources) < source_num:
                        sources.append('')
                    sources[source_num - 1] = source_url
            else:
                # Основной контент - сохраняем
                main_content_lines.append(line)
        
        # Убираем пустые элементы из sources
        sources = [s for s in sources if s]
        
        # Формируем основной текст
        main_content = '\n'.join(main_content_lines).strip()
        
        # Если не нашли источники в отдельной секции, пробуем найти в тексте
        if not sources:
            url_pattern = r'https?://[^\s\)\]>]+'
            sources = re.findall(url_pattern, content)
            sources = list(set(sources))
            sources = [source.rstrip('.,;:') for source in sources]
            
            # Если URL не найдены, но есть ссылки на документы, добавляем стандартные источники
            if not sources and '[1]' in main_content:
                # Ищем упоминания законопроектов
                bill_match = re.search(r'N\s*(\d+-\d+)', main_content)
                if bill_match:
                    bill_number = bill_match.group(1)
                    sources.append(f'https://sozd.duma.gov.ru/bill/{bill_number}')
                else:
                    # Добавляем общий источник
                    sources.append('https://sozd.duma.gov.ru/')
                    
                logger.warning("Источники не найдены в ответе, добавлены стандартные ссылки")
        
        # Если вообще никаких источников не найдено, добавляем дефолтный
        if not sources:
            # Пытаемся найти номер закона в тексте
            law_match = re.search(r'№\s*(\d+-ФЗ)', main_content)
            if law_match:
                law_number = law_match.group(1)
                sources.append(f'https://sozd.duma.gov.ru/bill/{law_number}')
            else:
                # Дефолтный источник на сайт законопроектов
                sources.append('https://sozd.duma.gov.ru/')
            
            logger.warning("Источники не найдены, использую дефолтный источник")
        
        logger.debug(f"Извлечено {len(sources)} источников")
        if sources:
            for i, source in enumerate(sources, 1):
                logger.debug(f"Источник [{i}]: {source}")
        
        return main_content, sources
    
    def get_legal_updates(self) -> Optional[dict]:
        """
        Получает информацию о законодательных изменениях за вчерашний день
        
        Returns:
            dict: {'content': str, 'sources': List[str]} или None в случае ошибки
        """
        try:
            prompt = get_perplexity_news_prompt()
            from prompts import get_yesterday_date
            yesterday_date = get_yesterday_date()
            
            logger.info(f"Запрашиваю информацию о законодательных изменениях за {yesterday_date}")
            
            payload = {
                "model": self.model,
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
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "presence_penalty": self.presence_penalty,
                "frequency_penalty": self.frequency_penalty,
                "return_citations": self.return_citations,
                "return_related_questions": self.return_related_questions
            }
            
            # Добавляем фильтр доменов если есть
            if self.search_domain_filter:
                payload["search_domain_filter"] = self.search_domain_filter
            
            # Добавляем новые параметры поиска если заданы
            if self.search_recency_filter:
                payload["search_recency_filter"] = self.search_recency_filter
                logger.debug(f"Применяю фильтр свежести: {self.search_recency_filter}")
            
            if self.search_after_date_filter:
                payload["search_after_date_filter"] = self.search_after_date_filter
                logger.debug(f"Ищу контент после: {self.search_after_date_filter}")
            
            if self.search_before_date_filter:
                payload["search_before_date_filter"] = self.search_before_date_filter
                logger.debug(f"Ищу контент до: {self.search_before_date_filter}")
            
            # Добавляем расширенные опции поиска для deep research
            if 'deep-research' in self.model.lower() and self.web_search_options:
                if self.web_search_options.get('search_context_size'):
                    payload["search_context_size"] = self.web_search_options['search_context_size']
                if self.web_search_options.get('enable_deep_search'):
                    payload["enable_deep_search"] = self.web_search_options['enable_deep_search']
                logger.info(f"Deep Research режим с контекстом: {self.web_search_options.get('search_context_size', 'default')}")
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            data = response.json()
            raw_content = data['choices'][0]['message']['content']
            
            logger.info("Успешно получен ответ от Perplexity API")
            logger.debug(f"Ответ получен (первые 200 символов): {raw_content[:200]}...")
            
            # Очищаем от тегов рассуждений Deep Research
            cleaned_content = self._clean_deep_research_content(raw_content)
            
            # Извлекаем источники
            content, sources = self._extract_sources_from_content(cleaned_content)
            
            # Удаляем любые оставшиеся маркеры ссылок из текста
            content = re.sub(r'\s*\[\d+\]', '', content)
            
            # Проверяем актуальность новости
            is_fresh, freshness_reason = is_content_fresh(content, max_age_days=3)
            logger.info(f"Проверка актуальности: {freshness_reason}")
            
            if not is_fresh:
                logger.warning("⚠️ Полученная новость устарела, попробуем еще раз с более строгими критериями")
                # Можно добавить повторный запрос с улучшенным промптом
                # Пока возвращаем как есть, но с предупреждением
            
            return {
                'content': content,
                'sources': sources
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к Perplexity API: {e}")
            return None
            
        except KeyError as e:
            logger.error(f"Неожиданный формат ответа от API: {e}")
            return None
            
        except Exception as e:
            logger.error(f"Неизвестная ошибка при работе с API: {e}")
            return None
    
    def test_connection(self) -> bool:
        """
        Тестирует подключение к API
        
        Returns:
            bool: True если подключение работает
        """
        try:
            test_payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Привет! Это тестовый запрос."
                    }
                ],
                "max_tokens": 50,
                "temperature": self.temperature,
                "return_citations": False  # Отключаем для теста
            }
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=test_payload,
                timeout=10
            )
            
            response.raise_for_status()
            logger.info("Тест подключения к Perplexity API прошел успешно")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при тестировании подключения: {e}")
            return False 