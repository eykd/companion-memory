"""Tests for heartbeat functionality."""

import os
from unittest.mock import patch


def test_is_heartbeat_enabled_returns_true_when_env_var_set() -> None:
    """Test that is_heartbeat_enabled() returns True when ENABLE_HEARTBEAT=1."""
    from companion_memory.heartbeat import is_heartbeat_enabled

    with patch.dict(os.environ, {'ENABLE_HEARTBEAT': '1'}):
        assert is_heartbeat_enabled() is True


def test_is_heartbeat_enabled_returns_false_when_env_var_unset() -> None:
    """Test that is_heartbeat_enabled() returns False when ENABLE_HEARTBEAT is unset."""
    from companion_memory.heartbeat import is_heartbeat_enabled

    with patch.dict(os.environ, {}, clear=True):
        assert is_heartbeat_enabled() is False


def test_is_heartbeat_enabled_returns_false_when_env_var_falsey() -> None:
    """Test that is_heartbeat_enabled() returns False when ENABLE_HEARTBEAT is falsey."""
    from companion_memory.heartbeat import is_heartbeat_enabled

    with patch.dict(os.environ, {'ENABLE_HEARTBEAT': '0'}):
        assert is_heartbeat_enabled() is False

    with patch.dict(os.environ, {'ENABLE_HEARTBEAT': ''}):
        assert is_heartbeat_enabled() is False
