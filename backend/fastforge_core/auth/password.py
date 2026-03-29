"""
FastForge Password Hashing
==============================
Uses bcrypt directly for password hashing (passlib is unmaintained
and incompatible with bcrypt >= 4.1).
"""
from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
