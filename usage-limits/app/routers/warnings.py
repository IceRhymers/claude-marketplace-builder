"""Warning management API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.warnings import get_active_warnings, mark_warning_resolved, log_audit_entry
from deps import get_db, require_admin
from schemas.warnings import WarningOut, ResolveWarningIn

router = APIRouter(prefix="/api/warnings", tags=["warnings"], dependencies=[Depends(require_admin)])


@router.get("/", response_model=list[WarningOut], operation_id="listActiveWarnings")
def list_active_warnings(session: Session = Depends(get_db)):
    rows = get_active_warnings(session)
    return [WarningOut(**r) for r in rows]


@router.post("/resolve", operation_id="resolveWarning")
def resolve_warning(body: ResolveWarningIn, session: Session = Depends(get_db)):
    mark_warning_resolved(session, body.warning_id)
    log_audit_entry(session, action="resolve_warning", details={"warning_id": body.warning_id})
    return {"resolved": True}
