#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Тестирование формата времени в веб-интерфейсе"""

import requests
from datetime import datetime
import re

def test_time_format():
    """Проверяет формат отображения времени"""
    
    # Получаем страницу
    response = requests.get('http://localhost:5000')
    html_content = response.text
    
    # Ищем JavaScript функцию updateCurrentTime
    js_pattern = r'function updateCurrentTime\(\).*?hour12:\s*(true|false)'
    match = re.search(js_pattern, html_content, re.DOTALL)
    
    if match:
        hour12_value = match.group(1)
        print(f"[OK] Found hour12 parameter: {hour12_value}")
        if hour12_value == "false":
            print("[INFO] Using 24-hour time format")
        else:
            print("[INFO] Using 12-hour time format")
    else:
        print("[ERROR] hour12 parameter not found in JavaScript code")
    
    # Проверяем текущее время
    current_time = datetime.now()
    
    print(f"\n[TIME] Current time:")
    print(f"   24-hour format: {current_time.strftime('%H:%M:%S')}")
    print(f"   12-hour format: {current_time.strftime('%I:%M:%S %p')}")
    
    # Проверяем наличие элемента current-time
    if 'id="current-time"' in html_content:
        print("\n[OK] Element with id='current-time' found on page")
    else:
        print("\n[ERROR] Element with id='current-time' NOT found on page")
    
    # Проверяем подключение tooltips
    if 'tooltips.css' in html_content and 'tooltips.js' in html_content:
        print("[OK] Tooltips files are connected")
    else:
        print("[ERROR] Tooltips files are not connected")
    
    # Ищем все места с toLocaleTimeString
    time_format_calls = re.findall(r'toLocaleTimeString\([^)]+\)', html_content)
    if time_format_calls:
        print(f"\n[INFO] Found {len(time_format_calls)} toLocaleTimeString calls:")
        for call in time_format_calls:
            print(f"   - {call}")

if __name__ == "__main__":
    try:
        test_time_format()
    except requests.exceptions.ConnectionError:
        print("[ERROR] Cannot connect to server at http://localhost:5000")
        print("   Make sure web server is running: python web_config_app.py")
    except Exception as e:
        print(f"[ERROR] Error: {e}")