"""Budget management API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.budget import propagate_default_budget, save_budget_config, save_default_budget
from core.models import BudgetConfig, DefaultBudget
from core.warnings import log_audit_entry
from deps import get_db, require_admin
from schemas.budgets import BudgetConfigIn, BudgetConfigOut, DefaultBudgetIn, DefaultBudgetOut

router = APIRouter(prefix="/api/budgets", tags=["budgets"], dependencies=[Depends(require_admin)])


@router.get("/", response_model=list[BudgetConfigOut], operation_id="listBudgets")
def list_budgets(session: Session = Depends(get_db)):
    rows = session.query(BudgetConfig).all()
    return [BudgetConfigOut(**r.to_dict()) for r in rows]


@router.post("/", response_model=BudgetConfigOut, operation_id="saveBudget")
def save_budget(body: BudgetConfigIn, session: Session = Depends(get_db)):
    save_budget_config(
        session,
        entity_type="user",
        entity_id=body.entity_id,
        daily_limit=body.daily_dollar_limit,
        weekly_limit=body.weekly_dollar_limit,
        monthly_limit=body.monthly_dollar_limit,
        is_custom=True,
    )
    log_audit_entry(session, action="save_budget", user_id=body.entity_id, details={
        "daily": body.daily_dollar_limit,
        "weekly": body.weekly_dollar_limit,
        "monthly": body.monthly_dollar_limit,
    })
    row = (
        session.query(BudgetConfig)
        .filter(BudgetConfig.entity_type == "user", BudgetConfig.entity_id == body.entity_id)
        .first()
    )
    return BudgetConfigOut(**row.to_dict())


@router.delete("/{budget_id}", operation_id="deleteBudget")
def delete_budget(budget_id: int, session: Session = Depends(get_db)):
    row = session.get(BudgetConfig, budget_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    log_audit_entry(session, action="delete_budget", user_id=row.entity_id)
    session.delete(row)
    session.commit()
    return {"deleted": True}


@router.get("/default", response_model=DefaultBudgetOut | None, operation_id="getDefaultBudget")
def get_default_budget(session: Session = Depends(get_db)):
    row = session.query(DefaultBudget).order_by(DefaultBudget.id.desc()).first()
    if row is None:
        return None
    return DefaultBudgetOut(**row.to_dict())


@router.post("/default", response_model=DefaultBudgetOut, operation_id="saveDefaultBudget")
def save_default(body: DefaultBudgetIn, session: Session = Depends(get_db)):
    save_default_budget(
        session,
        daily_limit=body.daily_dollar_limit,
        weekly_limit=body.weekly_dollar_limit,
        monthly_limit=body.monthly_dollar_limit,
    )
    propagated_count = propagate_default_budget(
        session,
        daily_limit=body.daily_dollar_limit,
        weekly_limit=body.weekly_dollar_limit,
        monthly_limit=body.monthly_dollar_limit,
    )
    log_audit_entry(session, action="save_default_budget", details={
        "daily": body.daily_dollar_limit,
        "weekly": body.weekly_dollar_limit,
        "monthly": body.monthly_dollar_limit,
        "propagated_count": propagated_count,
    })
    row = session.query(DefaultBudget).order_by(DefaultBudget.id.desc()).first()
    return DefaultBudgetOut(**row.to_dict())
