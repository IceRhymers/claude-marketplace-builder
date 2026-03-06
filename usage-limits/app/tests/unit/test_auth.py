"""Tests for core/auth.py — User identity resolution and admin checks."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.unit
class TestParseAdminGroups:
    def test_parses_csv(self):
        from core.auth import parse_admin_groups

        result = parse_admin_groups("group-a, group-b, group-c")
        assert result == ["group-a", "group-b", "group-c"]

    def test_empty_string_returns_empty_list(self):
        from core.auth import parse_admin_groups

        assert parse_admin_groups("") == []

    def test_strips_whitespace(self):
        from core.auth import parse_admin_groups

        result = parse_admin_groups("  alpha ,  beta  ")
        assert result == ["alpha", "beta"]

    def test_filters_empty_entries(self):
        from core.auth import parse_admin_groups

        result = parse_admin_groups("a,,b, ,c")
        assert result == ["a", "b", "c"]


@pytest.mark.unit
class TestIsAdmin:
    def test_admins_group_grants_admin(self):
        from core.auth import is_admin

        assert is_admin(["admins", "users"], []) is True

    def test_custom_group_grants_admin(self):
        from core.auth import is_admin

        assert is_admin(["data-team"], ["data-team", "ml-team"]) is True

    def test_no_matching_group_returns_false(self):
        from core.auth import is_admin

        assert is_admin(["users", "viewers"], ["data-team"]) is False

    def test_empty_groups_returns_false(self):
        from core.auth import is_admin

        assert is_admin([], []) is False

    def test_empty_admin_groups_only_admins_grants(self):
        from core.auth import is_admin

        assert is_admin(["admins"], []) is True
        assert is_admin(["some-group"], []) is False


@pytest.mark.unit
class TestResolveUserIdentity:
    def _make_mock_user(self, user_name, display_name, groups):
        user = MagicMock()
        user.user_name = user_name
        user.display_name = display_name
        group_values = []
        for g in groups:
            cv = MagicMock()
            cv.display = g
            group_values.append(cv)
        user.groups = group_values
        return user

    @patch("core.auth.WorkspaceClient")
    def test_resolves_admin_user(self, mock_wsc_class):
        from core.auth import resolve_user_identity

        mock_client = MagicMock()
        mock_user = self._make_mock_user("admin@example.com", "Admin User", ["admins", "users"])
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        identity = resolve_user_identity("valid-token", [])

        assert identity.email == "admin@example.com"
        assert identity.display_name == "Admin User"
        assert identity.groups == ["admins", "users"]
        assert identity.is_admin is True
        mock_wsc_class.assert_called_once_with(token="valid-token", auth_type="pat")

    @patch("core.auth.WorkspaceClient")
    def test_resolves_non_admin_user(self, mock_wsc_class):
        from core.auth import resolve_user_identity

        mock_client = MagicMock()
        mock_user = self._make_mock_user("user@example.com", "Regular User", ["users"])
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        identity = resolve_user_identity("valid-token", [])

        assert identity.email == "user@example.com"
        assert identity.is_admin is False

    @patch("core.auth.WorkspaceClient")
    def test_custom_admin_group_grants_admin(self, mock_wsc_class):
        from core.auth import resolve_user_identity

        mock_client = MagicMock()
        mock_user = self._make_mock_user("user@example.com", "Power User", ["data-team"])
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        identity = resolve_user_identity("valid-token", ["data-team"])

        assert identity.is_admin is True

    @patch("core.auth.WorkspaceClient")
    def test_invalid_token_raises(self, mock_wsc_class):
        from core.auth import resolve_user_identity

        mock_client = MagicMock()
        mock_client.current_user.me.side_effect = Exception("Invalid token")
        mock_wsc_class.return_value = mock_client

        with pytest.raises(Exception, match="Invalid token"):
            resolve_user_identity("bad-token", [])

    @patch("core.auth.WorkspaceClient")
    def test_user_with_no_groups(self, mock_wsc_class):
        from core.auth import resolve_user_identity

        mock_client = MagicMock()
        mock_user = self._make_mock_user("user@example.com", "No Groups", [])
        mock_user.groups = None
        mock_client.current_user.me.return_value = mock_user
        mock_wsc_class.return_value = mock_client

        identity = resolve_user_identity("valid-token", [])

        assert identity.groups == []
        assert identity.is_admin is False
