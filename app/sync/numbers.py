# -*- coding: utf-8 -*-
# app/sync/numbers.py
"""
Keeps numbers from clashing while the LAN server is offline.

Lab numbers: once LAN mode is on, the LAN server is the only place real lab
numbers are issued. Anything created on the cloud meanwhile (referrer
"book tests") gets a temporary WEB-XXXXXX number, which the LAN server
swaps for the next real number when the record syncs down.

Booking codes are derived from the row id, and ids differ between the two
databases, so bookings made on the cloud use their own permanent prefix.
The patient already holds that code for payment, so it is never changed.
"""
from __future__ import annotations

import logging
import secrets

from app.core.config import settings

log = logging.getLogger("solunex.sync")

TEMP_LAB_PREFIX = "WEB-"
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def cloud_issues_temp_numbers() -> bool:
    return settings.SYNC_ENABLED and settings.NODE_ROLE == "cloud"


def temp_lab_number() -> str:
    return TEMP_LAB_PREFIX + "".join(secrets.choice(_ALPHABET) for _ in range(6))


def booking_code(booking_id: int) -> str:
    prefix = "SLB-WEB" if cloud_issues_temp_numbers() else "SLB-BKG"
    return f"{prefix}-{booking_id:04d}"


def finalize_temp_lab_numbers(db) -> int:
    """LAN only: replace WEB- lab numbers with real ones. Returns how many were replaced."""
    from app.models.test_request import TestRequest
    from app.services.numbering_service import NumberingService

    temp_numbers = [
        row[0] for row in
        db.query(TestRequest.lab_number)
        .filter(TestRequest.lab_number.like(f"{TEMP_LAB_PREFIX}%"))
        .distinct()
        .all()
    ]
    for temp in temp_numbers:
        real = NumberingService(db).next_lab_number()
        for tr in db.query(TestRequest).filter(TestRequest.lab_number == temp).all():
            tr.lab_number = real
        db.commit()
        log.info("lab number %s -> %s", temp, real)
    return len(temp_numbers)
