/**
 * NEWSMAKER Custom Tooltip System
 * Glassmorphism tooltips with detailed descriptions
 */

class TooltipSystem {
    constructor() {
        this.tooltips = new Map();
        this.activeTooltip = null;
        this.init();
    }

    init() {
        // Define all tooltip contents
        this.tooltipData = {
            // Perplexity tooltips
            'temperature': {
                title: 'Температура (Temperature)',
                text: 'Контролирует случайность и креативность ответов модели.<br>Низкие значения дают предсказуемые результаты,<br>высокие – более творческие и разнообразные ответы.',
                example: '0.0 = максимальная точность<br>0.7 = оптимальный баланс<br>2.0 = максимальная креативность',
                type: 'info'
            },
            'top-p': {
                title: 'Top P (Nucleus Sampling)',
                text: 'Альтернативный метод контроля случайности ответов.<br>Ограничивает выбор токенов до суммарной вероятности P.<br>Используйте либо Temperature, либо Top P, не оба сразу.',
                example: '0.1 = только самые вероятные токены<br>0.9 = широкий выбор токенов<br>1.0 = все доступные токены',
                type: 'info'
            },
            'presence-penalty': {
                title: 'Presence Penalty',
                text: 'Штраф за повторение тем и концепций в тексте.<br>Положительные значения заставляют модель избегать<br>уже упомянутых тем, отрицательные – фокусироваться на них.',
                example: '-2.0 = активное повторение тем<br>0.0 = стандартное поведение<br>2.0 = максимальное разнообразие тем',
                type: 'warning'
            },
            'frequency-penalty': {
                title: 'Frequency Penalty',
                text: 'Штраф за частоту использования одинаковых токенов.<br>Снижает вероятность повторения одних и тех же слов<br>пропорционально частоте их появления в тексте.',
                example: '-2.0 = повторения слов приветствуются<br>0.0 = стандартное поведение модели<br>2.0 = максимально избегать повторов',
                type: 'warning'
            },
            'search-depth': {
                title: 'Глубина поиска',
                text: 'Определяет количество источников для анализа<br>при Deep Research. Высокая глубина даёт более<br>полные результаты, но требует больше времени.',
                example: 'Low = 10-20 источников (быстро)<br>Medium = 30-50 источников (баланс)<br>High = 100+ источников (глубокий анализ)',
                type: 'success'
            },
            'search-recency': {
                title: 'Фильтр свежести',
                text: 'Ограничивает поиск по времени публикации.<br>Полезно для получения актуальных новостей<br>и избежания устаревшей информации.',
                example: 'Hour = последний час<br>Day = последние 24 часа<br>Week = последняя неделя',
                type: 'success'
            },
            'perplexity-citations': {
                title: 'Источники цитирования',
                text: 'Возвращает ссылки на источники информации.<br>Важно для проверки фактов и обеспечения<br>достоверности новостей.',
                example: 'Включено = ссылки на источники<br>Выключено = только текст',
                type: 'info'
            },
            'perplexity-domains': {
                title: 'Фильтр доменов',
                text: 'Приоритетные домены для поиска информации.<br>Укажите надёжные источники юридических<br>новостей для повышения качества контента.',
                example: 'pravo.gov.ru<br>consultant.ru<br>garant.ru',
                type: 'info'
            },
            
            // OpenAI tooltips
            'openai-style': {
                title: 'Стиль изображения',
                text: 'Визуальный стиль для DALL-E 3.<br>Vivid создаёт яркие, насыщенные изображения.<br>Natural даёт более реалистичные результаты.',
                example: 'Vivid = художественный стиль<br>Natural = фотореалистичный',
                type: 'info'
            },
            
            // System tooltips
            'user-timezone': {
                title: 'Часовой пояс',
                text: 'Часовой пояс для планировщика задач.<br>Все времена публикаций будут<br>интерпретироваться в выбранном поясе.',
                example: 'Europe/Moscow = МСК<br>Asia/Vladivostok = МСК+7',
                type: 'warning'
            },
            
            // Schedule tooltips
            'collection-time': {
                title: 'Время сбора новостей',
                text: 'Ежедневное время запуска сбора новостей.<br>Рекомендуется раннее утро для получения<br>свежих новостей на весь день.',
                example: '08:30 = утренний сбор<br>06:00 = ранний сбор',
                type: 'success'
            },
            'publications-count': {
                title: 'Количество публикаций',
                text: 'Сколько новостей публиковать в день.<br>Больше публикаций = больше охват,<br>но выше нагрузка на аудиторию.',
                example: '7 = оптимально<br>12 = активная лента<br>24 = максимум',
                type: 'info'
            },
            
            // Content tooltips
            'generate-images': {
                title: 'Генерация комиксов',
                text: 'Создавать 4-панельные комиксы для новостей.<br>Повышает вовлечённость аудитории,<br>но увеличивает время и стоимость.',
                example: 'Время: ~3 мин/изображение<br>Цена: $0.02-$0.19',
                type: 'warning'
            },
            'publish-without-images': {
                title: 'Публикация без изображений',
                text: 'Публиковать новости даже если генерация<br>изображений не удалась. Обеспечивает<br>непрерывность публикаций.',
                example: 'Включено = надёжность<br>Выключено = только с картинками',
                type: 'info'
            }
        };

        // Initialize tooltips after DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initializeTooltips());
        } else {
            this.initializeTooltips();
        }
    }

    initializeTooltips() {
        // Remove old title attributes and add custom tooltips
        this.addTooltip('perplexity-temperature', 'temperature', 'label');
        this.addTooltip('perplexity-top-p', 'top-p', 'label');
        this.addTooltip('perplexity-presence-penalty', 'presence-penalty', 'label');
        this.addTooltip('perplexity-frequency-penalty', 'frequency-penalty', 'label');
        this.addTooltip('search-depth', 'search-depth', 'label');
        this.addTooltip('search-recency', 'search-recency', 'label');
        this.addTooltip('perplexity-citations', 'perplexity-citations', 'parent');
        this.addTooltip('perplexity-domains', 'perplexity-domains', 'label');
        this.addTooltip('openai-style', 'openai-style', 'label');
        this.addTooltip('user-timezone', 'user-timezone', 'label');
        this.addTooltip('collection-time', 'collection-time', 'label');
        this.addTooltip('publications-count', 'publications-count', 'label');
        this.addTooltip('generate-images', 'generate-images', 'parent');
        this.addTooltip('publish-without-images', 'publish-without-images', 'parent');
    }

    addTooltip(elementId, tooltipKey, targetType = 'self') {
        const element = document.getElementById(elementId);
        if (!element) return;

        const data = this.tooltipData[tooltipKey];
        if (!data) return;

        let target;
        if (targetType === 'label') {
            // Find the label for this element
            target = element.closest('div')?.querySelector('label');
        } else if (targetType === 'parent') {
            // Use parent label element
            target = element.closest('label');
        } else {
            target = element;
        }

        if (!target) return;

        // Remove old title attribute if exists
        const oldTitle = target.querySelector('[title]');
        if (oldTitle) {
            oldTitle.removeAttribute('title');
        }

        // Create tooltip trigger icon
        const trigger = document.createElement('span');
        trigger.className = 'tooltip-trigger';
        trigger.innerHTML = '<i class="fas fa-info-circle text-xs"></i>';
        
        // Create tooltip container
        const container = document.createElement('span');
        container.className = 'tooltip-container';
        container.appendChild(trigger);

        // Create tooltip element
        const tooltip = document.createElement('div');
        tooltip.className = `tooltip tooltip-top tooltip-${data.type}`;
        tooltip.innerHTML = `
            <div class="tooltip-content">
                ${data.title ? `<div class="tooltip-title">${data.title}</div>` : ''}
                <div class="tooltip-text">${data.text}</div>
                ${data.example ? `<div class="tooltip-example">${data.example}</div>` : ''}
            </div>
        `;

        container.appendChild(tooltip);
        
        // Add to target element
        if (targetType === 'label' && target) {
            // Insert after the label text
            const textNode = Array.from(target.childNodes).find(node => node.nodeType === 3);
            if (textNode) {
                target.insertBefore(container, textNode.nextSibling);
            } else {
                target.appendChild(container);
            }
        } else {
            target.appendChild(container);
        }

        // Setup events
        this.setupTooltipEvents(trigger, tooltip);
    }

    setupTooltipEvents(trigger, tooltip) {
        let showTimeout;
        let hideTimeout;

        trigger.addEventListener('mouseenter', () => {
            clearTimeout(hideTimeout);
            showTimeout = setTimeout(() => {
                this.showTooltip(tooltip);
            }, 200);
        });

        trigger.addEventListener('mouseleave', () => {
            clearTimeout(showTimeout);
            hideTimeout = setTimeout(() => {
                this.hideTooltip(tooltip);
            }, 100);
        });

        // Keep tooltip open when hovering over it
        tooltip.addEventListener('mouseenter', () => {
            clearTimeout(hideTimeout);
        });

        tooltip.addEventListener('mouseleave', () => {
            hideTimeout = setTimeout(() => {
                this.hideTooltip(tooltip);
            }, 100);
        });
    }

    showTooltip(tooltip) {
        // Hide any active tooltip
        if (this.activeTooltip && this.activeTooltip !== tooltip) {
            this.hideTooltip(this.activeTooltip);
        }

        // Position adjustment if needed
        this.adjustPosition(tooltip);
        
        // Show tooltip
        tooltip.classList.add('show');
        this.activeTooltip = tooltip;
    }

    hideTooltip(tooltip) {
        tooltip.classList.remove('show');
        if (this.activeTooltip === tooltip) {
            this.activeTooltip = null;
        }
    }

    adjustPosition(tooltip) {
        const rect = tooltip.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        // Check if tooltip goes out of viewport
        if (rect.right > viewportWidth) {
            tooltip.classList.remove('tooltip-top');
            tooltip.classList.add('tooltip-left');
        } else if (rect.left < 0) {
            tooltip.classList.remove('tooltip-top');
            tooltip.classList.add('tooltip-right');
        } else if (rect.top < 0) {
            tooltip.classList.remove('tooltip-top');
            tooltip.classList.add('tooltip-bottom');
        }
    }
}

// Initialize tooltip system
const tooltipSystem = new TooltipSystem();