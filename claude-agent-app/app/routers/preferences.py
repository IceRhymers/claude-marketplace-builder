"""User skill preferences endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import CurrentUser, get_current_user
from core.models import UserSkillPref
from core.skills import SkillsConfig
from deps import get_db, get_skills_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preferences")


class SkillPrefUpdate(BaseModel):
    enabled: bool


@router.get("/skills")
def get_skill_prefs(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    skills_config: SkillsConfig = Depends(get_skills_config),
):
    """Return all skills with the user's preference state.

    Skills without a preference row default to enabled=true.
    """
    rows = db.query(UserSkillPref).filter(
        UserSkillPref.user_id == current_user.user_id
    ).all()
    prefs_by_name = {r.skill_name: r.enabled for r in rows}
    return [
        {
            "name": name,
            "enabled": prefs_by_name.get(name, True),
            "has_scripts": sd.has_scripts,
            "has_references": sd.has_references,
        }
        for name, sd in skills_config.skills.items()
    ]


@router.patch("/skills/{skill_name}")
def update_skill_pref(
    skill_name: str,
    body: SkillPrefUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    skills_config: SkillsConfig = Depends(get_skills_config),
):
    """Upsert a skill preference for the authenticated user.

    Returns 404 if skill_name is not in the current SkillsConfig.
    """
    if skill_name not in skills_config.skills:
        raise HTTPException(
            status_code=404,
            detail=f"Skill not found: {skill_name}",
        )

    row = db.query(UserSkillPref).filter_by(
        user_id=current_user.user_id,
        skill_name=skill_name,
    ).first()

    if row is None:
        row = UserSkillPref(
            user_id=current_user.user_id,
            skill_name=skill_name,
            enabled=body.enabled,
        )
        db.add(row)
    else:
        row.enabled = body.enabled

    db.commit()
    db.refresh(row)

    sd = skills_config.skills[skill_name]
    return {
        "name": skill_name,
        "enabled": row.enabled,
        "has_scripts": sd.has_scripts,
        "has_references": sd.has_references,
    }
