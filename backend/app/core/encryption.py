"""
AEGIS UNIFIED DATA CORE - API Key & Secret Encryption at Rest
Uses Fernet (AES-128-CBC + HMAC-SHA256 authenticated cryptography) derived from AEGIS_SECRET_KEY.
Ensures external provider secrets are NEVER stored or logged in plaintext.
"""
import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from backend.app.core.config import settings


class SecretVault:
    _cipher: Optional[Fernet] = None

    @classmethod
    def _get_cipher(cls) -> Fernet:
        if cls._cipher is None:
            # Derive 32-byte url-safe base64 key from settings.AEGIS_SECRET_KEY
            key_hash = hashlib.sha256(settings.AEGIS_SECRET_KEY.encode('utf-8')).digest()
            fernet_key = base64.urlsafe_b64encode(key_hash)
            cls._cipher = Fernet(fernet_key)
        return cls._cipher

    @classmethod
    def encrypt_secret(cls, secret_value: str) -> str:
        """Encrypts a plaintext provider secret before database persistence."""
        if not secret_value:
            return ""
        cipher = cls._get_cipher()
        encrypted_bytes = cipher.encrypt(secret_value.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')

    @classmethod
    def decrypt_secret(cls, encrypted_secret: str) -> str:
        """Decrypts a stored provider secret only in memory during external HTTP dispatch."""
        if not encrypted_secret:
            return ""
        try:
            cipher = cls._get_cipher()
            decrypted_bytes = cipher.decrypt(encrypted_secret.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except (InvalidToken, Exception):
            # If token is invalid or unencrypted fallback
            return ""

    @staticmethod
    def mask_secret(secret_value: str) -> str:
        """
        Masks a secret for display in admin UI. Never exposes the full secret.
        Example: '****************AB92'
        """
        if not secret_value:
            return ""
        if len(secret_value) <= 4:
            return "****************"
        suffix = secret_value[-4:]
        return f"{'*' * (len(secret_value) - 4)}{suffix}"
