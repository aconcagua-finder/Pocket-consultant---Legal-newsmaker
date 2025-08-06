#!/usr/bin/env python3
"""
Запуск NEWSMAKER с предварительной валидацией

Этот скрипт проверяет систему перед запуском
и гарантирует корректность конфигурации.
"""

import sys
from loguru import logger

# Импортируем валидацию
from validation import run_full_validation

# Импортируем основную программу
from main import main as run_main


def startup_with_validation():
    """Запуск системы с полной проверкой"""
    
    logger.info("=" * 70)
    logger.info("🚀 NEWSMAKER - Запуск с валидацией")
    logger.info("=" * 70)
    
    # Шаг 1: Валидация системы
    logger.info("\n📋 ШАГ 1: Проверка системы...")
    if not run_full_validation():
        logger.error("\n❌ КРИТИЧЕСКАЯ ОШИБКА: Система не прошла валидацию!")
        logger.error("🔧 Исправьте проблемы и попробуйте снова")
        sys.exit(1)
    
    logger.info("\n✅ Система прошла все проверки!")
    
    # Шаг 2: Проверка timezone
    logger.info("\n📋 ШАГ 2: Проверка часового пояса...")
    try:
        from timezone_utils import test_timezone_functions
        test_timezone_functions()
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации timezone: {e}")
        sys.exit(1)
    
    # Шаг 3: Проверка файловой системы
    logger.info("\n📋 ШАГ 3: Проверка файловой системы...")
    try:
        from file_utils import test_file_operations
        test_file_operations()
    except Exception as e:
        logger.error(f"❌ Ошибка файловой системы: {e}")
        sys.exit(1)
    
    logger.info("\n" + "=" * 70)
    logger.info("🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО!")
    logger.info("🚀 Запускаю основную программу...")
    logger.info("=" * 70 + "\n")
    
    # Запуск основной программы
    run_main()


if __name__ == "__main__":
    try:
        startup_with_validation()
    except KeyboardInterrupt:
        logger.info("\n⏹️ Программа остановлена пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n💥 Критическая ошибка: {e}")
        logger.exception("Детали ошибки:")
        sys.exit(1)