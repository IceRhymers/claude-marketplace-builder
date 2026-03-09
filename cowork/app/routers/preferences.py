"""User skill and MCP server preferences endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import CurrentUser, get_current_user
from core.models import UserMcpPref, UserSkillPref
from core.skills import SkillsConfig
from deps import get_db, get_skills_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preferences")


class SkillPrefUpdate(BaseModel):
    enabled: bool


class McpPrefUpdate(BaseModel):
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


@router.get("/mcp")
def get_mcp_prefs(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    skills_config: SkillsConfig = Depends(get_skills_config),
):
    """Return all MCP servers with the user's preference state.

    Servers without a preference row default to enabled=true.
    """
    mcp_servers = (skills_config.mcp_config or {}).get("mcpServers", {})
    rows = db.query(UserMcpPref).filter(
        UserMcpPref.user_id == current_user.user_id
    ).all()
    prefs_by_name = {r.mcp_name: r.enabled for r in rows}
    return [
        {
            "name": name,
            "enabled": prefs_by_name.get(name, True),
        }
        for name in mcp_servers
    ]


@router.patch("/mcp/{mcp_name}")
def update_mcp_pref(
    mcp_name: str,
    body: McpPrefUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    skills_config: SkillsConfig = Depends(get_skills_config),
):
    """Upsert an MCP server preference for the authenticated user.

    Returns 404 if mcp_name is not in the current mcp_config["mcpServers"].
    """
    mcp_servers = (skills_config.mcp_config or {}).get("mcpServers", {})
    if mcp_name not in mcp_servers:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server not found: {mcp_name}",
        )

    row = db.query(UserMcpPref).filter_by(
        user_id=current_user.user_id,
        mcp_name=mcp_name,
    ).first()

    if row is None:
        row = UserMcpPref(
            user_id=current_user.user_id,
            mcp_name=mcp_name,
            enabled=body.enabled,
        )
        db.add(row)
    else:
        row.enabled = body.enabled

    db.commit()
    db.refresh(row)

    return {
        "name": mcp_name,
        "enabled": row.enabled,
    }
