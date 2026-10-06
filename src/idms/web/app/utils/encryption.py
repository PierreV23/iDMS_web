import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from flask import current_app


def generate_fernet_key_from_string(secret_string: str, salt: bytes | None = None) -> bytes:
    """Derives a valid 32-byte base64 Fernet key from an arbitrary string."""
    # Salt should be saved alongside your encrypted data if static derivation is needed
    if salt is None:
        salt = b'static_or_random_salt_16b'  # Must be at least 16 bytes

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,  # High iteration count prevents brute-force attacks
    )

    # Derive key and base64 encode it for Fernet
    key = base64.urlsafe_b64encode(kdf.derive(secret_string.encode('utf-8')))
    return key

def _get_fernet() -> Fernet:
    """Utility to retrieve the Fernet instance from app config."""
    key = current_app.config.get("FERNET_KEY")
    if not key:
        raise ValueError("FERNET_KEY is missing from app.config despite encryption being enabled.")

    if isinstance(key, str):
        key = key.encode('utf-8')

    return Fernet(key)

def encrypt(data: str) -> str:
    """Encrypts string data if SERVER_SIDE_ENCRYPTION is enabled, otherwise returns raw string."""
    if not current_app.config.get("SERVER_SIDE_ENCRYPTION", False):
        return data

    f = _get_fernet()
    return f.encrypt(data.encode('utf-8')).decode('utf-8')

def decrypt(enc_data: str) -> str:
    """Decrypts string data if SERVER_SIDE_ENCRYPTION is enabled, otherwise returns raw string."""
    if not current_app.config.get("SERVER_SIDE_ENCRYPTION", False):
        return enc_data

    f = _get_fernet()
    try:
        return f.decrypt(enc_data.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        # Failsafe if unencrypted legacy data is passed while encryption is turned ON
        return enc_data
    except AttributeError:
        return ''