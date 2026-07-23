#app/services/user_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.user import User
from app.models.branch import Branch
from app.core.security import hash_password


class UserService:

    def __init__(self, db: Session):
        self.db = db

    def list_users(self, current_user: User):
        query = self.db.query(User)

        if current_user.role != "super_admin":
            query = query.filter(User.branch_id == current_user.branch_id)

        return query.order_by(User.id).all()

    def create_user(
        self,
        current_user: User,
        username: str,
        password: str,
        role: str,
        branch_id: int | None,
    ):
        # Prevent duplicate usernames
        if self.db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="Username already exists")

        # Disallow creating super_admin
        if role == "super_admin":
            raise HTTPException(status_code=403, detail="Cannot create super_admin")

        # SUPER ADMIN LOGIC
        if current_user.role == "super_admin":
            if role == "branch_admin" or role == "lab_staff" or role == "cashier":
                if not branch_id:
                    raise HTTPException(status_code=400, detail="Branch required")

                branch = self.db.query(Branch).filter(Branch.id == branch_id).first()
                if not branch:
                    raise HTTPException(status_code=404, detail="Branch not found")

            else:
                raise HTTPException(status_code=403, detail="Invalid role")

        # BRANCH ADMIN LOGIC
        elif current_user.role == "branch_admin":
            if role not in ["lab_staff", "cashier"]:
                raise HTTPException(status_code=403, detail="Insufficient permission")

            branch_id = current_user.branch_id

        else:
            raise HTTPException(status_code=403, detail="Insufficient permission")

        user = User(
            username=username,
            password_hash=hash_password(password),
            role=role,
            branch_id=branch_id,
            is_active=True,
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        return user
    
    
    def get_user(self, current_user: User, user_id: int) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        # Branch admins can only touch their own branch's users
        if current_user.role != "super_admin" and user.branch_id != current_user.branch_id:
            raise HTTPException(status_code=403, detail="Insufficient permission")
        return user

    def update_user(
        self,
        current_user: User,
        user_id: int,
        role: str,
        branch_id: int | None,
    ):
        user = self.get_user(current_user, user_id)

        if user.role == "super_admin" or role == "super_admin":
            raise HTTPException(status_code=403, detail="Cannot modify super_admin accounts")

        if current_user.role == "super_admin":
            if role in ("branch_admin", "lab_staff", "cashier"):
                if not branch_id:
                    raise HTTPException(status_code=400, detail="Branch required")
                branch = self.db.query(Branch).filter(Branch.id == branch_id).first()
                if not branch:
                    raise HTTPException(status_code=404, detail="Branch not found")
            else:
                raise HTTPException(status_code=403, detail="Invalid role")
        elif current_user.role == "branch_admin":
            if role not in ("lab_staff", "cashier"):
                raise HTTPException(status_code=403, detail="Insufficient permission")
            branch_id = current_user.branch_id
        else:
            raise HTTPException(status_code=403, detail="Insufficient permission")

        user.role = role
        user.branch_id = branch_id
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_active(self, current_user: User, user_id: int, active: bool):
        user = self.get_user(current_user, user_id)
        if user.role == "super_admin":
            raise HTTPException(status_code=403, detail="Cannot deactivate super_admin accounts")
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
        user.is_active = active
        self.db.commit()
        self.db.refresh(user)
        return user

    def reset_password(self, current_user: User, user_id: int, new_password: str):
        user = self.get_user(current_user, user_id)
        if user.role == "super_admin" and current_user.id != user.id:
            raise HTTPException(status_code=403, detail="Cannot reset super_admin password")
        user.password_hash = hash_password(new_password)
        self.db.commit()
        return user
