"""Tests for daily summary scheduling functionality."""

from datetime import UTC, datetime
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


def test_get_next_7am_utc_same_day() -> None:
    """Test computing next 7am when it's still early in the day."""
    from companion_memory.daily_summary_scheduler import get_next_7am_utc

    # 3:00 AM EST on 2025-01-15 should return 7:00 AM EST same day
    now_utc = datetime(2025, 1, 15, 8, 0, tzinfo=UTC)  # 3:00 AM EST
    user_tz = ZoneInfo('America/New_York')

    result = get_next_7am_utc(user_tz, now_utc)

    # Should be 7:00 AM EST = 12:00 UTC
    expected = datetime(2025, 1, 15, 12, 0, tzinfo=UTC)
    assert result == expected


def test_get_next_7am_utc_next_day() -> None:
    """Test computing next 7am when it's past 7am today."""
    from companion_memory.daily_summary_scheduler import get_next_7am_utc

    # 10:00 AM EST on 2025-01-15 should return 7:00 AM EST next day
    now_utc = datetime(2025, 1, 15, 15, 0, tzinfo=UTC)  # 10:00 AM EST
    user_tz = ZoneInfo('America/New_York')

    result = get_next_7am_utc(user_tz, now_utc)

    # Should be 7:00 AM EST next day = 12:00 UTC next day
    expected = datetime(2025, 1, 16, 12, 0, tzinfo=UTC)
    assert result == expected


def test_get_next_7am_utc_different_timezone() -> None:
    """Test computing next 7am in different timezone."""
    from companion_memory.daily_summary_scheduler import get_next_7am_utc

    # 1:00 AM JST on 2025-01-15 should return 7:00 AM JST same day
    now_utc = datetime(2025, 1, 14, 16, 0, tzinfo=UTC)  # 1:00 AM JST
    user_tz = ZoneInfo('Asia/Tokyo')

    result = get_next_7am_utc(user_tz, now_utc)

    # Should be 7:00 AM JST = 22:00 UTC previous day
    expected = datetime(2025, 1, 14, 22, 0, tzinfo=UTC)
    assert result == expected


def test_make_daily_summary_job_id() -> None:
    """Test generating daily summary job ID from user and local date."""
    from companion_memory.daily_summary_scheduler import make_daily_summary_job_id

    user_id = 'U12345'
    user_tz = ZoneInfo('America/New_York')

    # 7:00 AM EST on 2025-01-15 (which is 12:00 UTC)
    local_7am_utc = datetime(2025, 1, 15, 12, 0, tzinfo=UTC)

    result = make_daily_summary_job_id(user_id, user_tz, local_7am_utc)

    # Should extract the local date (2025-01-15) from the UTC time
    expected = 'daily_summary#U12345#2025-01-15'
    assert result == expected


def test_make_daily_summary_job_id_timezone_crossing() -> None:
    """Test job ID generation when UTC and local dates differ."""
    from companion_memory.daily_summary_scheduler import make_daily_summary_job_id

    user_id = 'U67890'
    user_tz = ZoneInfo('Asia/Tokyo')

    # 7:00 AM JST on 2025-01-15 is 22:00 UTC on 2025-01-14
    local_7am_utc = datetime(2025, 1, 14, 22, 0, tzinfo=UTC)

    result = make_daily_summary_job_id(user_id, user_tz, local_7am_utc)

    # Should use the local date (2025-01-15) not the UTC date (2025-01-14)
    expected = 'daily_summary#U67890#2025-01-15'
    assert result == expected
