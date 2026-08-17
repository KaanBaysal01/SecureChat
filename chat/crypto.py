import os
from cryptography.fernet import Fernet, InvalidToken

_fernet = None


def get_fernet():
    global _fernet
    if _fernet is None:
        key = os.getenv("FERNET_KEY")
        if not key:
            raise RuntimeError("FERNET_KEY tanımlı değil.")
        _fernet = Fernet(key.encode())
    return _fernet


def encrypt_message(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_message(ciphertext: str) -> str:
    try:
        return get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return "[çözülemedi]"
