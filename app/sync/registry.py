# -*- coding: utf-8 -*-
# app/sync/registry.py
"""
Which tables sync, and how their columns reference other rows.

Many "foreign keys" in this schema are plain Integer columns without a
ForeignKey constraint, so every reference is declared here by hand.
Integer ids are never sent between nodes; each reference travels as the
parent's sync id and is turned back into a local id on arrival.

Tables are listed parents-first; incoming changes are applied in this order.

direction:
  "both" — changes flow LAN -> cloud and cloud -> LAN
  "up"   — the LAN server is the authority; the cloud never sends these down
           (numbering counters, settings, subscription records)

Not synced (derived or node-local): analytics_snapshots,
disease_weekly_trends, ssdo_index (rebuildable index), portal_auth_attempts.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TableSpec:
    table: str
    fks: dict = field(default_factory=dict)          # column -> parent table
    poly: dict = field(default_factory=dict)         # id column -> (type column, {type value: table})
    csv_fks: dict = field(default_factory=dict)      # column holding "1,2,3" -> table
    natural_key: str | None = None                   # unique key that identifies the same thing on both nodes
    direction: str = "both"
    exclude: tuple = ()                              # node-local columns, never sent
    files: dict = field(default_factory=dict)        # column -> local path template ({id}) or None


_REFERENCE_TYPES = {
    "booking": "bookings",
    "patient": "patients",
    "test_request": "test_requests",
    "test_result": "test_results",
}

SPECS: list[TableSpec] = [
    TableSpec("branches", natural_key="code"),
    TableSpec("users", fks={"branch_id": "branches"}, natural_key="username"),
    TableSpec("subscription_tiers", natural_key="name", direction="up"),
    TableSpec("subscriptions", fks={"branch_id": "branches", "tier_id": "subscription_tiers"}, direction="up"),
    TableSpec("trial_records", fks={"subscription_id": "subscriptions"}, direction="up"),
    TableSpec("system_config", natural_key="key", direction="up"),
    TableSpec("lab_report_counters", natural_key="year", direction="up"),
    TableSpec("test_types"),
    TableSpec("test_templates", fks={"test_type_id": "test_types"}),
    TableSpec(
        "referrers",
        natural_key="email",
        # The avatar is served as /uploads/referrers/<local id>.jpg, so on
        # arrival the file is stored under the receiving node's own id.
        files={"avatar_path": "uploads/referrers/{id}.jpg"},
    ),
    # No natural key: two different people must never be merged just because
    # they ended up with the same patient number.
    TableSpec("patients", fks={"branch_id": "branches", "referrer_id": "referrers"}),
    TableSpec("bookings", fks={"approved_by_user_id": "users", "referrer_id": "referrers"}),
    TableSpec("booking_items", fks={"booking_id": "bookings", "patient_id": "patients", "test_type_id": "test_types"}),
    TableSpec("payment_proofs", fks={"booking_id": "bookings", "verified_by": "users"}, files={"file_path": None}),
    TableSpec(
        "test_results",
        fks={"patient_id": "patients", "test_type_id": "test_types",
             "template_id": "test_templates", "branch_id": "branches"},
        exclude=("pdf_path",),
    ),
    TableSpec(
        "test_requests",
        fks={"patient_id": "patients", "test_type_id": "test_types",
             "test_result_id": "test_results", "branch_id": "branches"},
    ),
    TableSpec(
        "payments",
        fks={"patient_id": "patients", "created_by_id": "users", "branch_id": "branches"},
        csv_fks={"request_ids_csv": "test_requests"},
    ),
    TableSpec("referral_store", fks={"branch_id": "branches"}),
    TableSpec("referral_data", fks={"store_id": "referral_store", "patient_id": "patients",
                                    "test_request_id": "test_requests"}),
    TableSpec("referral_financial_records", fks={"referrer_id": "referrers", "payment_id": "payments"}),
    TableSpec("referral_batches", fks={"referrer_id": "referrers"}),
    TableSpec("referral_batch_links", fks={"test_request_id": "test_requests"}),
    TableSpec("referral_ledgers", fks={"referrer_id": "referrers"}),
    TableSpec("blood_donors", fks={"branch_id": "branches"}),
    TableSpec("blood_inventory", fks={"donor_id": "blood_donors", "branch_id": "branches"}),
    TableSpec("cross_matches", fks={"patient_id": "patients", "inventory_id": "blood_inventory",
                                    "branch_id": "branches"}),
    TableSpec("notifications", poly={"reference_id": ("reference_type", _REFERENCE_TYPES)}),
    TableSpec("voice_announcements", fks={"branch_id": "branches"},
              poly={"reference_id": ("reference_type", _REFERENCE_TYPES)}),
    TableSpec("audit_logs", poly={"entity_id": ("entity", _REFERENCE_TYPES)}),
]

BY_TABLE: dict[str, TableSpec] = {s.table: s for s in SPECS}
RANK: dict[str, int] = {s.table: i for i, s in enumerate(SPECS)}


def spec_for(table_name: str) -> TableSpec | None:
    return BY_TABLE.get(table_name)
