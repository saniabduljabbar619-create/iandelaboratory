# -*- coding: utf-8 -*-
# app/api/routers/sync.py
"""
LAN <-> cloud sync endpoints.

Cloud side (called by the LAN server's sync agent, X-Sync-Token required):
  POST /api/sync/push   apply a batch of changes made in the lab
  POST /api/sync/pull   hand the LAN server changes made on the cloud
  GET  /api/sync/file   download an uploaded file belonging to a synced row
  POST /api/sync/file   receive an uploaded file belonging to a synced row

Either side (staff login required):
  GET  /api/sync/status   is sync on, is the cloud reachable, how much is queued
  POST /api/sync/run-now  LAN only: sync immediately instead of waiting

All of these answer 404 unless SYNC_ENABLED is on for this node.
"""
from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.sync import engine as sync
from app.sync import state
from app.sync.files import safe_upload_path
from app.sync.progress import progress_status
from app.sync.registry import spec_for

router = APIRouter(prefix="/api/sync", tags=["sync"])


def _require_enabled():
    if not settings.SYNC_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")


def _require_peer(x_sync_token: str | None = Header(default=None)):
    """Only the LAN server's agent may call the cloud-side endpoints."""
    token = settings.SYNC_TOKEN or ""
    if not settings.SYNC_ENABLED or settings.NODE_ROLE != "cloud" or len(token) < 16:
        raise HTTPException(status_code=404, detail="Not Found")
    if not x_sync_token or not hmac.compare_digest(x_sync_token, token):
        raise HTTPException(status_code=401, detail="Invalid sync token")


class PushIn(BaseModel):
    changes: list[dict[str, Any]]


class PullIn(BaseModel):
    ack_ids: list[int] = Field(default_factory=list)
    limit: int = Field(default=200, ge=1, le=1000)


@router.post("/push", dependencies=[Depends(_require_peer)])
def push(payload: PushIn, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        stats = sync.apply_incoming(db, payload.changes)
        db.commit()
        for job, local_id in sync.reindex_jobs(stats):
            background_tasks.add_task(job, local_id)
    except sync.SyncError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except Exception:
        db.rollback()
        raise
    return stats


@router.post("/pull", dependencies=[Depends(_require_peer)])
def pull(payload: PullIn, db: Session = Depends(get_db)):
    conn = db.connection()
    # Everything the LAN server confirmed last time is done; drop it first.
    sync.delete_outbox(conn, payload.ack_ids)
    changes, ids = sync.collect_outgoing(conn, payload.limit)
    remaining = max(sync.pending_count(conn) - len(ids), 0)
    db.commit()
    # "remaining" lets the LAN server show how much is still waiting up here.
    return {"changes": changes, "ids": ids, "more": remaining > 0, "remaining": remaining}


def _row_file(db: Session, table: str, sync_id: str, column: str):
    spec = spec_for(table)
    if not spec or column not in spec.files:
        raise HTTPException(status_code=400, detail="Not a synced file column")
    conn = db.connection()
    local_id, exists = sync.resolve(conn, table, sync_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Row not found")
    t = sync.table_of(table)
    path = safe_upload_path(conn.execute(select(t.c[column]).where(t.c.id == local_id)).scalar())
    if not path:
        raise HTTPException(status_code=404, detail="No file for this row")
    return path


@router.get("/file", dependencies=[Depends(_require_peer)])
def get_file(table: str, sync_id: str, column: str, db: Session = Depends(get_db)):
    path = _row_file(db, table, sync_id, column)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on server")
    return FileResponse(path=str(path))


@router.post("/file", dependencies=[Depends(_require_peer)])
async def put_file(
    table: str = Form(...),
    sync_id: str = Form(...),
    column: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    path = _row_file(db, table, sync_id, column)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(await file.read())
    return {"ok": True, "path": str(path).replace("\\", "/")}


@router.get("/status", dependencies=[Depends(_require_enabled)])
def status(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return progress_status(db.connection())


@router.post("/run-now", dependencies=[Depends(_require_enabled)])
def run_now(current_user=Depends(get_current_user)):
    if settings.NODE_ROLE != "lan":
        raise HTTPException(status_code=400, detail="Only the LAN server runs the sync agent")
    from app.sync import agent
    agent.wake()
    return {"ok": True}
