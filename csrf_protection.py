"""
CSRF защита для веб-интерфейса NEWSMAKER

Обеспечивает защиту от межсайтовой подделки запросов.
"""

import secrets
import hmac
import hashlib
from functools import wraps
from flask import session, request, jsonify, abort
from loguru import logger
from typing import Callable, Optional
import time


class CSRFProtection:
    """Менеджер CSRF токенов"""
    
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or secrets.token_hex(32)
        self.token_lifetime = 3600  # 1 час
        self.tokens = {}  # Хранение активных токенов
        
    def generate_token(self, session_id: str) -> str:
        """Генерирует CSRF токен для сессии"""
        # Создаем уникальный токен
        token = secrets.token_urlsafe(32)
        timestamp = int(time.time())
        
        # Создаем подпись токена
        signature = self._create_signature(token, session_id, timestamp)
        
        # Сохраняем токен
        full_token = f"{token}.{timestamp}.{signature}"
        self.tokens[session_id] = {
            'token': full_token,
            'created_at': timestamp
        }
        
        return full_token
    
    def _create_signature(self, token: str, session_id: str, timestamp: int) -> str:
        """Создает HMAC подпись для токена"""
        message = f"{token}.{session_id}.{timestamp}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def validate_token(self, token: str, session_id: str) -> bool:
        """Проверяет валидность CSRF токена"""
        if not token or not session_id:
            return False
        
        # Парсим токен
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return False
            
            token_value, timestamp_str, signature = parts
            timestamp = int(timestamp_str)
            
        except (ValueError, IndexError):
            logger.warning(f"Invalid CSRF token format: {token[:20]}...")
            return False
        
        # Проверяем время жизни токена
        current_time = int(time.time())
        if current_time - timestamp > self.token_lifetime:
            logger.warning(f"CSRF token expired for session {session_id}")
            return False
        
        # Проверяем подпись
        expected_signature = self._create_signature(token_value, session_id, timestamp)
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning(f"Invalid CSRF token signature for session {session_id}")
            return False
        
        # Проверяем, что токен активен для этой сессии
        if session_id in self.tokens:
            stored_token = self.tokens[session_id]['token']
            if stored_token != token:
                logger.warning(f"CSRF token mismatch for session {session_id}")
                return False
        
        return True
    
    def cleanup_expired_tokens(self):
        """Очищает устаревшие токены"""
        current_time = int(time.time())
        expired_sessions = []
        
        for session_id, token_data in self.tokens.items():
            if current_time - token_data['created_at'] > self.token_lifetime:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.tokens[session_id]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired CSRF tokens")


# Глобальный экземпляр
csrf = CSRFProtection()


def csrf_exempt(f: Callable) -> Callable:
    """Декоратор для исключения роута из CSRF проверки"""
    f.csrf_exempt = True
    return f


def csrf_protect(f: Callable) -> Callable:
    """Декоратор для защиты роута CSRF токеном"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Пропускаем GET запросы
        if request.method == 'GET':
            return f(*args, **kwargs)
        
        # Проверяем, исключен ли роут
        if hasattr(f, 'csrf_exempt') and f.csrf_exempt:
            return f(*args, **kwargs)
        
        # Получаем session_id
        session_id = session.get('session_id')
        if not session_id:
            logger.warning("No session_id for CSRF validation")
            return jsonify({'error': 'Session required'}), 403
        
        # Получаем CSRF токен из заголовка или формы
        csrf_token = None
        
        # Проверяем заголовок
        csrf_token = request.headers.get('X-CSRF-Token')
        
        # Если нет в заголовке, проверяем форму
        if not csrf_token and request.form:
            csrf_token = request.form.get('csrf_token')
        
        # Если нет в форме, проверяем JSON
        if not csrf_token and request.is_json:
            data = request.get_json()
            if data:
                csrf_token = data.get('csrf_token')
        
        # Валидируем токен
        if not csrf_token:
            logger.warning(f"Missing CSRF token for {request.path}")
            return jsonify({'error': 'CSRF token required'}), 403
        
        if not csrf.validate_token(csrf_token, session_id):
            logger.warning(f"Invalid CSRF token for {request.path}")
            return jsonify({'error': 'Invalid CSRF token'}), 403
        
        return f(*args, **kwargs)
    
    return decorated


def get_csrf_token() -> str:
    """Получает или генерирует CSRF токен для текущей сессии"""
    session_id = session.get('session_id')
    if not session_id:
        # Создаем временный session_id
        session_id = secrets.token_urlsafe(32)
        session['session_id'] = session_id
    
    # Проверяем существующий токен
    if session_id in csrf.tokens:
        token_data = csrf.tokens[session_id]
        # Проверяем, не истек ли токен
        if int(time.time()) - token_data['created_at'] < csrf.token_lifetime:
            return token_data['token']
    
    # Генерируем новый токен
    return csrf.generate_token(session_id)


def inject_csrf_token():
    """Инжектит CSRF токен в контекст шаблона"""
    return {
        'csrf_token': get_csrf_token
    }


# Middleware для автоматической очистки токенов
class CSRFCleanupMiddleware:
    """Middleware для периодической очистки устаревших токенов"""
    
    def __init__(self, app=None, cleanup_interval=3600):
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = time.time()
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Инициализация middleware с Flask приложением"""
        app.before_request(self.before_request)
    
    def before_request(self):
        """Выполняется перед каждым запросом"""
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            csrf.cleanup_expired_tokens()
            self.last_cleanup = current_time


# Утилиты для работы с CSRF в JavaScript
def generate_csrf_meta_tags() -> str:
    """Генерирует мета-теги для использования CSRF токена в JavaScript"""
    token = get_csrf_token()
    return f'<meta name="csrf-token" content="{token}">'


# Пример использования в JavaScript:
"""
// Получение CSRF токена из мета-тега
function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : null;
}

// Отправка запроса с CSRF токеном
fetch('/api/config', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': getCSRFToken()
    },
    body: JSON.stringify(data)
});
"""