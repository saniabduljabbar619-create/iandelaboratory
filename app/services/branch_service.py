from sqlalchemy.orm import Session
from app.models.branch import Branch


class BranchService:

    def __init__(self, db: Session):
        self.db = db

    def list_branches(self):
        return self.db.query(Branch).order_by(Branch.id).all()

    def create_branch(self, name: str, address: str | None):
        count = self.db.query(Branch).count()
        code = f"SLB-{count + 1:03d}"

        branch = Branch(
            name=name,
            code=code,
            address=address,
        )

        self.db.add(branch)
        self.db.commit()
        self.db.refresh(branch)

        return branch
