"""User identity resolution and admin group membership checks."""

from __future__ import annotations

from dataclasses import dataclass

from databricks.sdk import WorkspaceClient


@dataclass(frozen=True)
class UserIdentity:
    """Resolved user identity from a Databricks access token."""

    email: str
    display_name: str
    groups: list[str]
    is_admin: bool


def parse_admin_groups(csv_str: str) -> list[str]:
    """Parse comma-separated group names, strip whitespace, filter empties."""
    return [g.strip() for g in csv_str.split(",") if g.strip()]


def is_admin(groups: list[str], admin_groups: list[str]) -> bool:
    """True if 'admins' in groups OR any admin_groups entry in groups."""
    group_set = set(groups)
    if "admins" in group_set:
        return True
    return bool(group_set & set(admin_groups))


def resolve_user_identity(token: str, admin_groups: list[str]) -> UserIdentity:
    """Create WorkspaceClient with user token, extract identity + groups, compute is_admin."""
    client = WorkspaceClient(token=token, auth_type="pat")
    user = client.current_user.me()
    groups = [g.display for g in user.groups] if user.groups else []
    return UserIdentity(
        email=user.user_name,
        display_name=user.display_name,
        groups=groups,
        is_admin=is_admin(groups, admin_groups),
    )
