"""Unit tests for authorization module."""

import os

# Import the auth module
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.core.auth import get_authorized_users_info, is_user_authorized


class TestIsUserAuthorized:
    """Test cases for is_user_authorized function."""

    def test_authorized_by_username(self):
        """Test authorization by exact username match."""
        assert is_user_authorized(username="Colin_10NetZero") is True
        assert is_user_authorized(username="Bryan_10NetZero") is True
        assert is_user_authorized(username="Joel_10NetZero") is True

    def test_authorized_by_username_with_at_prefix(self):
        """Test authorization with @ prefix in username."""
        assert is_user_authorized(username="@Colin_10NetZero") is True
        assert is_user_authorized(username="@Bryan_10NetZero") is True

    def test_authorized_by_username_case_insensitive(self):
        """Test case-insensitive username matching."""
        assert is_user_authorized(username="colin_10netzero") is True
        assert is_user_authorized(username="BRYAN_10NETZERO") is True
        assert is_user_authorized(username="@JoEl_10NeTzErO") is True

    def test_unauthorized_username(self):
        """Test unauthorized usernames."""
        assert is_user_authorized(username="unauthorized_user") is False
        assert is_user_authorized(username="@random_person") is False
        assert is_user_authorized(username="hacker") is False

    def test_authorized_by_user_id(self):
        """Test authorization by user ID when added to list."""
        # Temporarily add a test user ID
        from src.core import auth

        original_ids = auth.AUTHORIZED_USER_IDS.copy()
        auth.AUTHORIZED_USER_IDS.append(12345)

        try:
            assert is_user_authorized(user_id=12345) is True
            assert is_user_authorized(user_id=88888) is False
        finally:
            auth.AUTHORIZED_USER_IDS = original_ids

    def test_user_id_takes_precedence(self):
        """Test that user ID authorization takes precedence over username."""
        from src.core import auth

        original_ids = auth.AUTHORIZED_USER_IDS.copy()
        auth.AUTHORIZED_USER_IDS.append(12345)

        try:
            # Authorized by ID even with wrong username
            assert is_user_authorized(username="wrong_name", user_id=12345) is True
        finally:
            auth.AUTHORIZED_USER_IDS = original_ids

    def test_edge_cases(self):
        """Test edge cases with None and empty values."""
        assert is_user_authorized() is False
        assert is_user_authorized(username=None) is False
        assert is_user_authorized(user_id=None) is False
        assert is_user_authorized(username="") is False
        assert is_user_authorized(username=None, user_id=None) is False

    def test_whitespace_handling(self):
        """Test handling of whitespace in usernames."""
        assert is_user_authorized(username=" Colin_10NetZero ") is False  # With spaces
        assert is_user_authorized(username="Colin_10NetZero\n") is False  # With newline


class TestEnvironmentLoading:
    """Test loading authorized users from environment variables."""

    @patch.dict(
        os.environ,
        {
            "AUTHORIZED_USERNAMES": '["env_user1", "env_user2"]',
            "AUTHORIZED_USER_IDS": "[111, 222]",
        },
    )
    def test_load_from_environment(self):
        """Test loading authorized users from environment."""
        # Need to reload the module to pick up env vars
        import importlib

        from src.core import auth

        importlib.reload(auth)

        # Check that env users are loaded
        assert "env_user1" in auth.AUTHORIZED_USERNAMES
        assert "env_user2" in auth.AUTHORIZED_USERNAMES
        assert 111 in auth.AUTHORIZED_USER_IDS
        assert 222 in auth.AUTHORIZED_USER_IDS

        # Verify authorization works with env users
        assert auth.is_user_authorized(username="env_user1") is True
        assert auth.is_user_authorized(user_id=111) is True

    @patch.dict(
        os.environ,
        {"AUTHORIZED_USERNAMES": "invalid json", "AUTHORIZED_USER_IDS": "[not valid]"},
    )
    def test_invalid_json_in_environment(self):
        """Test handling of invalid JSON in environment variables."""
        # Should not crash, just use defaults
        import importlib

        from src.core import auth

        # Capture the default values before reload
        default_usernames = ["Colin_10NetZero", "Bryan_10NetZero", "Joel_10NetZero"]

        # Reload should handle errors gracefully
        importlib.reload(auth)

        # Should still have default users
        for username in default_usernames:
            assert username in auth.AUTHORIZED_USERNAMES


class TestGetAuthorizedUsersInfo:
    """Test the get_authorized_users_info function."""

    def test_returns_correct_info(self):
        """Test that function returns correct authorization info."""
        info = get_authorized_users_info()

        assert "usernames" in info
        assert "user_ids" in info
        assert "total_authorized" in info

        assert isinstance(info["usernames"], list)
        assert isinstance(info["user_ids"], list)
        assert isinstance(info["total_authorized"], int)

        # Check default usernames are present
        assert "Colin_10NetZero" in info["usernames"]
        assert "Bryan_10NetZero" in info["usernames"]
        assert "Joel_10NetZero" in info["usernames"]
