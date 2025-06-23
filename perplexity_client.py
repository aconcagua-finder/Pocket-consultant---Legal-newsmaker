import requests
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from loguru import logger

import config


class PerplexityClient:
    """Клиент для работы с Perplexity API (модель Sonar-pro)"""
    
    def __init__(self):
        self.api_key = config.PERPLEXITY_API_KEY
        self.api_url = config.PERPLEXITY_API_URL
        self.timeout = config.REQUEST_TIMEOUT
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _get_yesterday_date(self) -> str:
        """Получает вчерашнюю дату в формате 'день месяц'"""
        yesterday = datetime.now() - timedelta(days=1)
        months = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля",
            5: "мая", 6: "июня", 7: "июля", 8: "августа", 
            9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
        }
        
        day = yesterday.day
        month = months[yesterday.month]
        return f"{day} {month}"
    
    def _create_prompt(self) -> str:
        """Создает промпт для запроса информации о законодательных изменениях"""
        yesterday_date = self._get_yesterday_date()
        
        prompt = f"""Найди ОДНО главное изменение в российском законодательстве за {yesterday_date}.

ТРЕБОВАНИЯ:
- Изучи источники и найди КОНКРЕТНЫЕ цифры: суммы, проценты, сроки
- НЕ пиши общие фразы без конкретики
- Комментарий должен быть КРАТКИМ (максимум 100-120 слов)
- Стиль: юридический с легкой иронией, БЕЗ публицистических заголовков

КРИТИЧЕСКИ ВАЖНО ПРО ССЫЛКИ:
- ОБЯЗАТЕЛЬНО ставь [1] после КАЖДОГО факта в тексте
- В заголовке документа ОБЯЗАТЕЛЬНО должен быть [1]
- В первом предложении комментария ОБЯЗАТЕЛЬНО должен быть [1]
- Если упоминаешь факт из источника - ставь [1] или [2] сразу после факта
- Пример: "С 1 июня штраф составит 5000 рублей [1]"

Формат ответа:

📜 Федеральный закон №123-ФЗ [1] - штрафы увеличены вдвое

💬 КОММЕНТАРИЙ КАРМАННОГО КОНСУЛЬТАНТА:

С 1 июня вступает в силу закон об увеличении штрафов до 5000 рублей [1]. 

Затронет всех автомобилистов - придется платить в два раза больше [1].

Видимо, бюджету нужны деньги, а граждане - традиционный источник пополнения казны 💰

ИСТОЧНИКИ:
🔗 Источник: https://sozd.duma.gov.ru/bill/123456-8
🔗 Источник: https://pravo.gov.ru/proxy/ips/?docbody=123456

ВАЖНО: 
- Пиши как юрист-практик, а НЕ журналист
- Максимум 3 коротких абзаца
- БЕЗ ССЫЛОК [1] ОТВЕТ НЕ ПРИНИМАЕТСЯ!"""

        return prompt
    
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
            prompt = self._create_prompt()
            yesterday_date = self._get_yesterday_date()
            
            logger.info(f"Запрашиваю информацию о законодательных изменениях за {yesterday_date}")
            
            payload = {
                "model": "sonar-pro",
                "messages": [
                    {
                        "role": "system",
                        "content": "Ты опытный юрист-практик. Отвечай кратко, по существу, с конкретными фактами и цифрами."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "max_tokens": 600,
                "temperature": 0.2,
                "top_p": 0.9
            }
            
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
            logger.info(f"Полный ответ от AI:\n{raw_content}\n---")
            
            # Проверяем наличие маркеров ссылок
            link_markers = re.findall(r'\[\d+\]', raw_content)
            if link_markers:
                logger.debug(f"Найдены маркеры ссылок в тексте: {link_markers}")
            else:
                logger.warning("В тексте не найдены маркеры ссылок [1], [2] и т.д.")
            
            # Извлекаем источники
            content, sources = self._extract_sources_from_content(raw_content)
            
            # Заменяем любые номера ссылок на [1], [2] и т.д. по порядку
            # Находим все уникальные номера ссылок в тексте
            all_ref_numbers = sorted(set(int(m.group(1)) for m in re.finditer(r'\[(\d+)\]', content)))
            
            if all_ref_numbers:
                logger.info(f"Найдены ссылки с номерами: {all_ref_numbers}")
                # Создаем маппинг старых номеров на новые
                ref_mapping = {old_num: new_num for new_num, old_num in enumerate(all_ref_numbers, 1)}
                
                # Заменяем все ссылки
                for old_num, new_num in ref_mapping.items():
                    old_ref = f'[{old_num}]'
                    new_ref = f'[{new_num}]'
                    content = content.replace(old_ref, new_ref)
                    logger.debug(f"Заменено {old_ref} на {new_ref}")
            
            # Проверяем наличие маркеров после замены
            link_markers = re.findall(r'\[\d+\]', content)
            if not link_markers and sources:
                logger.warning("Добавляю недостающие маркеры ссылок...")
                lines = content.split('\n')
                modified_lines = []
                
                for i, line in enumerate(lines):
                    if line.strip():
                        # Добавляем [1] к заголовку документа
                        if line.strip().startswith('📜') and '[1]' not in line:
                            line = line.rstrip() + ' [1]'
                            logger.debug(f"Добавлен [1] к заголовку: {line}")
                        # Добавляем [1] к первому предложению комментария
                        elif i > 0 and lines[i-1].strip().startswith('💬') and '[1]' not in line:
                            # Добавляем [1] в конец первого предложения
                            if '. ' in line:
                                first_sentence_end = line.find('. ')
                                line = line[:first_sentence_end] + ' [1]' + line[first_sentence_end:]
                            else:
                                line = line.rstrip() + ' [1]'
                            logger.debug(f"Добавлен [1] к первому предложению: {line}")
                    
                    modified_lines.append(line)
                
                content = '\n'.join(modified_lines)
            
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
                "model": "sonar-pro",
                "messages": [
                    {
                        "role": "user",
                        "content": "Привет! Это тестовый запрос."
                    }
                ],
                "max_tokens": 50
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