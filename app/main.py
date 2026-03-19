# -*- coding: utf-8 -*-
# app/main.py
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text

from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal

from app.api.routers import (
    auth, patients, templates, results, portal,
    test_types, debug, audit, test_requests, payments, reports
)
from app.api.routers import booking_conversion
from app.api.routers.referrer import router as referrer_router

from app.web.routes.portal_ui import router as portal_ui_router
from app.web.routes.admin import router as admin_router

from app.services.audit_service import AuditService


# --------------------------------------------------
# BASE PATH (DEPLOYMENT SAFE)
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------
# APP INIT (ONLY ONCE)
# --------------------------------------------------
# main.py
app = FastAPI(title=settings.APP_NAME, redirect_slashes=False)

# --------------------------------------------------
# CORS (ALLOW ALL FOR NOW)
# --------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# STATIC + UPLOADS (SAFE PATHS)
# --------------------------------------------------
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# --------------------------------------------------
# ROUTERS
# --------------------------------------------------
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(patients.router, prefix="/api/patients", tags=["patients"])
app.include_router(test_requests.router, prefix="/api/test-requests", tags=["test_requests"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])

app.include_router(booking_conversion.router)

app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
app.include_router(results.router, prefix="/api/results", tags=["results"])
app.include_router(test_types.router, prefix="/api/test-types", tags=["test_types"])

app.include_router(portal.router, prefix="/portal", tags=["portal"])

app.include_router(debug.router, prefix="/api/debug", tags=["debug"])
app.include_router(audit.router, prefix="/api/audits", tags=["audits"])

app.include_router(referrer_router)
app.include_router(portal_ui_router)
app.include_router(admin_router, prefix="/admin")

# --------------------------------------------------
# STARTUP
# --------------------------------------------------
@app.on_event("startup")
def _startup():
    os.makedirs(BASE_DIR.parent / "uploads" / "payments", exist_ok=True)
    os.makedirs(BASE_DIR.parent / "uploads" / "results", exist_ok=True)
    init_db()

# --------------------------------------------------
# TEST ROUTE (AUDIT)
# --------------------------------------------------
@app.get("/audit-test")
def audit_test(request: Request):
    ip = request.client.host if request.client else None
    db = SessionLocal()
    try:
        AuditService(db).log(
            actor_type="system",
            actor="audit-test",
            action="audit_test",
            entity="audit_logs",
            entity_id=None,
            ip=ip,
            meta={"ok": True},
        )
        return {"ok": True}
    finally:
        db.close()

# --------------------------------------------------
# HEALTH CHECKS
# --------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "service": settings.APP_NAME}


@app.get("/health/db")
def health_db():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"db": "ok"}
    except Exception as e:
        return {"db": "error", "detail": str(e)}
    finally:
        db.close()
