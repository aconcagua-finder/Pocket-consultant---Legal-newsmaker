/**
 * Modern Icon Loader for NEWSMAKER
 * Динамическая загрузка и управление иконками
 */

class IconLoader {
    constructor() {
        this.iconLibraries = {
            lucide: 'https://unpkg.com/lucide@latest',
            phosphor: 'https://unpkg.com/@phosphor-icons/web@2.0.3',
            tabler: 'https://unpkg.com/@tabler/icons@latest/icons',
            heroicons: 'https://unpkg.com/heroicons@2.0.18'
        };
        
        // Маппинг эмодзи на современные иконки
        this.emojiToIcon = {
            '⚙️': { icon: 'settings', library: 'lucide', class: 'icon-primary' },
            '🔧': { icon: 'wrench', library: 'lucide', class: 'icon-secondary' },
            '🚀': { icon: 'rocket', library: 'lucide', class: 'icon-success' },
            '📊': { icon: 'bar-chart-3', library: 'lucide', class: 'icon-info' },
            '📝': { icon: 'file-text', library: 'lucide', class: 'icon-primary' },
            '💬': { icon: 'message-circle', library: 'lucide', class: 'icon-secondary' },
            '⏰': { icon: 'clock', library: 'lucide', class: 'icon-warning' },
            '💾': { icon: 'save', library: 'lucide', class: 'icon-success' },
            '🔍': { icon: 'search', library: 'lucide', class: 'icon-info' },
            '📰': { icon: 'newspaper', library: 'lucide', class: 'icon-dark' },
            '✨': { icon: 'sparkles', library: 'lucide', class: 'icon-warning' },
            '🎨': { icon: 'palette', library: 'lucide', class: 'icon-gradient' },
            '✅': { icon: 'check-circle', library: 'lucide', class: 'icon-success' },
            '❌': { icon: 'x-circle', library: 'lucide', class: 'icon-danger' },
            '🎉': { icon: 'party-popper', library: 'lucide', class: 'icon-success' },
            '🛑': { icon: 'octagon', library: 'lucide', class: 'icon-danger' },
            '⏹️': { icon: 'square', library: 'lucide', class: 'icon-muted' },
            '💥': { icon: 'zap', library: 'lucide', class: 'icon-danger' },
            '🧪': { icon: 'flask', library: 'lucide', class: 'icon-info' }
        };
        
        this.init();
    }
    
    init() {
        // Загружаем Lucide Icons
        this.loadLucideIcons();
        
        // Заменяем все эмодзи на странице
        this.replaceAllEmojis();
        
        // Добавляем observer для динамического контента
        this.observeChanges();
    }
    
    loadLucideIcons() {
        // Проверяем, не загружены ли уже иконки
        if (!window.lucide) {
            const script = document.createElement('script');
            script.src = 'https://unpkg.com/lucide@latest/dist/umd/lucide.js';
            script.onload = () => {
                if (window.lucide) {
                    window.lucide.createIcons();
                }
            };
            document.head.appendChild(script);
        }
    }
    
    createIcon(iconName, className = '', size = 20) {
        // Создаём SVG иконку
        const iconHTML = `
            <i data-lucide="${iconName}" 
               class="icon ${className}" 
               width="${size}" 
               height="${size}">
            </i>
        `;
        return iconHTML;
    }
    
    replaceEmoji(text) {
        // Заменяем эмодзи на иконки в тексте
        let result = text;
        
        for (const [emoji, config] of Object.entries(this.emojiToIcon)) {
            const iconHTML = this.createIcon(config.icon, config.class);
            result = result.replace(new RegExp(emoji, 'g'), iconHTML);
        }
        
        return result;
    }
    
    replaceAllEmojis() {
        // Находим все текстовые узлы и заменяем эмодзи
        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );
        
        const nodesToReplace = [];
        while (walker.nextNode()) {
            const node = walker.currentNode;
            if (this.containsEmoji(node.textContent)) {
                nodesToReplace.push(node);
            }
        }
        
        nodesToReplace.forEach(node => {
            const span = document.createElement('span');
            span.innerHTML = this.replaceEmoji(node.textContent);
            node.parentNode.replaceChild(span, node);
        });
        
        // Обновляем Lucide иконки
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }
    
    containsEmoji(text) {
        // Проверяем, содержит ли текст эмодзи из нашего списка
        return Object.keys(this.emojiToIcon).some(emoji => text.includes(emoji));
    }
    
    observeChanges() {
        // Наблюдаем за изменениями DOM для динамического контента
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList') {
                    mutation.addedNodes.forEach((node) => {
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            this.processNode(node);
                        }
                    });
                }
            });
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }
    
    processNode(node) {
        // Обрабатываем новый узел
        const walker = document.createTreeWalker(
            node,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );
        
        while (walker.nextNode()) {
            const textNode = walker.currentNode;
            if (this.containsEmoji(textNode.textContent)) {
                const span = document.createElement('span');
                span.innerHTML = this.replaceEmoji(textNode.textContent);
                textNode.parentNode.replaceChild(span, textNode);
            }
        }
        
        // Обновляем иконки
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }
    
    // Методы для программного добавления иконок
    addIcon(element, iconName, options = {}) {
        const {
            size = 20,
            color = '',
            className = '',
            animation = '',
            tooltip = ''
        } = options;
        
        const iconElement = document.createElement('i');
        iconElement.setAttribute('data-lucide', iconName);
        iconElement.className = `icon ${className} ${animation}`;
        
        if (color) {
            iconElement.style.color = color;
        }
        
        if (tooltip) {
            iconElement.className += ' icon-tooltip';
            iconElement.setAttribute('data-tooltip', tooltip);
        }
        
        iconElement.setAttribute('width', size);
        iconElement.setAttribute('height', size);
        
        element.appendChild(iconElement);
        
        if (window.lucide) {
            window.lucide.createIcons();
        }
        
        return iconElement;
    }
    
    // Анимированная иконка загрузки
    createLoadingIcon(text = 'Загрузка...') {
        return `
            <div class="icon-group">
                <i data-lucide="loader-2" class="icon icon-spin icon-primary"></i>
                <span>${text}</span>
            </div>
        `;
    }
    
    // Иконка со статусом
    createStatusIcon(status, text) {
        const statusConfig = {
            'success': { icon: 'check-circle', class: 'icon-success' },
            'error': { icon: 'x-circle', class: 'icon-danger' },
            'warning': { icon: 'alert-triangle', class: 'icon-warning' },
            'info': { icon: 'info', class: 'icon-info' },
            'pending': { icon: 'clock', class: 'icon-warning icon-pulse' }
        };
        
        const config = statusConfig[status] || statusConfig['info'];
        
        return `
            <div class="status-icon status-${status}">
                <i data-lucide="${config.icon}" class="icon ${config.class}"></i>
                <span>${text}</span>
            </div>
        `;
    }
    
    // Иконка с бэйджем
    createBadgeIcon(iconName, badgeCount, options = {}) {
        const { color = 'primary' } = options;
        
        return `
            <div class="icon-badge">
                <i data-lucide="${iconName}" class="icon icon-${color}"></i>
                ${badgeCount > 0 ? `<span class="badge">${badgeCount > 99 ? '99+' : badgeCount}</span>` : ''}
            </div>
        `;
    }
}

// Инициализируем загрузчик иконок при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    window.iconLoader = new IconLoader();
});

// Экспортируем для использования в других скриптах
if (typeof module !== 'undefined' && module.exports) {
    module.exports = IconLoader;
}