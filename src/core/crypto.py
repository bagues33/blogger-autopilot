"""
Encryption Service for Blogger Auto-Pilot SaaS
Provides symmetric AES-128-CBC / Fernet encryption to protect OAuth tokens at rest in database.
"""

import os
import json
import base64
import hashlib
from cryptography.fernet import Fernet

_DEV_CRYPTO_FALLBACK = 'blogger-autopilot-dev-secret-key-32bytes!'
_CRYPTO_PLACEHOLDERS = ('ganti_dengan', 'dev-secret', 'change_me', 'placeholder', 'your_secret')

def get_encryption_key() -> bytes:
    raw_key = os.environ.get('ENCRYPTION_SECRET_KEY', '').strip()
    is_prod = os.environ.get('ENVIRONMENT', '').strip().lower() == 'production'
    if is_prod:
        if (
            not raw_key
            or len(raw_key) < 24
            or raw_key == _DEV_CRYPTO_FALLBACK
            or any(m in raw_key.lower() for m in _CRYPTO_PLACEHOLDERS)
        ):
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: ENCRYPTION_SECRET_KEY wajib diisi dengan string acak minimal 24 karakter saat ENVIRONMENT=production!"
            )
    if not raw_key:
        # Fallback predictable dev key (for local dev only)
        raw_key = _DEV_CRYPTO_FALLBACK
    
    # Ensure key is exactly 32 url-safe base64-encoded bytes for Fernet
    digest = hashlib.sha256(raw_key.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest)

def encrypt_token_data(token_obj) -> str:
    """
    Encrypts a token dict or JSON string into a secure ciphertext string.
    """
    if isinstance(token_obj, dict):
        text = json.dumps(token_obj)
    else:
        text = str(token_obj)
        
    f = Fernet(get_encryption_key())
    encrypted_bytes = f.encrypt(text.encode('utf-8'))
    return encrypted_bytes.decode('utf-8')

def decrypt_token_data(ciphertext: str) -> dict:
    """
    Decrypts a ciphertext string back into a token dictionary.
    """
    if not ciphertext:
        return {}
        
    f = Fernet(get_encryption_key())
    decrypted_bytes = f.decrypt(ciphertext.encode('utf-8'))
    text = decrypted_bytes.decode('utf-8')
    try:
        return json.loads(text)
    except Exception:
        return {'raw': text}
