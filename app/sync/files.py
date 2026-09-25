# -*- coding: utf-8 -*-
# app/sync/files.py
"""Uploaded files (payment proofs, referrer avatars) that travel with synced rows."""
from __future__ import annotations

from pathlib import Path

UPLOADS_ROOT = Path("uploads")


def safe_upload_path(value: str | None) -> Path | None:
    """Local path for a stored file column, or None if it's not a plain path under uploads/."""
    if not value:
        return None
    rel = Path(str(value).replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts or not rel.parts or rel.parts[0] != UPLOADS_ROOT.name:
        return None
    return rel
