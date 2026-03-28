"""
FastForge Password Hashing
==============================
Wraps passlib for bcrypt password hashing.
"""
from __future__ import annotations

try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except ImportError:
    pwd_context = None


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    if pwd_context is None:
        raise ImportError("Install passlib: pip install passlib[bcrypt]")
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    if pwd_context is None:
        raise ImportError("Install passlib: pip install passlib[bcrypt]")
    return pwd_context.verify(plain, hashed)
