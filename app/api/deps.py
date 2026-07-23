# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Generator, Optional

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.security import decode_token
from app.core.constants import UserRole

bearer_scheme = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_claims(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    token = credentials.credentials
    try:
        return decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def require_roles(*roles: UserRole):
    allowed = {r.value for r in roles}

    def _guard(claims: dict = Depends(get_current_user_claims)) -> dict:
        role = claims.get("role")
        if role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return claims

    return _guard


def get_portal_claims(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing portal token")

    token = authorization
    if token.lower().startswith("bearer "):
        token = token.split(" ", 1)[1].strip()

    try:
        claims = decode_token(token)
        if claims.get("kind") != "portal":
            raise HTTPException(status_code=401, detail="Invalid portal token")
        return claims
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid portal token")