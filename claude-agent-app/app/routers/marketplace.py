"""Marketplace endpoints for skills and MCP configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.auth import CurrentUser, get_current_user
from core.skills import SkillsConfig
from deps import get_skills_config

router = APIRouter(prefix="/api")


@router.get("/skills")
def list_skills(
    current_user: CurrentUser = Depends(get_current_user),
    skills_config: SkillsConfig = Depends(get_skills_config),
):
    """Return the list of loaded skill definitions."""
    return [
        {"name": name, "has_scripts": sd.has_scripts, "has_references": sd.has_references}
        for name, sd in skills_config.skills.items()
    ]


@router.get("/mcp")
def get_mcp_config(
    current_user: CurrentUser = Depends(get_current_user),
    skills_config: SkillsConfig = Depends(get_skills_config),
):
    """Return the raw MCP server configuration (without token substitution)."""
    return skills_config.mcp_config
