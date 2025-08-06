"""
Типы данных и модели для NEWSMAKER

Этот модуль содержит типизированные структуры данных
для улучшения безопасности типов и IDE поддержки.
"""

from typing import TypedDict, Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# ========================================================================
# ENUMS - Перечисления
# ========================================================================

class NewsPriority(Enum):
    """Приоритеты новостей"""
    CRITICAL = 1  # Критически важно
    VERY_HIGH = 2  # Очень важно
    HIGH = 3       # Важно
    MEDIUM = 4     # Средняя важность
    MODERATE = 5   # Умеренная важность
    ADDITIONAL = 6 # Дополнительная
    LOW = 7        # Низкая важность


class PublicationStatus(Enum):
    """Статус публикации"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PUBLISHED = "published"
    FAILED = "failed"
    SKIPPED = "skipped"


class JobStatus(Enum):
    """Статус выполнения задачи"""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ========================================================================
# TYPED DICTS - Типизированные словари
# ========================================================================

class NewsItem(TypedDict):
    """Структура одной новости"""
    id: str
    priority: int
    title: str
    content: str
    sources: List[str]
    scheduled_time: str
    collected_at: str
    published: bool
    publication_attempts: int
    published_at: Optional[str]
    image_path: Optional[str]
    image_generated: bool
    image_size: Optional[int]
    image_error: Optional[str]


class NewsFileData(TypedDict):
    """Структура файла с новостями за день"""
    date: str
    collected_at: str
    total_news: int
    news: List[NewsItem]


class TelegramMessage(TypedDict):
    """Структура сообщения для Telegram"""
    content: str
    sources: List[str]


class MessageHistoryItem(TypedDict):
    """Элемент истории сообщений"""
    hash: str
    timestamp: str
    preview: str


class PublicationResult(TypedDict):
    """Результат публикации новости"""
    success: bool
    reason: Optional[str]
    message: Optional[str]
    news_id: Optional[str]
    priority: Optional[int]
    scheduled_time: Optional[str]
    title: Optional[str]
    remaining_news: Optional[int]
    attempts: Optional[int]


class BatchPublicationResult(TypedDict):
    """Результат пакетной публикации"""
    success: bool
    total_news: int
    successful_count: int
    failed_count: int
    success_rate: float
    results: List[Dict[str, Any]]
    reason: Optional[str]
    message: Optional[str]


class NewsFileStatus(TypedDict):
    """Статус файла новостей"""
    exists: bool
    date: str
    file_path: str
    collected_at: Optional[str]
    total_news: Optional[int]
    news_count: Optional[int]
    published_count: Optional[int]
    error: Optional[str]


class PublicationStatusReport(TypedDict):
    """Статус публикаций за день (отчет)"""
    date: str
    file_exists: bool
    total_news: Optional[int]
    published_count: Optional[int]
    unpublished_count: Optional[int]
    collection_time: Optional[str]
    news_details: Optional[List[Dict[str, Any]]]
    error: Optional[str]


class ConfigStatus(TypedDict):
    """Статус конфигурации системы"""
    api_keys: Dict[str, bool]
    schedule: Dict[str, Any]
    storage: Dict[str, Any]
    modes: Dict[str, bool]


class NextNewsData(TypedDict):
    """Данные следующей новости для публикации"""
    file_date: datetime
    news_item: NewsItem
    total_unpublished: int


class APIResponse(TypedDict):
    """Общий ответ от API"""
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    status_code: Optional[int]


class PerplexityResponse(TypedDict):
    """Ответ от Perplexity API"""
    content: str
    sources: List[str]


class ImageGenerationResult(TypedDict):
    """Результат генерации изображения"""
    success: bool
    image_bytes: Optional[bytes]
    error: Optional[str]
    size: Optional[int]
    model: Optional[str]


# ========================================================================
# VALIDATION SCHEMAS - Схемы валидации
# ========================================================================

class NewsContentValidation(TypedDict):
    """Параметры валидации контента новости"""
    min_length: int
    max_length: int
    required_fields: List[str]
    max_sources: int
    allowed_priorities: List[int]


class TimeSlotValidation(TypedDict):
    """Валидация временного слота"""
    time: str  # HH:MM format
    priority: int
    is_valid: bool
    error: Optional[str]


# ========================================================================
# SYSTEM STATES - Состояния системы
# ========================================================================

class SystemState(TypedDict):
    """Общее состояние системы"""
    is_running: bool
    last_collection: Optional[str]
    last_publication: Optional[str]
    pending_publications: int
    errors_count: int
    warnings_count: int
    uptime_seconds: float


class SchedulerState(TypedDict):
    """Состояние планировщика"""
    is_active: bool
    next_collection: Optional[str]
    next_publication: Optional[str]
    jobs_in_queue: int
    architecture: Literal["new", "legacy"]


# ========================================================================
# ERROR TYPES - Типы ошибок
# ========================================================================

class ErrorInfo(TypedDict):
    """Информация об ошибке"""
    error_type: str
    message: str
    timestamp: str
    module: str
    traceback: Optional[str]
    retry_count: int
    is_critical: bool


class ValidationError(TypedDict):
    """Ошибка валидации"""
    field: str
    value: Any
    expected: str
    message: str


# ========================================================================
# HELPER FUNCTIONS - Вспомогательные функции
# ========================================================================

def create_empty_news_item() -> NewsItem:
    """
    Создает пустую структуру новости с дефолтными значениями
    
    Returns:
        NewsItem: Пустая новость
    """
    return NewsItem(
        id="",
        priority=7,
        title="",
        content="",
        sources=[],
        scheduled_time="",
        collected_at=datetime.now().isoformat(),
        published=False,
        publication_attempts=0,
        published_at=None,
        image_path=None,
        image_generated=False,
        image_size=None,
        image_error=None
    )


def validate_news_item(item: Dict[str, Any]) -> bool:
    """
    Валидирует структуру новости
    
    Args:
        item: Словарь с данными новости
        
    Returns:
        bool: True если структура валидна
    """
    required_fields = ['id', 'priority', 'title', 'content', 'sources']
    
    for field in required_fields:
        if field not in item:
            return False
    
    # Проверяем типы
    if not isinstance(item.get('priority'), int):
        return False
    
    if not isinstance(item.get('sources'), list):
        return False
    
    if not isinstance(item.get('published'), bool):
        return False
    
    # Проверяем диапазоны
    if not 1 <= item.get('priority', 0) <= 7:
        return False
    
    return True


def convert_priority_to_enum(priority: int) -> NewsPriority:
    """
    Преобразует числовой приоритет в enum
    
    Args:
        priority: Числовой приоритет (1-7)
        
    Returns:
        NewsPriority: Enum значение приоритета
    """
    priority_map = {
        1: NewsPriority.CRITICAL,
        2: NewsPriority.VERY_HIGH,
        3: NewsPriority.HIGH,
        4: NewsPriority.MEDIUM,
        5: NewsPriority.MODERATE,
        6: NewsPriority.ADDITIONAL,
        7: NewsPriority.LOW
    }
    
    return priority_map.get(priority, NewsPriority.LOW)


def get_priority_description(priority: NewsPriority) -> str:
    """
    Возвращает описание приоритета на русском
    
    Args:
        priority: Enum приоритета
        
    Returns:
        str: Описание приоритета
    """
    descriptions = {
        NewsPriority.CRITICAL: "Критически важно",
        NewsPriority.VERY_HIGH: "Очень важно",
        NewsPriority.HIGH: "Важно",
        NewsPriority.MEDIUM: "Средняя важность",
        NewsPriority.MODERATE: "Умеренная важность",
        NewsPriority.ADDITIONAL: "Дополнительная",
        NewsPriority.LOW: "Низкая важность"
    }
    
    return descriptions.get(priority, "Неизвестный приоритет")