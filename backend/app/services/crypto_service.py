import base64
import hashlib
import logging
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings

logger = logging.getLogger(__name__)

PREFIX = "enc:v1:"


class LockerCryptoService:
    """
    AES-256-GCM authenticated encryption service for MindMesh Private Locker data.
    Provides backward-compatible decryption (unencrypted text is returned as-is).
    """

    def __init__(self, key: Optional[str] = None):
        raw_key = key or settings.locker_encryption_key
        if not raw_key:
            # Fallback to key derived from auth_secret_key in development
            raw_key = settings.auth_secret_key + ":mindmesh-locker-crypto-salt"
            if settings.app_env == "production":
                logger.warning(
                    "LOCKER_ENCRYPTION_KEY not set in production! Falling back to derived key."
                )

        # Derive exact 32-byte key using SHA-256
        self._key = hashlib.sha256(raw_key.encode("utf-8")).digest()
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypts plaintext string using AES-256-GCM.
        Returns format: enc:v1:<base64_nonce>:<base64_ciphertext_and_tag>
        """
        if not plaintext:
            return plaintext

        # 96-bit / 12-byte nonce recommended for AES-GCM
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

        b64_nonce = base64.b64encode(nonce).decode("utf-8")
        b64_ciphertext = base64.b64encode(ciphertext).decode("utf-8")

        return f"{PREFIX}{b64_nonce}:{b64_ciphertext}"

    def decrypt(self, ciphertext_str: str) -> str:
        """
        Decrypts ciphertext string.
        Backward-compatible: if the input does not start with 'enc:v1:',
        it returns the raw string unchanged, preserving existing database records.
        """
        if not ciphertext_str or not isinstance(ciphertext_str, str):
            return ciphertext_str

        if not ciphertext_str.startswith(PREFIX):
            # Backward compatibility for existing plaintext memories
            return ciphertext_str

        payload = ciphertext_str[len(PREFIX):]
        parts = payload.split(":", 1)
        if len(parts) != 2:
            logger.error("Malformed encrypted locker data payload")
            return "[Encrypted Locker Content - Malformed]"

        try:
            nonce = base64.b64decode(parts[0])
            ciphertext = base64.b64decode(parts[1])
            decrypted_bytes = self._aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to decrypt locker data: {e}")
            return "[Encrypted Locker Content - Decryption Failed]"


# Global singleton instance
locker_crypto = LockerCryptoService()
