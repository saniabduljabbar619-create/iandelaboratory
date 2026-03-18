# -*- coding: utf-8 -*-
# app/api/routers/auth.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import verify_password, create_token
from app.core.config import settings


router = APIRouter()


# ----------------------------
# DB Dependency
# ----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------------
# Login Schema
# ----------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


# ----------------------------
# Login Endpoint
# ----------------------------
@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.username == data.username).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User inactive")

    # Create JWT token
    token = create_token(
        subject=str(user.id),
        claims={
            "username": user.username,
            "role": user.role,
            "branch_id": user.branch_id,
        },
        minutes=settings.JWT_EXPIRES_MIN,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "branch_id": user.branch_id,
        },
    }