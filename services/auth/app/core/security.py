import hashlib
import secrets

from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], default="bcrypt", deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def generate_token(length: int = 32) -> str:
    token = secrets.token_urlsafe(length)
    return token

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

