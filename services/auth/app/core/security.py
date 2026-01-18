import hashlib
import secrets
from time import time # type: ignore[attr-defined]

from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], default="bcrypt", deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def generate_token(length: int = 32) -> str:
    random_part = secrets.token_urlsafe(length)
    timestamp = str(int(time() * 1000))  # миллисекунды
    token = f"{random_part}-{timestamp}"
    return token

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

