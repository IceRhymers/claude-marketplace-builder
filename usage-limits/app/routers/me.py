"""Current user identity endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.auth import UserIdentity
from deps import get_current_user
from schemas.auth import MeResponse

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me", response_model=MeResponse, operation_id="getMe")
def get_me(user: UserIdentity = Depends(get_current_user)):
    return MeResponse(
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
    )
