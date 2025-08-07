"""
Icon Mapper для NEWSMAKER
Маппинг эмодзи на современные иконки и текстовые символы
"""

from typing import Dict, Optional, Tuple
from enum import Enum


class IconStyle(Enum):
    """Стили отображения иконок"""
    EMOJI = "emoji"          # Оригинальные эмодзи
    TEXT = "text"            # Текстовые символы
    RICH = "rich"            # Rich library форматирование
    HTML = "html"            # HTML иконки
    UNICODE = "unicode"      # Unicode символы


class IconMapper:
    """Класс для маппинга эмодзи на различные форматы"""
    
    def __init__(self, style: IconStyle = IconStyle.TEXT):
        self.style = style
        
        # Маппинг эмодзи на различные представления
        self.icon_map = {
            '⚙️': {
                'text': '[CONFIG]',
                'rich': '[bold cyan]⚙[/bold cyan]',
                'html': '<i data-lucide="settings" class="icon icon-primary"></i>',
                'unicode': '⚙',
                'description': 'Настройки'
            },
            '🔧': {
                'text': '[TOOLS]',
                'rich': '[bold yellow]🔧[/bold yellow]',
                'html': '<i data-lucide="wrench" class="icon icon-secondary"></i>',
                'unicode': '🔧',
                'description': 'Инструменты'
            },
            '🚀': {
                'text': '[START]',
                'rich': '[bold green]→[/bold green]',
                'html': '<i data-lucide="rocket" class="icon icon-success"></i>',
                'unicode': '→',
                'description': 'Запуск'
            },
            '📊': {
                'text': '[STATS]',
                'rich': '[bold blue]█[/bold blue]',
                'html': '<i data-lucide="bar-chart-3" class="icon icon-info"></i>',
                'unicode': '█',
                'description': 'Статистика'
            },
            '📝': {
                'text': '[LOG]',
                'rich': '[dim]▪[/dim]',
                'html': '<i data-lucide="file-text" class="icon icon-primary"></i>',
                'unicode': '▪',
                'description': 'Лог'
            },
            '💬': {
                'text': '[MSG]',
                'rich': '[bold]◆[/bold]',
                'html': '<i data-lucide="message-circle" class="icon icon-secondary"></i>',
                'unicode': '◆',
                'description': 'Сообщение'
            },
            '⏰': {
                'text': '[TIME]',
                'rich': '[yellow]◉[/yellow]',
                'html': '<i data-lucide="clock" class="icon icon-warning"></i>',
                'unicode': '◉',
                'description': 'Время'
            },
            '💾': {
                'text': '[SAVE]',
                'rich': '[green]▼[/green]',
                'html': '<i data-lucide="save" class="icon icon-success"></i>',
                'unicode': '▼',
                'description': 'Сохранение'
            },
            '🔍': {
                'text': '[SEARCH]',
                'rich': '[cyan]◎[/cyan]',
                'html': '<i data-lucide="search" class="icon icon-info"></i>',
                'unicode': '◎',
                'description': 'Поиск'
            },
            '📰': {
                'text': '[NEWS]',
                'rich': '[bold]▣[/bold]',
                'html': '<i data-lucide="newspaper" class="icon icon-dark"></i>',
                'unicode': '▣',
                'description': 'Новости'
            },
            '✨': {
                'text': '[NEW]',
                'rich': '[bright_yellow]★[/bright_yellow]',
                'html': '<i data-lucide="sparkles" class="icon icon-warning"></i>',
                'unicode': '★',
                'description': 'Новое'
            },
            '🎨': {
                'text': '[ART]',
                'rich': '[magenta]◈[/magenta]',
                'html': '<i data-lucide="palette" class="icon icon-gradient"></i>',
                'unicode': '◈',
                'description': 'Дизайн'
            },
            '✅': {
                'text': '[OK]',
                'rich': '[bold green]✓[/bold green]',
                'html': '<i data-lucide="check-circle" class="icon icon-success"></i>',
                'unicode': '✓',
                'description': 'Успешно'
            },
            '❌': {
                'text': '[ERROR]',
                'rich': '[bold red]✗[/bold red]',
                'html': '<i data-lucide="x-circle" class="icon icon-danger"></i>',
                'unicode': '✗',
                'description': 'Ошибка'
            },
            '🎉': {
                'text': '[SUCCESS]',
                'rich': '[bold bright_green]♦[/bold bright_green]',
                'html': '<i data-lucide="party-popper" class="icon icon-success"></i>',
                'unicode': '♦',
                'description': 'Празднование'
            },
            '🛑': {
                'text': '[STOP]',
                'rich': '[bold red]■[/bold red]',
                'html': '<i data-lucide="octagon" class="icon icon-danger"></i>',
                'unicode': '■',
                'description': 'Стоп'
            },
            '⏹️': {
                'text': '[PAUSE]',
                'rich': '[dim]▪[/dim]',
                'html': '<i data-lucide="square" class="icon icon-muted"></i>',
                'unicode': '▪',
                'description': 'Пауза'
            },
            '💥': {
                'text': '[CRITICAL]',
                'rich': '[bold bright_red]![/bold bright_red]',
                'html': '<i data-lucide="zap" class="icon icon-danger"></i>',
                'unicode': '!',
                'description': 'Критично'
            },
            '🧪': {
                'text': '[TEST]',
                'rich': '[cyan]◊[/cyan]',
                'html': '<i data-lucide="flask" class="icon icon-info"></i>',
                'unicode': '◊',
                'description': 'Тест'
            }
        }
        
        # Цветовые коды для консоли
        self.colors = {
            'reset': '\033[0m',
            'bold': '\033[1m',
            'dim': '\033[2m',
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m'
        }
    
    def get_icon(self, emoji: str, style: Optional[IconStyle] = None) -> str:
        """
        Получить иконку в нужном стиле
        
        Args:
            emoji: Эмодзи для замены
            style: Стиль отображения (если не указан, используется дефолтный)
            
        Returns:
            Строка с иконкой в нужном формате
        """
        current_style = style or self.style
        
        if current_style == IconStyle.EMOJI:
            return emoji
        
        if emoji not in self.icon_map:
            return emoji  # Возвращаем оригинал если нет маппинга
        
        style_key = current_style.value
        if style_key in self.icon_map[emoji]:
            return self.icon_map[emoji][style_key]
        
        # Fallback на текстовый вариант
        return self.icon_map[emoji].get('text', emoji)
    
    def replace_all_emojis(self, text: str, style: Optional[IconStyle] = None) -> str:
        """
        Заменить все эмодзи в тексте
        
        Args:
            text: Текст с эмодзи
            style: Стиль замены
            
        Returns:
            Текст с замененными иконками
        """
        result = text
        for emoji in self.icon_map.keys():
            if emoji in result:
                result = result.replace(emoji, self.get_icon(emoji, style))
        return result
    
    def get_colored_icon(self, emoji: str, color: str = 'green') -> str:
        """
        Получить цветную иконку для консоли
        
        Args:
            emoji: Эмодзи
            color: Цвет (red, green, yellow, blue, magenta, cyan)
            
        Returns:
            Цветная иконка для консоли
        """
        icon = self.get_icon(emoji, IconStyle.UNICODE)
        if color in self.colors:
            return f"{self.colors[color]}{self.colors['bold']}{icon}{self.colors['reset']}"
        return icon
    
    def get_status_icon(self, status: str) -> Tuple[str, str]:
        """
        Получить иконку для статуса
        
        Args:
            status: Статус (success, error, warning, info, pending)
            
        Returns:
            Кортеж (иконка, цвет)
        """
        status_map = {
            'success': ('✅', 'green'),
            'error': ('❌', 'red'),
            'warning': ('⏰', 'yellow'),
            'info': ('📊', 'blue'),
            'pending': ('⏰', 'yellow'),
            'critical': ('💥', 'red'),
            'start': ('🚀', 'green'),
            'stop': ('🛑', 'red')
        }
        
        if status in status_map:
            emoji, color = status_map[status]
            return self.get_colored_icon(emoji, color), color
        
        return self.get_icon('📝'), 'white'
    
    def format_for_rich(self, text: str) -> str:
        """
        Форматировать текст для Rich library
        
        Args:
            text: Текст с эмодзи
            
        Returns:
            Форматированный текст для Rich
        """
        return self.replace_all_emojis(text, IconStyle.RICH)
    
    def format_for_html(self, text: str) -> str:
        """
        Форматировать текст для HTML
        
        Args:
            text: Текст с эмодзи
            
        Returns:
            HTML с иконками
        """
        return self.replace_all_emojis(text, IconStyle.HTML)
    
    def strip_all_icons(self, text: str) -> str:
        """
        Удалить все иконки из текста
        
        Args:
            text: Текст с иконками
            
        Returns:
            Чистый текст
        """
        result = text
        for emoji in self.icon_map.keys():
            result = result.replace(emoji, '')
        
        # Удаляем текстовые маркеры
        for icon_data in self.icon_map.values():
            if 'text' in icon_data:
                result = result.replace(icon_data['text'], '')
        
        return result.strip()


# Глобальный экземпляр маппера
icon_mapper = IconMapper()


# Удобные функции для быстрого доступа
def get_icon(emoji: str, style: IconStyle = IconStyle.TEXT) -> str:
    """Получить иконку в нужном стиле"""
    return icon_mapper.get_icon(emoji, style)


def replace_emojis(text: str, style: IconStyle = IconStyle.TEXT) -> str:
    """Заменить все эмодзи в тексте"""
    return icon_mapper.replace_all_emojis(text, style)


def get_status_icon(status: str) -> Tuple[str, str]:
    """Получить иконку для статуса"""
    return icon_mapper.get_status_icon(status)


def strip_icons(text: str) -> str:
    """Удалить все иконки из текста"""
    return icon_mapper.strip_all_icons(text)


if __name__ == "__main__":
    # Тестирование
    mapper = IconMapper()
    
    test_text = "🚀 Запуск системы... ✅ Успешно! 📊 Статистика загружена."
    
    print("Оригинал:", test_text)
    print("TEXT:", mapper.replace_all_emojis(test_text, IconStyle.TEXT))
    print("UNICODE:", mapper.replace_all_emojis(test_text, IconStyle.UNICODE))
    print("RICH:", mapper.replace_all_emojis(test_text, IconStyle.RICH))
    print("Без иконок:", mapper.strip_all_icons(test_text))