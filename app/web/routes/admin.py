#app/web/routes/admin.py
from fastapi import APIRouter, Request, Form, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.payment_proof_model import PaymentProof
from app.services.payment_service import PaymentService
from app.services.notification_service import NotificationService
from app.models.notification_model import Notification
from app.models.booking_item import BookingItem
from app.api.deps import get_db
from app.models.user import User
from app.core.security import verify_password, create_token, decode_token
from app.core.config import settings
from app.models.branch import Branch
from app.services.branch_service import BranchService
from app.web.deps import get_current_admin
from typing import Optional
from app.services.dashboard_service import DashboardService
from app.core.config import settings
from datetime import datetime
from fastapi import HTTPException
from datetime import datetime, time, timezone # Add this import at the top

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


# =======================
# LOGIN PAGE
# =======================
@router.get("/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request})


# =======================
# LOGIN ACTION
# =======================
@router.post("/login")
def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()

    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "admin/login.html",
            {"request": request, "error": "Invalid credentials"},
        )

    token = create_token(
        subject=str(user.id),
        claims={
            "role": user.role,
            "branch_id": user.branch_id,
        },
        minutes=settings.JWT_EXPIRES_MIN,
    )

    response = RedirectResponse("/admin/dashboard", status_code=303)
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        max_age=settings.JWT_EXPIRES_MIN * 60,
    )
    return response


# =======================
# DASHBOARD (PATCHED)
# =======================
@router.get("/dashboard", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    branch_id: Optional[str] = None,
    financial_view: Optional[str] = None,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # 1. Setup & Service Initialization
    if branch_id == "": branch_id = None
    elif branch_id is not None:
        try: branch_id = int(branch_id)
        except ValueError: branch_id = None

    financial_view = financial_view or "payments"
    service = DashboardService(db, current_user, branch_id)

    # 2. Fetch Smart Metrics (using the patched DashboardService)
    metrics = service.get_metrics()
    today_metrics = service.get_today_metrics()
    trend_data = service.get_last_7_days_revenue()
    
    request.state.year = datetime.utcnow().year

    # 3. Chart Data Preparation
    trend_labels = [d.strftime("%d %b") for d, a in trend_data]
    trend_values = [float(a or 0) for d, a in trend_data]

    financial_data = []

    # 4. VIEW FILTERING LOGIC
    if financial_view == "payments":
        # Cash/Verified flow
        query = db.query(Booking).filter(
            Booking.status.in_(["payment_verified", "paid", "converted"])
        )
        #-------------------------------------------------------------------#

        financial_data = service._apply_branch_filter(query, Booking).order_by(Booking.created_at.desc()).limit(50).all()

    elif financial_view == "credit_pending":
        # Admin Authorization Queue
        query = db.query(Booking).filter(
            Booking.status.in_(["pending_approval", "pending"])
        )
        financial_data = service._apply_branch_filter(query, Booking).order_by(Booking.created_at.desc()).all()

    elif financial_view == "credit_approved":
        from sqlalchemy import func
        # SMART PATCH: The Grouped Debt Ledger
        # We group by booking_code and referrer_name to show "Batches"
        query = db.query(
            Booking.booking_code,
            Booking.referrer_name,
            func.count(Booking.id).label("patient_count"),
            func.sum(Booking.total_amount).label("total_batch_amount"),
            func.max(Booking.created_at).label("latest_date")
        ).filter(
            Booking.status == "approved_credit"
        ).group_by(
            Booking.booking_code, 
            Booking.referrer_name
        )
        
        # Apply branch security filters if applicable
        query = service._apply_branch_filter(query, Booking)
        financial_data = query.order_by(func.max(Booking.created_at).desc()).all()

    elif financial_view == "high_risk":
        # Placeholder for referrer debt analysis
        HIGH_RISK_THRESHOLD = 200000
        referrers = db.query(Booking.referrer_name).distinct().all()
        for (ref_name,) in referrers:
            # Note: This requires the calculate_referrer_outstanding method in DashboardService
            outstanding = service.calculate_referrer_outstanding(db, ref_name)
            if outstanding > HIGH_RISK_THRESHOLD:
                financial_data.append({"referrer_name": ref_name, "outstanding": outstanding})

    # 5. Branch Scope for Super Admin
    branches = db.query(Branch).order_by(Branch.name.asc()).all() if current_user.role == "super_admin" else []
    selected_branch_id = branch_id if current_user.role == "super_admin" else current_user.branch_id

    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "user": current_user,
            "branches": branches,
            "selected_branch_id": selected_branch_id,
            "metrics": metrics,
            "today_metrics": today_metrics,
            "trend_labels": trend_labels,
            "trend_values": trend_values,
            "financial_view": financial_view,
            "financial_data": financial_data,
            "settings": settings,
        },
    )

@router.get("/branches", response_class=HTMLResponse)
def branch_list(
    request: Request,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if current_user.role != "super_admin":
        return RedirectResponse("/admin/dashboard", status_code=303)

    service = BranchService(db)
    branches = service.list_branches()

    return templates.TemplateResponse(
        "admin/branches.html",
        {"request": request, "branches": branches},
    )


@router.get("/branches/create", response_class=HTMLResponse)
def branch_create_page(
    request: Request,
    current_user = Depends(get_current_admin),
):
    if current_user.role != "super_admin":
        return RedirectResponse("/admin/dashboard", status_code=303)

    return templates.TemplateResponse(
        "admin/branch_create.html",
        {"request": request},
    )


@router.post("/branches/create")
def branch_create(
    request: Request,
    name: str = Form(...),
    address: str = Form(""),
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if current_user.role != "super_admin":
        return RedirectResponse("/admin/dashboard", status_code=303)

    service = BranchService(db)
    service.create_branch(name=name, address=address)

    return RedirectResponse("/admin/branches", status_code=303)



from app.services.user_service import UserService


@router.get("/users", response_class=HTMLResponse)
def user_list(
    request: Request,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    service = UserService(db)
    users = service.list_users(current_user)

    return templates.TemplateResponse(
        "admin/users.html",
        {"request": request, "users": users, "current_user": current_user},
    )


@router.get("/users/create", response_class=HTMLResponse)
def user_create_page(
    request: Request,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    branches = db.query(Branch).all() if current_user.role == "super_admin" else []

    return templates.TemplateResponse(
        "admin/user_create.html",
        {"request": request, "branches": branches, "current_user": current_user},
    )


@router.post("/users/create")
def user_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    branch_id: int | None = Form(None),
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    service = UserService(db)
    service.create_user(current_user, username, password, role, branch_id)

    return RedirectResponse(
    "/admin/users?success=User created successfully",
    status_code=303
)




# -----------------------------------------
# Notifications
# -----------------------------------------

@router.get("/notifications")
def list_notifications(db: Session = Depends(get_db)):

    notifications = NotificationService.list_recent(db)

    return [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "reference_type": n.reference_type,
            "reference_id": n.reference_id,
            "is_read": n.is_read,
            "created_at": n.created_at
        }
        for n in notifications
    ]


@router.get("/notifications/unread-count")
def unread_count(db: Session = Depends(get_db)):

    count = NotificationService.unread_count(db)

    return {"count": count}


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db)
):

    NotificationService.mark_read(db, notification_id)

    return {"success": True}



@router.get("/bookings", response_class=HTMLResponse)
def admin_booking_list(
    request: Request,
    db: Session = Depends(get_db)
):

    bookings = (
        db.query(Booking)
        .order_by(Booking.created_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "admin/bookings_list.html",
        {
            "request": request,
            "bookings": bookings
        }
    )



@router.get("/bookings/{booking_id}", response_class=HTMLResponse)
def admin_booking_detail(
    request: Request,
    booking_id: int,
    db: Session = Depends(get_db)
):

    booking = db.query(Booking).filter(
        Booking.id == booking_id
    ).first()

    if not booking:
        raise HTTPException(status_code=404)

    proof = db.query(PaymentProof).filter(
        PaymentProof.booking_id == booking_id
    ).first()

    return templates.TemplateResponse(
        "admin/booking_detail.html",
        {
            "request": request,
            "booking": booking,
            "items": booking.items,
            "proof": proof
        }
    )

@router.post("/bookings/{proof_id}/approve")
def approve_payment(
    proof_id: int,
    db: Session = Depends(get_db)
):

    PaymentService.approve_payment(
        db=db,
        proof_id=proof_id,
        admin_id=1  # later replace with current_user.id
    )

    return {"status": "approved"}

from fastapi import Query

@router.post("/bookings/{proof_id}/reject")
def reject_payment(
    proof_id: int,
    note: str = Query(...),
    db: Session = Depends(get_db)
):

    PaymentService.reject_payment(
        db=db,
        proof_id=proof_id,
        admin_id=1,
        note=note
    )

    return {"status": "rejected"}


# -----------------------------------------
# CREDIT APPROVAL ACTION (STAYS THE SAME)
# -----------------------------------------
@router.post("/bookings/{booking_id}/approve-credit")
def approve_credit_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Only pending approval bookings can be approved")

    # Update Status
    booking.status = "approved_credit"
    booking.approved_by_user_id = current_user.id
    booking.approved_at = datetime.now(timezone.utc)
    db.commit()

    # Create the 'Smart' Notification that the Dashboard uses for Debt tracking
    NotificationService.create(
        db=db,
        type="credit_approved",
        title="Credit Booking Approved",
        message=f"Booking {booking.booking_code} approved.",
        reference_type="booking",
        reference_id=booking.id
    )

    return {"status": "approved_credit"}



# =========================================
# BATCH SETTLEMENT ACTION
# =========================================
@router.post("/finance/settle-batch/{booking_code}")
def settle_batch_payment(
    booking_code: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin)
):
    # Find all bookings in this specific batch that are still marked as debt
    bookings = db.query(Booking).filter(
        Booking.booking_code == booking_code,
        Booking.status == "approved_credit"
    ).all()

    if not bookings:
        raise HTTPException(status_code=404, detail="No outstanding credit found for this batch")

    for b in bookings:
        b.status = "paid" 
        # Optionally log who cleared the debt
        b.updated_at = datetime.datetime.utcnow()

    db.commit()

    # Create a notification for the audit trail
    NotificationService.create(
        db=db,
        type="debt_settled",
        title="Debt Batch Settled",
        message=f"Batch {booking_code} was marked as PAID by {current_user.username}.",
        reference_type="booking_batch",
        reference_id=0 # Batch level
    )

    return {"status": "success", "message": f"Batch {booking_code} settled"}





# =========================================
# PAYMENTS & RECONCILIATION
# =========================================

# 1. Keep this for the HTML page
@router.get("/payments/reconcile", response_class=HTMLResponse)
def reconciliation_page(request: Request, current_user = Depends(get_current_admin)):
    return templates.TemplateResponse("admin/reconciliation.html", {"request": request, "user": current_user})



@router.get("/payments/reconcile/data")
def reconciliation_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    service = PaymentService(db, current_user)
    
    # FIX: Use time.min and time.max for the 'combine' function
    start_dt = datetime.combine(datetime.strptime(start_date, "%Y-%m-%d"), time.min) if start_date else None
    end_dt = datetime.combine(datetime.strptime(end_date, "%Y-%m-%d"), time.max) if end_date else None
    
    payments = service.reconcile(start_date=start_dt, end_date=end_dt)
    summary = service.reconcile_summary(start_date=start_dt, end_date=end_dt)

    return {
        "payments": [
            {
                "created_at": p.created_at.isoformat(),
                "method": p.method,
                "amount": float(p.amount),
                "notes": p.notes or "",
                # Now works because of the relationship fix above
                "staff_name": p.created_by.username if p.created_by else "System",
                "branch_name": p.branch.name if p.branch else "N/A"
            } for p in payments
        ],
        "summary": summary
    }
