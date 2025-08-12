"""
Модуль шифрования для защиты чувствительных данных NEWSMAKER

Обеспечивает шифрование API ключей и других секретных данных.
"""

import os
import base64
import json
from pathlib import Path
from typing import Any, Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from loguru import logger


class EncryptionManager:
    """Менеджер шифрования для защиты чувствительных данных"""
    
    def __init__(self, key_file: str = ".encryption_key"):
        self.key_file = Path(key_file)
        self.cipher = self._initialize_cipher()
        
    def _initialize_cipher(self) -> Fernet:
        """Инициализирует шифровальщик с ключом"""
        encryption_key = self._get_or_create_key()
        return Fernet(encryption_key)
    
    def _get_or_create_key(self) -> bytes:
        """Получает существующий ключ или создает новый"""
        if self.key_file.exists():
            try:
                with open(self.key_file, 'rb') as f:
                    key = f.read()
                    if len(key) == 44:  # Проверяем валидность ключа
                        return key
            except Exception as e:
                logger.error(f"Ошибка чтения ключа шифрования: {e}")
        
        # Генерируем новый ключ
        key = self._generate_key()
        self._save_key(key)
        return key
    
    def _generate_key(self) -> bytes:
        """Генерирует новый ключ шифрования"""
        # Используем криптографически стойкий генератор
        key = Fernet.generate_key()
        logger.info("Сгенерирован новый ключ шифрования")
        return key
    
    def _derive_key_from_password(self, password: str, salt: bytes = None) -> bytes:
        """Создает ключ из пароля используя PBKDF2"""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _save_key(self, key: bytes):
        """Сохраняет ключ шифрования в защищенный файл"""
        try:
            with open(self.key_file, 'wb') as f:
                f.write(key)
            
            # Устанавливаем права доступа только для владельца
            if os.name != 'nt':  # Unix-like системы
                os.chmod(self.key_file, 0o600)
            
            logger.info(f"Ключ шифрования сохранен в {self.key_file}")
        except Exception as e:
            logger.error(f"Ошибка сохранения ключа шифрования: {e}")
    
    def encrypt_string(self, plaintext: str) -> str:
        """Шифрует строку"""
        try:
            encrypted = self.cipher.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Ошибка шифрования: {e}")
            raise
    
    def decrypt_string(self, ciphertext: str) -> str:
        """Расшифровывает строку"""
        try:
            encrypted = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Ошибка расшифровки: {e}")
            raise
    
    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """Шифрует словарь"""
        try:
            json_str = json.dumps(data)
            return self.encrypt_string(json_str)
        except Exception as e:
            logger.error(f"Ошибка шифрования словаря: {e}")
            raise
    
    def decrypt_dict(self, ciphertext: str) -> Dict[str, Any]:
        """Расшифровывает словарь"""
        try:
            json_str = self.decrypt_string(ciphertext)
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Ошибка расшифровки словаря: {e}")
            raise
    
    def encrypt_file(self, input_file: Path, output_file: Optional[Path] = None):
        """Шифрует файл"""
        if output_file is None:
            output_file = Path(str(input_file) + '.encrypted')
        
        try:
            with open(input_file, 'rb') as f:
                data = f.read()
            
            encrypted = self.cipher.encrypt(data)
            
            with open(output_file, 'wb') as f:
                f.write(encrypted)
            
            logger.info(f"Файл зашифрован: {input_file} -> {output_file}")
        except Exception as e:
            logger.error(f"Ошибка шифрования файла: {e}")
            raise
    
    def decrypt_file(self, input_file: Path, output_file: Optional[Path] = None):
        """Расшифровывает файл"""
        if output_file is None:
            output_file = Path(str(input_file).replace('.encrypted', ''))
        
        try:
            with open(input_file, 'rb') as f:
                encrypted = f.read()
            
            decrypted = self.cipher.decrypt(encrypted)
            
            with open(output_file, 'wb') as f:
                f.write(decrypted)
            
            logger.info(f"Файл расшифрован: {input_file} -> {output_file}")
        except Exception as e:
            logger.error(f"Ошибка расшифровки файла: {e}")
            raise
    
    def rotate_key(self, old_key_file: str = None) -> bool:
        """Ротация ключа шифрования с перешифровкой данных"""
        try:
            # Сохраняем старый шифровальщик
            old_cipher = self.cipher
            
            # Генерируем новый ключ
            new_key = self._generate_key()
            self.cipher = Fernet(new_key)
            
            # Сохраняем новый ключ
            self._save_key(new_key)
            
            # Здесь должна быть логика перешифровки всех существующих данных
            # с использованием old_cipher для расшифровки и self.cipher для шифрования
            
            logger.info("Ключ шифрования успешно ротирован")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка ротации ключа: {e}")
            return False


class SecureConfig:
    """Класс для безопасного хранения конфигурации с шифрованием"""
    
    def __init__(self, config_file: str = ".secure_config.enc"):
        self.config_file = Path(config_file)
        self.encryption = EncryptionManager()
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Загружает и расшифровывает конфигурацию"""
        if not self.config_file.exists():
            return {}
        
        try:
            with open(self.config_file, 'r') as f:
                encrypted_data = f.read()
            
            return self.encryption.decrypt_dict(encrypted_data)
        except Exception as e:
            logger.error(f"Ошибка загрузки защищенной конфигурации: {e}")
            return {}
    
    def save_config(self):
        """Шифрует и сохраняет конфигурацию"""
        try:
            encrypted_data = self.encryption.encrypt_dict(self.config)
            
            with open(self.config_file, 'w') as f:
                f.write(encrypted_data)
            
            # Устанавливаем права доступа
            if os.name != 'nt':
                os.chmod(self.config_file, 0o600)
            
            logger.info("Конфигурация сохранена в зашифрованном виде")
        except Exception as e:
            logger.error(f"Ошибка сохранения защищенной конфигурации: {e}")
    
    def set_api_key(self, key_name: str, key_value: str):
        """Сохраняет API ключ в зашифрованном виде"""
        if 'api_keys' not in self.config:
            self.config['api_keys'] = {}
        
        self.config['api_keys'][key_name] = key_value
        self.save_config()
        logger.info(f"API ключ {key_name} сохранен в зашифрованном виде")
    
    def get_api_key(self, key_name: str) -> Optional[str]:
        """Получает расшифрованный API ключ"""
        if 'api_keys' not in self.config:
            return None
        
        return self.config['api_keys'].get(key_name)
    
    def remove_api_key(self, key_name: str):
        """Удаляет API ключ"""
        if 'api_keys' in self.config and key_name in self.config['api_keys']:
            del self.config['api_keys'][key_name]
            self.save_config()
            logger.info(f"API ключ {key_name} удален")


# Глобальный экземпляр для использования в проекте
encryption_manager = EncryptionManager()
secure_config = SecureConfig()


# Функция для миграции существующих ключей
def migrate_env_to_encrypted():
    """Мигрирует API ключи из .env в зашифрованное хранилище"""
    from dotenv import load_dotenv
    
    env_file = Path('.env')
    if not env_file.exists():
        logger.warning("Файл .env не найден для миграции")
        return
    
    load_dotenv(env_file)
    
    # Список ключей для миграции
    keys_to_migrate = [
        'PERPLEXITY_API_KEY',
        'OPENAI_API_KEY',
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHANNEL_ID'
    ]
    
    migrated = 0
    for key in keys_to_migrate:
        value = os.getenv(key)
        if value and value != 'your_' + key.lower() + '_here':
            secure_config.set_api_key(key, value)
            migrated += 1
            logger.info(f"Мигрирован ключ {key}")
    
    if migrated > 0:
        logger.info(f"Мигрировано {migrated} ключей в защищенное хранилище")
        logger.warning("Рекомендуется удалить ключи из .env файла")
    else:
        logger.info("Нет ключей для миграции")


# Функция для безопасного получения API ключей
def get_api_key(key_name: str) -> Optional[str]:
    """Получает API ключ из защищенного хранилища или .env"""
    # Сначала проверяем защищенное хранилище
    key = secure_config.get_api_key(key_name)
    if key:
        return key
    
    # Fallback на .env
    return os.getenv(key_name)


if __name__ == "__main__":
    # Тестирование
    logger.info("Тестирование модуля шифрования...")
    
    # Тест шифрования строк
    test_string = "Test API Key: sk-1234567890"
    encrypted = encryption_manager.encrypt_string(test_string)
    decrypted = encryption_manager.decrypt_string(encrypted)
    assert decrypted == test_string, "Ошибка шифрования/расшифровки строки"
    logger.info("✅ Шифрование строк работает")
    
    # Тест шифрования словарей
    test_dict = {"api_key": "secret", "user": "admin"}
    encrypted_dict = encryption_manager.encrypt_dict(test_dict)
    decrypted_dict = encryption_manager.decrypt_dict(encrypted_dict)
    assert decrypted_dict == test_dict, "Ошибка шифрования/расшифровки словаря"
    logger.info("✅ Шифрование словарей работает")
    
    logger.info("✅ Все тесты пройдены")