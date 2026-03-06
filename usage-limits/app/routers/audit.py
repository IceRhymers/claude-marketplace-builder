"""Audit log API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.models import AuditLog
from deps import get_db, require_admin
from schemas.audit import AuditLogOut

router = APIRouter(prefix="/api/audit", tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("/", response_model=list[AuditLogOut], operation_id="listAuditLog")
def list_audit_log(limit: int = 100, session: Session = Depends(get_db)):
    rows = (
        session.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        AuditLogOut(
            id=r.id,
            action=r.action,
            user_id=r.user_id,
            details=r.details,
            created_at=r.created_at,
        )
        for r in rows
    ]
