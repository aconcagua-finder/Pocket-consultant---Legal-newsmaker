"""
Модуль для асинхронной обработки операций в NEWSMAKER

Обеспечивает параллельное выполнение операций для повышения производительности.
"""

import asyncio
import aiohttp
# import httpx  # Удален - не используется в текущей версии
from typing import List, Dict, Any, Optional, Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from loguru import logger
import time

import config
# Retry логика теперь в error_handler
from error_handler import retry_on_error, calculate_backoff_time, is_retryable_error
from cache_manager import cache_api_response


# ========================================================================
# КОНФИГУРАЦИЯ АСИНХРОННЫХ ОПЕРАЦИЙ
# ========================================================================

# Максимальное количество одновременных соединений
MAX_CONCURRENT_CONNECTIONS = 10

# Максимальное количество воркеров в пуле потоков
MAX_THREAD_WORKERS = 5

# Таймауты для различных операций
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)
API_TIMEOUT = aiohttp.ClientTimeout(total=60)
IMAGE_TIMEOUT = aiohttp.ClientTimeout(total=120)


# ========================================================================
# АСИНХРОННЫЕ HTTP КЛИЕНТЫ
# ========================================================================

class AsyncHTTPClient:
    """Асинхронный HTTP клиент с поддержкой retry и rate limiting"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.session: Optional[aiohttp.ClientSession] = None
        self.connector = None
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_CONNECTIONS)
    
    async def __aenter__(self):
        """Вход в контекстный менеджер"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекстного менеджера"""
        await self.close()
    
    async def start(self):
        """Инициализирует сессию"""
        if not self.session:
            self.connector = aiohttp.TCPConnector(
                limit=MAX_CONCURRENT_CONNECTIONS,
                limit_per_host=5,
                ttl_dns_cache=300
            )
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=DEFAULT_TIMEOUT
            )
    
    async def close(self):
        """Закрывает сессию"""
        if self.session:
            await self.session.close()
            self.session = None
        if self.connector:
            await self.connector.close()
            self.connector = None
    
    async def request_with_retry(
        self,
        method: str,
        url: str,
        headers: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        timeout: Optional[aiohttp.ClientTimeout] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Выполняет HTTP запрос с повторными попытками
        
        Args:
            method: HTTP метод
            url: URL для запроса
            headers: Заголовки запроса
            json_data: JSON данные для отправки
            timeout: Таймаут запроса
            **kwargs: Дополнительные параметры
            
        Returns:
            Dict с результатом запроса
        """
        if not self.session:
            await self.start()
        
        timeout = timeout or DEFAULT_TIMEOUT
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                async with self.semaphore:  # Ограничиваем количество одновременных запросов
                    async with self.session.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=json_data,
                        timeout=timeout,
                        **kwargs
                    ) as response:
                        # Проверяем rate limiting
                        if response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', 60))
                            logger.warning(f"Rate limit достигнут, ожидание {retry_after} сек")
                            await asyncio.sleep(retry_after)
                            continue
                        
                        response.raise_for_status()
                        
                        # Возвращаем результат
                        return {
                            'status': response.status,
                            'headers': dict(response.headers),
                            'data': await response.json() if response.content_type == 'application/json' else await response.text(),
                            'content': await response.read() if response.content_type.startswith('image/') else None
                        }
                        
            except Exception as e:
                last_exception = e
                
                if not is_retryable_error(e) or attempt >= self.max_retries:
                    logger.error(f"Ошибка запроса {url}: {e}")
                    raise
                
                # Вычисляем время ожидания
                wait_time = calculate_backoff_time(attempt)
                logger.warning(f"Попытка {attempt}/{self.max_retries} неудачна, повтор через {wait_time:.1f} сек")
                await asyncio.sleep(wait_time)
        
        if last_exception:
            raise last_exception


# ========================================================================
# АСИНХРОННЫЕ ОПЕРАЦИИ С API
# ========================================================================

class AsyncAPIOperations:
    """Класс для асинхронных операций с различными API"""
    
    def __init__(self):
        self.http_client = AsyncHTTPClient()
    
    async def __aenter__(self):
        await self.http_client.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.close()
    
    async def fetch_perplexity_news(self, prompt: str) -> Optional[Dict]:
        """
        Асинхронно получает новости от Perplexity API
        
        Args:
            prompt: Промпт для генерации
            
        Returns:
            Dict с ответом или None при ошибке
        """
        headers = {
            "Authorization": f"Bearer {config.PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": config.PERPLEXITY_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8192,
            "temperature": 0.7
        }
        
        try:
            result = await self.http_client.request_with_retry(
                method="POST",
                url=config.PERPLEXITY_API_URL,
                headers=headers,
                json_data=payload,
                timeout=API_TIMEOUT
            )
            return result.get('data')
        except Exception as e:
            logger.error(f"Ошибка при запросе к Perplexity: {e}")
            return None
    
    async def generate_image_async(self, prompt: str) -> Optional[bytes]:
        """
        Асинхронно генерирует изображение через OpenAI
        
        Args:
            prompt: Промпт для генерации
            
        Returns:
            bytes изображения или None при ошибке
        """
        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": config.OPENAI_IMAGE_MODEL,
            "prompt": prompt,
            "size": "1536x1024",
            "quality": "medium",
            "n": 1
        }
        
        try:
            # Генерируем изображение
            result = await self.http_client.request_with_retry(
                method="POST",
                url="https://api.openai.com/v1/images/generations",
                headers=headers,
                json_data=payload,
                timeout=IMAGE_TIMEOUT
            )
            
            data = result.get('data')
            if data and 'data' in data and len(data['data']) > 0:
                image_url = data['data'][0].get('url')
                if image_url:
                    # Загружаем изображение
                    image_result = await self.http_client.request_with_retry(
                        method="GET",
                        url=image_url,
                        timeout=aiohttp.ClientTimeout(total=30)
                    )
                    return image_result.get('content')
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при генерации изображения: {e}")
            return None
    
    async def send_telegram_message_async(
        self,
        text: str,
        image: Optional[bytes] = None
    ) -> bool:
        """
        Асинхронно отправляет сообщение в Telegram
        
        Args:
            text: Текст сообщения
            image: Изображение (опционально)
            
        Returns:
            bool: Успешность отправки
        """
        bot_token = config.TELEGRAM_BOT_TOKEN
        chat_id = config.TELEGRAM_CHANNEL_ID
        
        if image:
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            
            # Формируем multipart data
            data = aiohttp.FormData()
            data.add_field('chat_id', str(chat_id))
            data.add_field('caption', text[:1024])  # Telegram ограничение
            data.add_field('photo', image, filename='image.png', content_type='image/png')
            
            try:
                async with self.http_client.session.post(url, data=data) as response:
                    return response.status == 200
            except Exception as e:
                logger.error(f"Ошибка отправки в Telegram: {e}")
                return False
        else:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': text[:4096],  # Telegram ограничение
                'parse_mode': 'HTML'
            }
            
            try:
                result = await self.http_client.request_with_retry(
                    method="POST",
                    url=url,
                    json_data=payload
                )
                return result.get('status') == 200
            except Exception as e:
                logger.error(f"Ошибка отправки в Telegram: {e}")
                return False


# ========================================================================
# ПАРАЛЛЕЛЬНАЯ ОБРАБОТКА
# ========================================================================

class ParallelProcessor:
    """Класс для параллельной обработки множественных операций"""
    
    def __init__(self, max_workers: int = MAX_THREAD_WORKERS):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.loop = None
    
    async def process_batch_async(
        self,
        tasks: List[Coroutine],
        max_concurrent: int = 5
    ) -> List[Any]:
        """
        Обрабатывает пакет асинхронных задач
        
        Args:
            tasks: Список корутин для выполнения
            max_concurrent: Максимум одновременных задач
            
        Returns:
            Список результатов
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def run_with_semaphore(task):
            async with semaphore:
                return await task
        
        results = await asyncio.gather(
            *[run_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )
        
        # Логируем ошибки
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Ошибка в задаче {i}: {result}")
        
        return results
    
    def run_async_in_thread(self, coro: Coroutine) -> Any:
        """
        Запускает асинхронную функцию в отдельном потоке
        
        Args:
            coro: Корутина для выполнения
            
        Returns:
            Результат выполнения
        """
        def run_in_new_loop():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        
        future = self.executor.submit(run_in_new_loop)
        return future.result()
    
    async def map_async(
        self,
        func: Callable,
        items: List[Any],
        max_concurrent: int = 5
    ) -> List[Any]:
        """
        Применяет функцию к списку элементов параллельно
        
        Args:
            func: Асинхронная функция для применения
            items: Список элементов
            max_concurrent: Максимум одновременных операций
            
        Returns:
            Список результатов
        """
        tasks = [func(item) for item in items]
        return await self.process_batch_async(tasks, max_concurrent)
    
    def cleanup(self):
        """Очищает ресурсы"""
        self.executor.shutdown(wait=True)


# ========================================================================
# ОПТИМИЗИРОВАННЫЕ ОПЕРАЦИИ
# ========================================================================

async def batch_generate_images(
    prompts: List[str],
    max_concurrent: int = 3
) -> List[Optional[bytes]]:
    """
    Генерирует несколько изображений параллельно
    
    Args:
        prompts: Список промптов
        max_concurrent: Максимум одновременных генераций
        
    Returns:
        Список изображений (bytes или None)
    """
    async with AsyncAPIOperations() as api:
        processor = ParallelProcessor()
        
        # Создаем задачи для генерации
        tasks = [api.generate_image_async(prompt) for prompt in prompts]
        
        # Выполняем параллельно с ограничением
        results = await processor.process_batch_async(tasks, max_concurrent)
        
        return results


async def parallel_api_requests(
    requests: List[Dict[str, Any]],
    max_concurrent: int = 5
) -> List[Any]:
    """
    Выполняет несколько API запросов параллельно
    
    Args:
        requests: Список запросов с параметрами
        max_concurrent: Максимум одновременных запросов
        
    Returns:
        Список результатов
    """
    async with AsyncHTTPClient() as client:
        tasks = []
        
        for req in requests:
            task = client.request_with_retry(
                method=req.get('method', 'GET'),
                url=req['url'],
                headers=req.get('headers'),
                json_data=req.get('json'),
                timeout=req.get('timeout', DEFAULT_TIMEOUT)
            )
            tasks.append(task)
        
        # Выполняем с ограничением параллелизма
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def run_with_limit(task):
            async with semaphore:
                return await task
        
        results = await asyncio.gather(
            *[run_with_limit(task) for task in tasks],
            return_exceptions=True
        )
        
        return results


# ========================================================================
# HELPER ФУНКЦИИ
# ========================================================================

def run_async(coro: Coroutine) -> Any:
    """
    Запускает асинхронную функцию из синхронного контекста
    
    Args:
        coro: Корутина для выполнения
        
    Returns:
        Результат выполнения
    """
    try:
        # Пробуем получить текущий event loop
        loop = asyncio.get_running_loop()
        # Если loop уже запущен, используем thread executor
        processor = ParallelProcessor()
        return processor.run_async_in_thread(coro)
    except RuntimeError:
        # Если нет запущенного loop, создаем новый
        return asyncio.run(coro)


async def measure_async_performance(
    func: Callable,
    *args,
    **kwargs
) -> tuple[Any, float]:
    """
    Измеряет время выполнения асинхронной функции
    
    Args:
        func: Функция для измерения
        *args: Позиционные аргументы
        **kwargs: Именованные аргументы
        
    Returns:
        Tuple (результат, время_выполнения)
    """
    start_time = time.perf_counter()
    result = await func(*args, **kwargs)
    elapsed = time.perf_counter() - start_time
    
    logger.debug(f"{func.__name__} выполнена за {elapsed:.2f} сек")
    return result, elapsed


# ========================================================================
# ТЕСТИРОВАНИЕ
# ========================================================================

async def test_async_operations():
    """Тестирует асинхронные операции"""
    logger.info("🧪 Тестирование асинхронных операций...")
    
    # Тест HTTP клиента
    async with AsyncHTTPClient() as client:
        try:
            result = await client.request_with_retry(
                method="GET",
                url="https://api.github.com",
                timeout=aiohttp.ClientTimeout(total=10)
            )
            logger.info(f"✅ HTTP клиент работает, статус: {result['status']}")
        except Exception as e:
            logger.error(f"❌ Ошибка HTTP клиента: {e}")
    
    # Тест параллельной обработки
    processor = ParallelProcessor()
    
    async def sample_task(n: int) -> int:
        await asyncio.sleep(0.1)
        return n * n
    
    tasks = [sample_task(i) for i in range(5)]
    results = await processor.process_batch_async(tasks, max_concurrent=3)
    
    if results == [0, 1, 4, 9, 16]:
        logger.info("✅ Параллельная обработка работает")
    else:
        logger.error(f"❌ Ошибка параллельной обработки: {results}")
    
    processor.cleanup()
    
    # Тест измерения производительности
    async def slow_function():
        await asyncio.sleep(0.5)
        return "done"
    
    result, elapsed = await measure_async_performance(slow_function)
    if 0.4 < elapsed < 0.6:
        logger.info(f"✅ Измерение производительности работает: {elapsed:.2f} сек")
    else:
        logger.error(f"❌ Ошибка измерения производительности: {elapsed:.2f} сек")
    
    logger.info("✅ Тесты асинхронных операций завершены")


if __name__ == "__main__":
    asyncio.run(test_async_operations())