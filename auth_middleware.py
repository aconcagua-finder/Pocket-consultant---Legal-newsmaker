"""
Модуль аутентификации для веб-интерфейса NEWSMAKER

Обеспечивает базовую HTTP аутентификацию и защиту от несанкционированного доступа.
"""

import os
import hashlib
import secrets
import time
from datetime import datetime
from functools import wraps
from typing import Optional, Callable, Dict, Any
from flask import request, Response, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from loguru import logger
from pathlib import Path
import json

# Путь к файлу с учетными данными
AUTH_FILE = Path(".auth.json")
SESSION_TIMEOUT = 3600  # 1 час


class AuthManager:
    """Менеджер аутентификации для веб-интерфейса"""
    
    def __init__(self):
        self.users = self.load_users()
        self.sessions = {}
        self.max_attempts = 5
        self.lockout_time = 300  # 5 минут
        self.attempts = {}  # IP -> (attempts, last_attempt_time)
        
    def load_users(self) -> dict:
        """Загружает пользователей из защищенного файла"""
        if AUTH_FILE.exists():
            try:
                with open(AUTH_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get('users', {})
            except Exception as e:
                logger.error(f"Ошибка загрузки пользователей: {e}")
                return {}
        else:
            # Создаем дефолтного пользователя
            return self.create_default_user()
    
    def create_default_user(self) -> dict:
        """Создает дефолтного пользователя с случайным паролем"""
        default_password = secrets.token_urlsafe(12)
        users = {
            'admin': {
                'password_hash': generate_password_hash(default_password),
                'created_at': str(datetime.now()),
                'role': 'admin'
            }
        }
        
        # Сохраняем в файл
        auth_data = {
            'users': users,
            'default_password': default_password,
            'warning': 'CHANGE THIS PASSWORD IMMEDIATELY!'
        }
        
        try:
            with open(AUTH_FILE, 'w') as f:
                json.dump(auth_data, f, indent=2)
            
            # Устанавливаем права доступа только для владельца
            if os.name != 'nt':  # Unix-like системы
                os.chmod(AUTH_FILE, 0o600)
            
            logger.warning(f"Created default admin user. Password: {default_password}")
            logger.warning("IMPORTANT: Change this password immediately!")
            
            # Также выводим в консоль
            print("\n" + "="*60)
            print("SECURITY WARNING!")
            print(f"Default admin password: {default_password}")
            print("Change it immediately in .auth.json file")
            print("="*60 + "\n")
            
        except Exception as e:
            logger.error(f"Ошибка создания дефолтного пользователя: {e}")
        
        return users
    
    def check_rate_limit(self, ip: str) -> bool:
        """Проверяет rate limiting для IP адреса"""
        import time
        current_time = time.time()
        
        if ip in self.attempts:
            attempts, last_time = self.attempts[ip]
            
            # Проверяем lockout
            if attempts >= self.max_attempts:
                if current_time - last_time < self.lockout_time:
                    return False
                else:
                    # Сбрасываем счетчик после lockout
                    self.attempts[ip] = (0, current_time)
        
        return True
    
    def record_attempt(self, ip: str, success: bool):
        """Записывает попытку входа"""
        import time
        current_time = time.time()
        
        if success:
            # Успешный вход - сбрасываем счетчик
            if ip in self.attempts:
                del self.attempts[ip]
        else:
            # Неудачная попытка
            if ip in self.attempts:
                attempts, _ = self.attempts[ip]
                self.attempts[ip] = (attempts + 1, current_time)
            else:
                self.attempts[ip] = (1, current_time)
            
            # Логируем подозрительную активность
            attempts_count = self.attempts[ip][0]
            if attempts_count >= 3:
                logger.warning(f"Multiple failed login attempts from {ip}: {attempts_count}")
    
    def authenticate(self, username: str, password: str) -> bool:
        """Проверяет учетные данные пользователя"""
        if username not in self.users:
            return False
        
        user = self.users[username]
        return check_password_hash(user['password_hash'], password)
    
    def create_session(self, username: str) -> str:
        """Создает сессию для пользователя"""
        session_id = secrets.token_urlsafe(32)
        import time
        self.sessions[session_id] = {
            'username': username,
            'created_at': time.time(),
            'last_activity': time.time()
        }
        return session_id
    
    def validate_session(self, session_id: str) -> Optional[str]:
        """Проверяет валидность сессии"""
        if session_id not in self.sessions:
            return None
        
        import time
        session_data = self.sessions[session_id]
        current_time = time.time()
        
        # Проверяем таймаут
        if current_time - session_data['last_activity'] > SESSION_TIMEOUT:
            del self.sessions[session_id]
            return None
        
        # Обновляем время активности
        session_data['last_activity'] = current_time
        return session_data['username']
    
    def logout(self, session_id: str):
        """Завершает сессию"""
        if session_id in self.sessions:
            del self.sessions[session_id]


# Глобальный экземпляр менеджера аутентификации
auth_manager = AuthManager()


def check_auth(username: str, password: str) -> bool:
    """Проверяет базовую HTTP аутентификацию"""
    ip = request.remote_addr
    
    # Проверяем rate limit
    if not auth_manager.check_rate_limit(ip):
        logger.warning(f"Rate limit exceeded for {ip}")
        return False
    
    # Проверяем учетные данные
    success = auth_manager.authenticate(username, password)
    auth_manager.record_attempt(ip, success)
    
    if success:
        logger.info(f"Successful login for {username} from {ip}")
    else:
        logger.warning(f"Failed login attempt for {username} from {ip}")
    
    return success


def authenticate():
    """Отправляет 401 ответ с требованием аутентификации"""
    return Response(
        'Authentication required. Please login with valid credentials.',
        401,
        {'WWW-Authenticate': 'Basic realm="NEWSMAKER Admin Panel"'}
    )


def requires_auth(f: Callable) -> Callable:
    """Декоратор для защиты роутов аутентификацией"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Проверяем сессию
        session_id = session.get('session_id')
        if session_id:
            username = auth_manager.validate_session(session_id)
            if username:
                request.current_user = username
                return f(*args, **kwargs)
        
        # Проверяем Basic Auth
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        
        # Создаем сессию при успешной аутентификации
        session_id = auth_manager.create_session(auth.username)
        session['session_id'] = session_id
        request.current_user = auth.username
        
        return f(*args, **kwargs)
    
    return decorated


def requires_admin(f: Callable) -> Callable:
    """Декоратор для проверки админских прав"""
    @wraps(f)
    @requires_auth
    def decorated(*args, **kwargs):
        username = getattr(request, 'current_user', None)
        if not username:
            return jsonify({'error': 'Unauthorized'}), 401
        
        user = auth_manager.users.get(username, {})
        if user.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    
    return decorated


# Дополнительные утилиты безопасности
def sanitize_input(text: str) -> str:
    """Очищает пользовательский ввод от опасных символов"""
    if not text:
        return ""
    
    # Удаляем HTML теги
    import re
    text = re.sub(r'<[^>]+>', '', text)
    
    # Экранируем специальные символы
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#x27;')
    text = text.replace('/', '&#x2F;')
    
    return text


def validate_ip_whitelist(ip: str, whitelist: list) -> bool:
    """Проверяет IP адрес против белого списка"""
    if not whitelist:
        return True  # Если белый список пуст, разрешаем все
    
    import ipaddress
    try:
        ip_addr = ipaddress.ip_address(ip)
        for allowed in whitelist:
            # Поддержка подсетей
            if '/' in allowed:
                network = ipaddress.ip_network(allowed)
                if ip_addr in network:
                    return True
            else:
                if str(ip_addr) == allowed:
                    return True
    except Exception as e:
        logger.error(f"Ошибка проверки IP {ip}: {e}")
    
    return False


# Добавляем необходимый импорт
from datetime import datetime


def update_user_password(username: str, new_password: str) -> bool:
    """Обновляет пароль пользователя"""
    if username not in auth_manager.users:
        return False
    
    auth_manager.users[username]['password_hash'] = generate_password_hash(new_password)
    auth_manager.users[username]['updated_at'] = str(datetime.now())
    
    # Сохраняем изменения
    auth_data = {
        'users': auth_manager.users,
        'updated_at': str(datetime.now())
    }
    
    try:
        with open(AUTH_FILE, 'w') as f:
            json.dump(auth_data, f, indent=2)
        logger.info(f"Password updated for user {username}")
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления пароля: {e}")
        return False