# -*- coding: utf-8 -*-
#app/core/security.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_token(subject: str, claims: Dict[str, Any], minutes: int, *, secret: str | None = None) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        **claims,
    }
    return jwt.encode(payload, secret or settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def decode_token(token: str, *, secret: str | None = None) -> Dict[str, Any]:
    return jwt.decode(token, secret or settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
