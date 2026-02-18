"""AES-256 encryption/decryption utility for OAuth tokens."""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_key(key_b64: str) -> bytes:
    """Decode a base64-encoded 32-byte AES key."""
    key = base64.b64decode(key_b64)
    if len(key) != 32:
        raise ValueError("Encryption key must be exactly 32 bytes (256 bits)")
    return key


def encrypt(plaintext: str, key_b64: str) -> bytes:
    """Encrypt plaintext using AES-256-GCM. Returns nonce + ciphertext."""
    key = _get_key(key_b64)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ciphertext


def decrypt(data: bytes, key_b64: str) -> str:
    """Decrypt AES-256-GCM data (nonce + ciphertext) back to plaintext."""
    key = _get_key(key_b64)
    aesgcm = AESGCM(key)
    nonce = data[:12]
    ciphertext = data[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
