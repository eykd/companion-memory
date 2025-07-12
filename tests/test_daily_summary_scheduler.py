"""Tests for daily summary scheduling functionality."""

from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest


@pytest.fixture
def mock_user_settings_store() -> MagicMock:
    """Mock UserSettingsStore with known timezones."""
    store = MagicMock()
    # Configure store to return specific timezones for test users
    store.get_user_timezone.side_effect = lambda user_id: {
        'user1': ZoneInfo('America/New_York'),  # EST/EDT
        'user2': ZoneInfo('Europe/London'),  # GMT/BST
        'user3': ZoneInfo('Asia/Tokyo'),  # JST
    }.get(user_id, ZoneInfo('UTC'))  # Default to UTC for unknown users
    return store


@pytest.fixture
def mock_job_table() -> MagicMock:
    """Mock JobTable for job creation."""
    table = MagicMock()
    table.put_job.return_value = None
    return table


@pytest.fixture
def mock_deduplication_index() -> MagicMock:
    """Mock JobDeduplicationIndex for deduplication checks."""
    index = MagicMock()
    index.try_reserve.return_value = True  # By default, allow job scheduling
    return index


def test_fixtures_are_properly_configured(
    mock_user_settings_store: MagicMock, mock_job_table: MagicMock, mock_deduplication_index: MagicMock
) -> None:
    """Test that our fixtures are properly configured."""
    # Test user settings store
    assert mock_user_settings_store.get_user_timezone('user1') == ZoneInfo('America/New_York')
    assert mock_user_settings_store.get_user_timezone('user2') == ZoneInfo('Europe/London')
    assert mock_user_settings_store.get_user_timezone('unknown') == ZoneInfo('UTC')

    # Test job table
    mock_job_table.put_job('test')
    mock_job_table.put_job.assert_called_once_with('test')

    # Test deduplication index
    assert mock_deduplication_index.try_reserve('test') is True
