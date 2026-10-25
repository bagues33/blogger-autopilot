"""
Encryption Service for Blogger Auto-Pilot SaaS
Provides symmetric AES-128-CBC / Fernet encryption to protect OAuth tokens at rest in database.
"""

import os
import json
import base64
import hashlib
from cryptography.fernet import Fernet

def get_encryption_key() -> bytes:
    raw_key = os.environ.get('ENCRYPTION_SECRET_KEY', '').strip()
    if not raw_key:
        # Fallback predictable dev key (for local dev only)
        raw_key = 'blogger-autopilot-dev-secret-key-32bytes!'
    
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
