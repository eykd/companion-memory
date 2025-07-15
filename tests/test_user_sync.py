"""Tests for user sync functionality."""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.block_network


def test_sync_user_timezone_no_user_id() -> None:
    """Test sync_user_timezone when SLACK_USER_ID is not set."""
    from companion_memory.user_sync import sync_user_timezone

    with patch.dict('os.environ', {}, clear=True):
        sync_user_timezone()
        # Should log warning and return early


def test_sync_user_timezone_slack_api_failure() -> None:
    """Test sync_user_timezone when Slack API returns failure."""
    from companion_memory.user_sync import sync_user_timezone

    mock_slack_client = MagicMock()
    mock_slack_client.users_info.return_value = {'ok': False, 'error': 'user_not_found'}

    with (
        patch.dict('os.environ', {'SLACK_USER_ID': 'U123456789'}),
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client),
    ):
        sync_user_timezone()
        # Should log warning and return early


def test_sync_user_timezone_no_timezone_in_profile() -> None:
    """Test sync_user_timezone when user profile has no timezone."""
    from companion_memory.user_sync import sync_user_timezone

    mock_slack_client = MagicMock()
    mock_slack_client.users_info.return_value = {'ok': True, 'user': {'id': 'U123456789'}}

    with (
        patch.dict('os.environ', {'SLACK_USER_ID': 'U123456789'}),
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client),
    ):
        sync_user_timezone()
        # Should log info and return early


def test_sync_user_timezone_success() -> None:
    """Test sync_user_timezone successful timezone sync."""
    from companion_memory.user_sync import sync_user_timezone

    mock_slack_client = MagicMock()
    mock_slack_client.users_info.return_value = {'ok': True, 'user': {'id': 'U123456789', 'tz': 'America/New_York'}}

    mock_settings_store = MagicMock()

    with (
        patch.dict('os.environ', {'SLACK_USER_ID': 'U123456789'}),
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client),
        patch('companion_memory.user_sync.DynamoUserSettingsStore', return_value=mock_settings_store),
    ):
        sync_user_timezone()

    # Verify settings store was called with correct data
    mock_settings_store.update_user_settings.assert_called_once_with('U123456789', {'timezone': 'America/New_York'})


def test_sync_user_timezone_exception_handling() -> None:
    """Test sync_user_timezone handles exceptions gracefully."""
    from companion_memory.user_sync import sync_user_timezone

    mock_slack_client = MagicMock()
    mock_slack_client.users_info.side_effect = Exception('Network error')

    with (
        patch.dict('os.environ', {'SLACK_USER_ID': 'U123456789'}),
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client),
    ):
        # Should not raise exception - it should be caught and logged
        sync_user_timezone()


def test_sync_user_timezone_from_slack_success() -> None:
    """Test sync_user_timezone_from_slack successful timezone sync."""
    from companion_memory.user_sync import sync_user_timezone_from_slack

    mock_slack_client = MagicMock()
    mock_slack_client.users_info.return_value = {'ok': True, 'user': {'id': 'U123456789', 'tz': 'America/New_York'}}

    mock_settings_store = MagicMock()

    with (
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client),
        patch('companion_memory.user_sync.DynamoUserSettingsStore', return_value=mock_settings_store),
    ):
        result = sync_user_timezone_from_slack('U123456789')

    # Verify return value
    assert result == 'America/New_York'

    # Verify settings store was called with correct data
    mock_settings_store.update_user_settings.assert_called_once_with('U123456789', {'timezone': 'America/New_York'})


def test_sync_user_timezone_from_slack_api_failure() -> None:
    """Test sync_user_timezone_from_slack when Slack API returns failure."""
    from companion_memory.user_sync import sync_user_timezone_from_slack

    mock_slack_client = MagicMock()
    mock_slack_client.users_info.return_value = {'ok': False, 'error': 'user_not_found'}

    with patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client):
        result = sync_user_timezone_from_slack('U123456789')

    # Should return None on failure
    assert result is None


def test_sync_user_timezone_from_slack_no_timezone() -> None:
    """Test sync_user_timezone_from_slack when user profile has no timezone."""
    from companion_memory.user_sync import sync_user_timezone_from_slack

    mock_slack_client = MagicMock()
    mock_slack_client.users_info.return_value = {'ok': True, 'user': {'id': 'U123456789'}}

    with patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client):
        result = sync_user_timezone_from_slack('U123456789')

    # Should return None when no timezone in profile
    assert result is None


def test_sync_user_timezone_from_slack_exception() -> None:
    """Test sync_user_timezone_from_slack handles exceptions gracefully."""
    from companion_memory.user_sync import sync_user_timezone_from_slack

    mock_slack_client = MagicMock()
    mock_slack_client.users_info.side_effect = Exception('Network error')

    with patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client):
        result = sync_user_timezone_from_slack('U123456789')

    # Should return None on exception
    assert result is None
