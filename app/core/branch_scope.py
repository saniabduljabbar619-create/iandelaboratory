from fastapi import HTTPException

def resolve_branch_scope(current_user, requested_branch_id=None):
    """
    Returns effective branch_id to filter with.
    Enforces branch-level isolation.
    """

    # SUPER ADMIN
    if current_user.role == "super_admin":
        # Super admin can filter by branch if provided
        if requested_branch_id:
            return requested_branch_id
        return None  # None = all branches

    # All other roles are branch-bound
    if not current_user.branch_id:
        raise HTTPException(
            status_code=400,
            detail="Branch-bound user has no branch_id assigned."
        )

    # Ignore requested branch_id for non-super users
    return current_user.branch_id
