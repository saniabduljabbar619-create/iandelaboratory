# -*- coding: utf-8 -*-
from __future__ import annotations

from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.models.booking import Booking
from app.models.referrer import Referrer
from app.models.booking_item import BookingItem
from app.models.test_type import TestType
from app.services.notification_service import NotificationService
from app.services.referrer_service import ReferrerService




class BookingService:

    def __init__(self, db: Session):
        self.db = db


    def create_booking(
        self,
        booking_type: str,
        referrer_name: str | None,
        referrer_phone: str | None,
        email: str | None,
        items: list[dict],
        billing_mode: str = "prepaid",
        referrer_id: int | None = None,
    ) -> Booking:

        if not items:
            raise HTTPException(status_code=400, detail="No patients added")

        try:

            total = Decimal("0.00")

            first = items[0]
            # ----------------------------------
            # PHASE 8: CREDIT VALIDATION
            # ----------------------------------

            referrer = None

            if billing_mode == "credit":

                if not referrer_id:
                    raise HTTPException(
                        status_code=400,
                        detail="Referrer is required for credit booking"
                    )

                referrer = (
                    self.db.query(Referrer)
                    .filter(Referrer.id == referrer_id)
                    .filter((Referrer.is_active == True) | (Referrer.is_active.is_(None)))
                    .first()
                )

                if not referrer:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid or inactive referrer"
                    )

                # overwrite snapshot values (VERY IMPORTANT)
                referrer_name = referrer.name
                referrer_phone = referrer.phone
            
            # ----------------------------------
            # AUTO-RESOLVE REFERRER (PORTAL FLOW)
            # ----------------------------------

            if referrer_phone and not referrer_id:
                referrer = (
                    self.db.query(Referrer)
                    .filter(Referrer.phone == referrer_phone)
                    .first()
                )

                if not referrer:
                    referrer = Referrer(
                        name=referrer_name or "Unknown Referrer",
                        phone=referrer_phone,
                        credit_limit=500000,   # default
                        is_active=True
                    )
                    self.db.add(referrer)
                    self.db.flush()  # 🔥 IMPORTANT

                referrer_id = referrer.id

            booking = Booking(
                booking_code="TEMP",
                # compatibility fields for existing schema
                full_name=first["patient_name"],
                phone=first["patient_phone"],
                email=email,
                dob=first.get("dob"),
                gender=first.get("gender"),

                booking_type=booking_type,
                billing_mode=billing_mode,
                referrer_id=referrer_id,
                referrer_name=referrer_name,
                referrer_phone=referrer_phone,

                total_amount=Decimal("0.00"),
                status="pending",
            )

            self.db.add(booking)
            self.db.flush()

            booking.booking_code = f"SLB-BKG-{booking.id:04d}"

            for entry in items:

                test = (
                    self.db.query(TestType)
                    .filter(TestType.id == entry["test_type_id"])
                    .filter(TestType.is_active == True)
                    .first()
                )

                if not test:
                    raise HTTPException(status_code=400, detail="Invalid test")

                total += Decimal(test.price)

                item = BookingItem(
                    booking_id=booking.id,
                    patient_id=entry.get("patient_id"),   # ✅ NEW
                    patient_name=entry["patient_name"],
                    patient_phone=entry["patient_phone"],
                    dob=entry.get("dob"),
                    gender=entry.get("gender"),
                    test_type_id=test.id,
                    test_name_snapshot=test.name,
                    price_snapshot=test.price,
                )

                self.db.add(item)

            booking.total_amount = total

            self.db.commit()
            self.db.refresh(booking)

            # --------------------------------------------------
            # Create Admin Notification
            # --------------------------------------------------

            NotificationService.create(
                db=self.db,
                type="booking_created",
                title="New Test Booking",
                message=f"New booking {booking.booking_code} from {booking.full_name}",
                reference_type="booking",
                reference_id=booking.id
            )

            return booking

        except SQLAlchemyError as e:
            self.db.rollback()
            print("BOOKING ERROR:", str(e))
            raise HTTPException(status_code=500, detail=str(e))


    

    def create_group_booking(
        self,
        referrer_name,
        email,
        referrer_phone,
        items,
        billing_mode: str = "prepaid",
        referrer_id: int | None = None,
    ):

        if not items:
            raise HTTPException(status_code=400, detail="No patients in group booking")

        try:

            total = Decimal("0.00")

            # --------------------------------------------------
            # Use first patient as booking anchor
            # --------------------------------------------------

            first_patient = items[0]

            # ----------------------------------
            # PHASE 8: CREDIT VALIDATION
            # ----------------------------------

            referrer = None

            if billing_mode == "credit":

                if not referrer_id:
                    raise HTTPException(
                        status_code=400,
                        detail="Referrer is required for credit booking"
                    )

                referrer = (
                    self.db.query(Referrer)
                    .filter(Referrer.id == referrer_id)
                    .filter(Referrer.is_active == True)
                    .first()
                )

                if not referrer:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid or inactive referrer"
                    )

                # overwrite snapshot values (VERY IMPORTANT)
                referrer_name = referrer.name
                referrer_phone = referrer.phone

            # ----------------------------------
            # AUTO-RESOLVE REFERRER (PORTAL FLOW)
            # ----------------------------------

            if referrer_phone and not referrer_id:
                referrer = (
                    self.db.query(Referrer)
                    .filter(Referrer.phone == referrer_phone)
                    .first()
                )

                if not referrer:
                    referrer = Referrer(
                        name=referrer_name or "Unknown Referrer",
                        phone=referrer_phone,
                        credit_limit=500000,   # default
                        is_active=True
                    )
                    self.db.add(referrer)
                    self.db.flush()  # 🔥 IMPORTANT

                referrer_id = referrer.id

            booking = Booking(
                booking_code="TEMP",
                booking_type="group",

                # required booking columns
                full_name=first_patient["patient_name"],
                email = email,
                phone=first_patient["patient_phone"],
                dob=None,
                gender=None,
                billing_mode=billing_mode,
                referrer_id=referrer_id,
                referrer_name=referrer_name,
                referrer_phone=referrer_phone,

                total_amount=Decimal("0.00"),
                status="pending"
            )

            self.db.add(booking)
            self.db.flush()

            # --------------------------------------------------
            # Generate booking code
            # --------------------------------------------------

            booking.booking_code = f"SLB-BKG-{booking.id:04d}"

            # --------------------------------------------------
            # Insert booking items
            # --------------------------------------------------
            print(items)
            for item in items:

                price = Decimal(str(item["price"]))
                total += price

                bi = BookingItem(
                    booking_id=booking.id,
                    test_type_id=item.get("test_type_id"),   # REQUIRED
                    test_name_snapshot=item["test_name"],
                    price_snapshot=price,

                    patient_name=item["patient_name"],
                    patient_phone=item["patient_phone"],

                    dob=item.get("dob"),
                    gender=item.get("gender")
                )

                self.db.add(bi)

            # --------------------------------------------------
            # Update booking total
            # --------------------------------------------------

            booking.total_amount = total

            self.db.commit()
            self.db.refresh(booking)

            # --------------------------------------------------
            # Admin Notification
            # --------------------------------------------------

            NotificationService.create(
                db=self.db,
                type="group_booking_created",
                title="New Group Booking",
                message=f"Group booking {booking.booking_code} created by {booking.referrer_name}",
                reference_type="booking",
                reference_id=booking.id
            )

            return booking

        except Exception:
            self.db.rollback()
            raise