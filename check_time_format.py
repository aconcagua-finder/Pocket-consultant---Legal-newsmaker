#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script for checking time format correctness (24-hour format)
"""

import re
import sys
from pathlib import Path
from datetime import datetime

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def check_file_for_time_issues(filepath):
    """Проверяет файл на наличие проблем с форматом времени"""
    issues = []
    
    try:
        content = filepath.read_text(encoding='utf-8')
        
        # Проверка на AM/PM в коде (исключая комментарии и CSS правила для скрытия)
        am_pm_pattern = r'\b(AM|PM|am|pm)\b'
        matches = re.finditer(am_pm_pattern, content)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            context = content[max(0, match.start()-50):min(len(content), match.end()+50)]
            # Пропускаем CSS правила для скрытия AM/PM
            if 'display: none' not in context and 'Hide AM/PM' not in context:
                issues.append(f"  Строка {line_num}: найдено '{match.group()}' в контексте: ...{context.strip()}...")
        
        # Проверка на использование 12-часового формата в strftime
        strftime_12h_pattern = r'strftime\([^)]*%[Ilp]'
        matches = re.finditer(strftime_12h_pattern, content)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            issues.append(f"  Строка {line_num}: использование 12-часового формата в strftime: {match.group()}")
        
        # Проверка на toLocaleTimeString без hour12: false
        locale_time_pattern = r'toLocaleTimeString\([^)]*\)'
        matches = re.finditer(locale_time_pattern, content)
        for match in matches:
            if 'hour12: false' not in match.group() and 'hour12:false' not in match.group():
                line_num = content[:match.start()].count('\n') + 1
                # Проверяем контекст - может быть hour12 установлен в переменной
                context_start = max(0, match.start() - 200)
                context = content[context_start:match.end() + 100]
                if 'hour12' not in context:
                    issues.append(f"  Строка {line_num}: toLocaleTimeString без явного hour12: false")
        
    except Exception as e:
        issues.append(f"  Ошибка при чтении файла: {e}")
    
    return issues

def main():
    print("=" * 60)
    print("TIME FORMAT CHECK IN PROJECT")
    print("=" * 60)
    
    # Файлы для проверки
    files_to_check = [
        Path('templates/config_modern.html'),
        Path('web_config_app.py'),
        Path('news_collector.py'),
        Path('news_publisher.py'),
        Path('news_scheduler.py'),
        Path('timezone_utils.py'),
        Path('logger_setup.py'),
    ]
    
    total_issues = 0
    
    for filepath in files_to_check:
        if filepath.exists():
            print(f"\nПроверка {filepath}...")
            issues = check_file_for_time_issues(filepath)
            if issues:
                print(f"  WARNING: Found issues: {len(issues)}")
                for issue in issues[:5]:  # Показываем первые 5 проблем
                    print(issue)
                if len(issues) > 5:
                    print(f"  ... and {len(issues) - 5} more issues")
                total_issues += len(issues)
            else:
                print("  OK: No issues found")
        else:
            print(f"\nERROR: File {filepath} not found")
    
    print("\n" + "=" * 60)
    
    # Проверка текущего времени
    now = datetime.now()
    print(f"\nTIME FORMATTING TEST:")
    print(f"  Current time: {now.strftime('%H:%M:%S')} (24-hour format)")
    print(f"  Date: {now.strftime('%d.%m.%Y')}")
    
    # Проверка критических моментов времени
    test_times = [
        (0, 0, "00:00", "Midnight"),
        (12, 0, "12:00", "Noon"),
        (13, 30, "13:30", "Afternoon"),
        (23, 59, "23:59", "End of day"),
    ]
    
    print(f"\nBOUNDARY VALUES CHECK:")
    for hour, minute, expected, description in test_times:
        test_time = now.replace(hour=hour, minute=minute, second=0)
        formatted = test_time.strftime('%H:%M')
        status = "OK" if formatted == expected else "FAIL"
        print(f"  [{status}] {description}: {formatted} (expected {expected})")
    
    print("\n" + "=" * 60)
    
    if total_issues == 0:
        print("SUCCESS: ALL CHECKS PASSED!")
        print("   System uses 24-hour time format.")
    else:
        print(f"WARNING: FOUND ISSUES: {total_issues}")
        print("   Please check the indicated places.")
    
    print("=" * 60)

if __name__ == "__main__":
    main()