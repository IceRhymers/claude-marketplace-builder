"""GET /api/me — return current user identity."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/api")


@router.get("/me")
def get_me(current_user: CurrentUser = Depends(get_current_user)):
    """Return the authenticated user's identity."""
    return {
        "user_id": current_user.user_id,
        "display_name": current_user.user_id,  # Use email as display name (no separate field)
    }
