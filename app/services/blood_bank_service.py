# -*- coding: utf-8 -*-
# app/services/blood_bank_service.py
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.blood_bank import BloodDonor, BloodInventory, CrossMatch


VALID_BLOOD_GROUPS = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
VALID_GENOTYPES = {"AA", "AS", "SS", "AC", "SC"}
VALID_COMPONENTS = {"Whole Blood", "Plasma", "Platelets", "Packed RBC"}

# ABO/Rh red-cell compatibility: donor group → set of patient groups that
# can SAFELY receive it. This is clinical truth; do not alter without review.
RBC_COMPATIBILITY = {
    "O-":  {"O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"},  # universal donor
    "O+":  {"O+", "A+", "B+", "AB+"},
    "A-":  {"A-", "A+", "AB-", "AB+"},
    "A+":  {"A+", "AB+"},
    "B-":  {"B-", "B+", "AB-", "AB+"},
    "B+":  {"B+", "AB+"},
    "AB-": {"AB-", "AB+"},
    "AB+": {"AB+"},
}


def is_compatible(donor_group: str, patient_group: str) -> bool:
    d = (donor_group or "").strip().upper().replace(" ", "")
    p = (patient_group or "").strip().upper().replace(" ", "")
    allowed = RBC_COMPATIBILITY.get(d)
    if allowed is None:
        return False  # unknown donor group → refuse (safe default)
    return p in allowed


class BloodBankService:

    def __init__(self, db: Session, branch_id: int):
        self.db = db
        self.branch_id = branch_id

    # --------------------------------------------------
    # DONORS
    # --------------------------------------------------

    def register_donor(self, data: dict) -> BloodDonor:
        blood_group = data.get("blood_group", "").strip().upper()
        if blood_group not in VALID_BLOOD_GROUPS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid blood group '{blood_group}'. Valid: {sorted(VALID_BLOOD_GROUPS)}"
            )

        genotype = (data.get("genotype") or "").strip().upper() or None
        if genotype and genotype not in VALID_GENOTYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid genotype '{genotype}'. Valid: {sorted(VALID_GENOTYPES)}"
            )

        donor = BloodDonor(
            full_name=data["full_name"].strip(),
            phone=data["phone"].strip(),
            date_of_birth=data.get("date_of_birth"),
            gender=data.get("gender"),
            blood_group=blood_group,
            genotype=genotype,
            address=data.get("address"),
            is_eligible=True,
            donation_count=0,
            branch_id=self.branch_id,
        )
        self.db.add(donor)
        self.db.commit()
        self.db.refresh(donor)
        return donor

    def get_donor(self, donor_id: int) -> BloodDonor:
        donor = self.db.query(BloodDonor).filter(
            BloodDonor.id == donor_id,
            BloodDonor.branch_id == self.branch_id,
        ).first()
        if not donor:
            raise HTTPException(status_code=404, detail="Donor not found.")
        return donor

    def list_donors(
        self,
        blood_group: Optional[str] = None,
        eligible_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BloodDonor], int]:
        q = self.db.query(BloodDonor).filter(
            BloodDonor.branch_id == self.branch_id
        )
        if blood_group:
            q = q.filter(BloodDonor.blood_group == blood_group.upper().strip())
        if eligible_only:
            q = q.filter(BloodDonor.is_eligible == True)
        total = q.count()
        donors = q.order_by(BloodDonor.full_name).offset(offset).limit(limit).all()
        return donors, total

    def mark_ineligible(self, donor_id: int, reason: str) -> BloodDonor:
        donor = self.get_donor(donor_id)
        donor.is_eligible = False
        donor.ineligibility_reason = reason
        self.db.commit()
        self.db.refresh(donor)
        return donor

    def record_donation(self, donor_id: int, donation_date: date) -> BloodDonor:
        donor = self.get_donor(donor_id)
        if not donor.is_eligible:
            raise HTTPException(
                status_code=400,
                detail=f"Donor is not eligible: {donor.ineligibility_reason}"
            )
        donor.donation_count += 1
        donor.last_donation_date = donation_date
        self.db.commit()
        self.db.refresh(donor)
        return donor

    # --------------------------------------------------
    # INVENTORY
    # --------------------------------------------------

    def add_to_inventory(self, data: dict) -> BloodInventory:
        blood_group = data.get("blood_group", "").strip().upper()
        if blood_group not in VALID_BLOOD_GROUPS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid blood group '{blood_group}'."
            )

        component = data.get("component", "").strip()
        if component not in VALID_COMPONENTS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid component '{component}'. Valid: {sorted(VALID_COMPONENTS)}"
            )

        expiry = data.get("expiry_date")
        if isinstance(expiry, str):
            expiry = date.fromisoformat(expiry)
        if expiry and expiry < date.today():
            raise HTTPException(status_code=400, detail="Expiry date cannot be in the past.")

        item = BloodInventory(
            blood_group=blood_group,
            component=component,
            units_available=data.get("units_available", 1),
            units_reserved=0,
            collection_date=data.get("collection_date") or date.today(),
            expiry_date=expiry,
            donor_id=data.get("donor_id"),
            batch_no=data.get("batch_no"),
            status="available",
            branch_id=self.branch_id,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_inventory(self, inventory_id: int) -> BloodInventory:
        item = self.db.query(BloodInventory).filter(
            BloodInventory.id == inventory_id,
            BloodInventory.branch_id == self.branch_id,
        ).first()
        if not item:
            raise HTTPException(status_code=404, detail="Inventory item not found.")
        return item

    def list_inventory(
        self,
        blood_group: Optional[str] = None,
        component: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BloodInventory], int]:
        q = self.db.query(BloodInventory).filter(
            BloodInventory.branch_id == self.branch_id
        )
        if blood_group:
            q = q.filter(BloodInventory.blood_group == blood_group.upper().strip())
        if component:
            q = q.filter(BloodInventory.component == component)
        if status:
            q = q.filter(BloodInventory.status == status)
        total = q.count()
        items = q.order_by(BloodInventory.expiry_date).offset(offset).limit(limit).all()
        return items, total

    def get_stock_summary(self) -> list[dict]:
        """Returns available units per blood group and component."""
        items = self.db.query(BloodInventory).filter(
            BloodInventory.branch_id == self.branch_id,
            BloodInventory.status == "available",
        ).all()

        summary: dict[str, dict] = {}
        for item in items:
            key = f"{item.blood_group}|{item.component}"
            if key not in summary:
                summary[key] = {
                    "blood_group": item.blood_group,
                    "component": item.component,
                    "units_available": 0,
                }
            summary[key]["units_available"] += item.units_available

        return sorted(summary.values(), key=lambda x: (x["blood_group"], x["component"]))

    def expire_stale_inventory(self) -> int:
        """Marks all past-expiry available items as expired. Returns count."""
        items = self.db.query(BloodInventory).filter(
            BloodInventory.branch_id == self.branch_id,
            BloodInventory.status == "available",
            BloodInventory.expiry_date < date.today(),
        ).all()
        for item in items:
            item.status = "expired"
        self.db.commit()
        return len(items)

    # --------------------------------------------------
    # CROSS MATCH
    # --------------------------------------------------

    def request_cross_match(self, data: dict) -> CrossMatch:
        inventory_item = self.get_inventory(data["inventory_id"])

        if inventory_item.status != "available":
            raise HTTPException(
                status_code=400,
                detail=f"Blood unit is not available (status: {inventory_item.status})."
            )

        # ── SAFETY HARD BLOCK: ABO/Rh compatibility ──
        from app.models.patient import Patient
        patient = self.db.query(Patient).filter(Patient.id == data["patient_id"]).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found.")
        # Tech confirms the patient's group at the bench (against the report).
        confirmed = (data.get("patient_blood_group") or "").strip().upper()
        if confirmed:
            patient.blood_group = confirmed   # persist the confirmed group
        patient_group = confirmed or getattr(patient, "blood_group", None)
        if not patient_group:
            raise HTTPException(
                status_code=400,
                detail="Patient blood group is unknown. Confirm the patient's group before cross-matching."
            )
        if not is_compatible(inventory_item.blood_group, patient_group):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"INCOMPATIBLE: a {inventory_item.blood_group} unit cannot be given to a "
                    f"{patient_group} patient. Transfusion blocked to prevent a haemolytic reaction."
                ),
            )


        # Reserve the unit immediately
        inventory_item.status = "reserved"
        inventory_item.units_reserved += 1

        cm = CrossMatch(
            patient_id=data["patient_id"],
            inventory_id=data["inventory_id"],
            requested_by=data.get("requested_by"),
            result="pending",
            branch_id=self.branch_id,
        )
        self.db.add(cm)
        self.db.commit()
        self.db.refresh(cm)
        return cm

    def record_cross_match_result(
        self,
        cross_match_id: int,
        result: str,
        performed_by: str,
        notes: Optional[str] = None,
    ) -> CrossMatch:
        cm = self.db.query(CrossMatch).filter(
            CrossMatch.id == cross_match_id,
            CrossMatch.branch_id == self.branch_id,
        ).first()
        if not cm:
            raise HTTPException(status_code=404, detail="Cross match record not found.")

        valid_results = {"compatible", "incompatible"}
        if result not in valid_results:
            raise HTTPException(
                status_code=400,
                detail=f"Result must be one of: {valid_results}"
            )

        cm.result = result
        cm.performed_by = performed_by
        cm.compatibility_notes = notes
        cm.performed_at = datetime.utcnow()

        # If incompatible, release the reservation
        if result == "incompatible":
            inventory_item = self.get_inventory(cm.inventory_id)
            inventory_item.status = "available"
            inventory_item.units_reserved = max(0, inventory_item.units_reserved - 1)

        self.db.commit()
        self.db.refresh(cm)
        return cm

    def list_cross_matches(
        self,
        patient_id: Optional[int] = None,
        result_filter: Optional[str] = None,
        limit: int = 50,
    ) -> list[CrossMatch]:
        q = self.db.query(CrossMatch).filter(
            CrossMatch.branch_id == self.branch_id
        )
        if patient_id:
            q = q.filter(CrossMatch.patient_id == patient_id)
        if result_filter:
            q = q.filter(CrossMatch.result == result_filter)
        return q.order_by(CrossMatch.created_at.desc()).limit(limit).all()
    
    
    