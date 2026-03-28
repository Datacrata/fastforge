"""
FastForge JWT Service
========================
Handles JWT token creation, validation, and refresh.
Used by the auth middleware and the identity module.

Configure via environment / Settings:
  JWT_SECRET=your-secret-key
  JWT_ALGORITHM=HS256
  JWT_EXPIRE_MINUTES=60
  JWT_REFRESH_EXPIRE_DAYS=30
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("fastforge.auth")

try:
    from jose import jwt, JWTError, ExpiredSignatureError
except ImportError:
    raise ImportError("Install python-jose: pip install python-jose[cryptography]")


@dataclass
class TokenConfig:
    """JWT configuration."""
    secret: str = "change-this-in-production"
    algorithm: str = "HS256"
    access_expire_minutes: int = 60
    refresh_expire_days: int = 30


@dataclass
class TokenPayload:
    """Decoded token data."""
    sub: str  # user ID
    email: Optional[str] = None
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    tenant_id: Optional[str] = None
    exp: Optional[datetime] = None
    token_type: str = "access"  # "access" or "refresh"


class JwtService:
    """
    Stateless JWT service.
    Create one instance in your app and reuse it.
    """

    def __init__(self, config: TokenConfig):
        self.config = config

    def create_access_token(
        self,
        user_id: str,
        email: str = None,
        roles: list[str] = None,
        permissions: list[str] = None,
        tenant_id: str = None,
        extra_claims: dict = None,
    ) -> str:
        """Create a signed access token."""
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.config.access_expire_minutes)
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "type": "access",
        }
        if email:
            payload["email"] = email
        if roles:
            payload["roles"] = roles
        if permissions:
            payload["permissions"] = permissions
        if tenant_id:
            payload["tenant_id"] = tenant_id
        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(payload, self.config.secret, algorithm=self.config.algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        """Create a long-lived refresh token."""
        expire = datetime.now(timezone.utc) + timedelta(days=self.config.refresh_expire_days)
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "type": "refresh",
        }
        return jwt.encode(payload, self.config.secret, algorithm=self.config.algorithm)

    def create_token_pair(
        self,
        user_id: str,
        email: str = None,
        roles: list[str] = None,
        permissions: list[str] = None,
        tenant_id: str = None,
    ) -> dict:
        """Create both access and refresh tokens."""
        return {
            "access_token": self.create_access_token(
                user_id, email, roles, permissions, tenant_id
            ),
            "refresh_token": self.create_refresh_token(user_id),
            "token_type": "bearer",
            "expires_in": self.config.access_expire_minutes * 60,
        }

    def decode_token(self, token: str) -> Optional[TokenPayload]:
        """
        Decode and validate a JWT. Returns None if invalid/expired.
        """
        try:
            payload = jwt.decode(token, self.config.secret, algorithms=[self.config.algorithm])
            return TokenPayload(
                sub=payload.get("sub", ""),
                email=payload.get("email"),
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", []),
                tenant_id=payload.get("tenant_id"),
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc) if "exp" in payload else None,
                token_type=payload.get("type", "access"),
            )
        except ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except JWTError as e:
            logger.debug(f"Token decode error: {e}")
            return None

    def decode_refresh_token(self, token: str) -> Optional[str]:
        """Decode a refresh token and return the user_id, or None if invalid."""
        payload = self.decode_token(token)
        if payload and payload.token_type == "refresh":
            return payload.sub
        return None
