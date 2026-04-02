"""加密存储管理"""
import json
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings


class SecureStorage:
    """安全存储 API 密钥等敏感信息"""

    def __init__(self):
        self.key_file = settings.ENCRYPTION_KEY_PATH
        self.config_file = settings.CONFIG_PATH
        self._key = None
        self._fernet = None

    def _get_or_create_key(self) -> bytes:
        """获取或创建加密密钥"""
        if self._key is not None:
            return self._key

        if self.key_file.exists():
            with open(self.key_file, "rb") as f:
                self._key = f.read()
        else:
            # 生成新密钥
            self._key = Fernet.generate_key()
            with open(self.key_file, "wb") as f:
                f.write(self._key)
            # 设置文件权限（仅当前用户可读）
            import stat
            self.key_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

        return self._key

    def _get_fernet(self) -> Fernet:
        """获取 Fernet 实例"""
        if self._fernet is None:
            self._fernet = Fernet(self._get_or_create_key())
        return self._fernet

    def save_config(self, api_key: str, base_url: str = None, model: str = None) -> bool:
        """加密保存 API 配置"""
        try:
            fernet = self._get_fernet()

            config = {
                "api_key": api_key,
                "base_url": base_url or str(settings.DEFAULT_AI_BASE_URL),
                "model": model or settings.DEFAULT_AI_MODEL
            }

            # 加密整个配置
            encrypted = fernet.encrypt(json.dumps(config).encode())

            with open(self.config_file, "wb") as f:
                f.write(encrypted)

            return True
        except Exception as e:
            print(f"Save config error: {e}")
            return False

    def load_config(self) -> dict:
        """解密加载 API 配置"""
        if not self.config_file.exists():
            return {}

        try:
            fernet = self._get_fernet()

            with open(self.config_file, "rb") as f:
                encrypted = f.read()

            decrypted = fernet.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception as e:
            print(f"Load config error: {e}")
            return {}

    def has_config(self) -> bool:
        """检查是否已有配置"""
        return self.config_file.exists()

    def clear_config(self) -> bool:
        """清除配置"""
        try:
            if self.config_file.exists():
                self.config_file.unlink()
            return True
        except Exception:
            return False


secure_storage = SecureStorage()
