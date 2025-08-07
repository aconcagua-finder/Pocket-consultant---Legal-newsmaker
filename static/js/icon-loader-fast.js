/**
 * Fast Icon System for NEWSMAKER - БЕЗ ВНЕШНИХ ЗАВИСИМОСТЕЙ
 * Использует только Font Awesome, который уже загружен
 */

class FastIconSystem {
    constructor() {
        // Маппинг эмодзи на Font Awesome иконки
        this.iconMap = {
            '⚙️': 'fa-gear',
            '🔧': 'fa-wrench',
            '🚀': 'fa-rocket',
            '📊': 'fa-chart-bar',
            '📝': 'fa-file-text',
            '💬': 'fa-comment',
            '⏰': 'fa-clock',
            '💾': 'fa-save',
            '🔍': 'fa-search',
            '📰': 'fa-newspaper',
            '✨': 'fa-sparkles',
            '🎨': 'fa-palette',
            '✅': 'fa-circle-check',
            '❌': 'fa-circle-xmark',
            '🎉': 'fa-champagne-glasses',
            '🛑': 'fa-stop',
            '⏹️': 'fa-square',
            '💥': 'fa-bolt',
            '🧪': 'fa-flask'
        };
        
        // Маппинг на цвета
        this.colorMap = {
            '⚙️': 'icon-primary',
            '🚀': 'icon-success',
            '📊': 'icon-info',
            '✅': 'icon-success',
            '❌': 'icon-danger',
            '⏰': 'icon-warning',
            '💥': 'icon-danger'
        };
        
        // Инициализация при загрузке
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }
    
    init() {
        // Заменяем эмодзи в заголовке страницы
        this.replacePageTitle();
        
        // Заменяем эмодзи в тексте
        this.replaceAllEmojis();
    }
    
    replacePageTitle() {
        // Заменяем эмодзи в title
        const title = document.querySelector('title');
        if (title && title.textContent.includes('⚙️')) {
            title.textContent = title.textContent.replace('⚙️', '');
        }
    }
    
    createIcon(emoji) {
        const faClass = this.iconMap[emoji];
        const colorClass = this.colorMap[emoji] || 'icon-primary';
        
        if (!faClass) return emoji;
        
        // Создаём элемент иконки
        const icon = document.createElement('i');
        icon.className = `fas ${faClass} icon ${colorClass}`;
        return icon;
    }
    
    replaceAllEmojis() {
        // Находим все текстовые узлы
        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: (node) => {
                    // Пропускаем скрипты и стили
                    const parent = node.parentElement;
                    if (parent && (parent.tagName === 'SCRIPT' || parent.tagName === 'STYLE')) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    
                    // Проверяем, есть ли эмодзи
                    for (const emoji of Object.keys(this.iconMap)) {
                        if (node.textContent.includes(emoji)) {
                            return NodeFilter.FILTER_ACCEPT;
                        }
                    }
                    return NodeFilter.FILTER_REJECT;
                }
            }
        );
        
        const nodesToReplace = [];
        while (walker.nextNode()) {
            nodesToReplace.push(walker.currentNode);
        }
        
        // Заменяем эмодзи на иконки
        nodesToReplace.forEach(node => {
            const parent = node.parentElement;
            let text = node.textContent;
            
            // Проверяем каждый эмодзи
            for (const [emoji, faClass] of Object.entries(this.iconMap)) {
                if (text.includes(emoji)) {
                    // Разбиваем текст по эмодзи
                    const parts = text.split(emoji);
                    
                    // Создаём новый контейнер
                    const container = document.createElement('span');
                    
                    parts.forEach((part, index) => {
                        if (part) {
                            container.appendChild(document.createTextNode(part));
                        }
                        
                        // Добавляем иконку между частями (кроме последней)
                        if (index < parts.length - 1) {
                            const icon = this.createIcon(emoji);
                            if (icon instanceof HTMLElement) {
                                container.appendChild(icon);
                            } else {
                                container.appendChild(document.createTextNode(icon));
                            }
                        }
                    });
                    
                    // Заменяем текстовый узел на контейнер
                    parent.replaceChild(container, node);
                    break;
                }
            }
        });
    }
    
    // Методы для программного добавления иконок
    addIcon(element, iconName, options = {}) {
        const { size = 'md', color = 'primary', animation = '' } = options;
        
        const icon = document.createElement('i');
        icon.className = `fas fa-${iconName} icon icon-${size} icon-${color} ${animation}`;
        
        element.appendChild(icon);
        return icon;
    }
    
    createStatusIcon(status, text) {
        const statusIcons = {
            'success': 'circle-check',
            'error': 'circle-xmark',
            'warning': 'triangle-exclamation',
            'info': 'circle-info',
            'loading': 'spinner'
        };
        
        const statusColors = {
            'success': 'success',
            'error': 'danger',
            'warning': 'warning',
            'info': 'info',
            'loading': 'primary'
        };
        
        const iconName = statusIcons[status] || 'circle-info';
        const color = statusColors[status] || 'info';
        const animation = status === 'loading' ? 'icon-spin' : '';
        
        const container = document.createElement('div');
        container.className = `status-icon status-${status}`;
        container.innerHTML = `
            <i class="fas fa-${iconName} icon icon-${color} ${animation}"></i>
            <span>${text}</span>
        `;
        
        return container;
    }
}

// Автоматическая инициализация
const iconSystem = new FastIconSystem();

// Экспорт для использования
window.FastIconSystem = FastIconSystem;
window.iconSystem = iconSystem;