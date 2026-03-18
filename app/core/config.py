# -*- coding: utf-8 -*-
#app/core/config.py
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    APP_NAME: str = "Solunex Lab Backend"
    ENV: str = "dev"

    # Example:
    # mysql+pymysql://root:password@127.0.0.1:3306/solunex_lab?charset=utf8mb4
    DATABASE_URL: str

    JWT_SECRET: str
    JWT_ALG: str = "HS256"
    JWT_EXPIRES_MIN: int = 60 * 8  # staff token (minutes)

    PORTAL_JWT_EXPIRES_MIN: int = 15
    PORTAL_SECRET: str = "change-me-portal-secret"


    PORTAL_MAX_FAILS: int = 5
    PORTAL_LOCK_MINUTES: int = 15


settings = Settings()
