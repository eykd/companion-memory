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
    store.get_user_settings.side_effect = lambda user_id: {
        'user1': {'timezone': 'America/New_York'},  # EST/EDT
        'user2': {'timezone': 'Europe/London'},  # GMT/BST
        'user3': {'timezone': 'Asia/Tokyo'},  # JST
    }.get(user_id, {})  # Default to empty dict for unknown users
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
    assert mock_user_settings_store.get_user_settings('user1') == {'timezone': 'America/New_York'}
    assert mock_user_settings_store.get_user_settings('user2') == {'timezone': 'Europe/London'}
    assert mock_user_settings_store.get_user_settings('unknown') == {}

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


def test_schedule_daily_summaries(
    mock_user_settings_store: MagicMock, mock_job_table: MagicMock, mock_deduplication_index: MagicMock
) -> None:
    """Test integration of schedule_daily_summaries function."""
    from unittest.mock import patch

    from companion_memory.daily_summary_scheduler import schedule_daily_summaries

    # Mock environment variable with test users
    with patch.dict('os.environ', {'DAILY_SUMMARY_USERS': 'user1,user2,user3'}):
        # Mock a specific "now" time for consistent testing
        now_utc = datetime(2025, 1, 15, 0, 0, tzinfo=UTC)  # 00:00 UTC

        schedule_daily_summaries(
            user_settings_store=mock_user_settings_store,
            job_table=mock_job_table,
            deduplication_index=mock_deduplication_index,
            now_utc=now_utc,
        )

    # Verify that user settings were fetched for each user
    mock_user_settings_store.get_user_settings.assert_any_call('user1')
    mock_user_settings_store.get_user_settings.assert_any_call('user2')
    mock_user_settings_store.get_user_settings.assert_any_call('user3')
    assert mock_user_settings_store.get_user_settings.call_count == 3

    # Verify deduplication was attempted for each user
    assert mock_deduplication_index.try_reserve.call_count == 3

    # Verify jobs were created for each user (since try_reserve returns True)
    assert mock_job_table.put_job.call_count == 3

    # Check that the job payloads are correct
    job_calls = mock_job_table.put_job.call_args_list
    job_payloads = [call[0][0].payload for call in job_calls]

    assert {'user_id': 'user1'} in job_payloads
    assert {'user_id': 'user2'} in job_payloads
    assert {'user_id': 'user3'} in job_payloads


def test_schedule_daily_summaries_deduplication_prevents_duplicate(
    mock_user_settings_store: MagicMock, mock_job_table: MagicMock, mock_deduplication_index: MagicMock
) -> None:
    """Test that deduplication prevents duplicate job scheduling."""
    from unittest.mock import patch

    from companion_memory.daily_summary_scheduler import schedule_daily_summaries

    # Configure deduplication to fail for second user (job already exists)
    mock_deduplication_index.try_reserve.side_effect = [True, False, True]  # user1: yes, user2: no, user3: yes

    with patch.dict('os.environ', {'DAILY_SUMMARY_USERS': 'user1,user2,user3'}):
        now_utc = datetime(2025, 1, 15, 0, 0, tzinfo=UTC)

        schedule_daily_summaries(
            user_settings_store=mock_user_settings_store,
            job_table=mock_job_table,
            deduplication_index=mock_deduplication_index,
            now_utc=now_utc,
        )

    # Should only create 2 jobs (user1 and user3), skipping user2
    assert mock_job_table.put_job.call_count == 2

    job_calls = mock_job_table.put_job.call_args_list
    job_payloads = [call[0][0].payload for call in job_calls]

    assert {'user_id': 'user1'} in job_payloads
    assert {'user_id': 'user2'} not in job_payloads
    assert {'user_id': 'user3'} in job_payloads


def test_scheduler_registers_daily_summary_job() -> None:
    """Test that the scheduler registers the daily summary scheduling job."""
    from unittest.mock import MagicMock, patch

    with patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        # Mock the scheduler lock acquisition
        with patch('companion_memory.scheduler.SchedulerLock') as mock_lock_class:
            mock_lock = MagicMock()
            mock_lock.acquire.return_value = True
            mock_lock.lock_acquired = True
            mock_lock_class.return_value = mock_lock

            from companion_memory.scheduler import DistributedScheduler

            scheduler = DistributedScheduler()
            scheduler.start()

            # Check that the scheduler added the daily summary scheduling job
            # It should be one of the calls to add_job
            job_calls = mock_scheduler.add_job.call_args_list

            # Look for a call that includes schedule_daily_summaries function
            daily_summary_job_found = False
            for call in job_calls:
                args, kwargs = call
                if len(args) > 0 and hasattr(args[0], '__name__') and 'schedule_daily_summaries' in args[0].__name__:
                    daily_summary_job_found = True
                    # Check it has the right cron schedule (daily at midnight UTC)
                    assert 'cron' in args or kwargs.get('trigger') == 'cron'
                    assert kwargs.get('hour') == 0 or (len(args) > 2 and 'hour' in str(args[2]))
                    break

            assert daily_summary_job_found, 'Daily summary scheduling job not found in scheduler jobs'


def test_daily_summary_handler() -> None:
    """Test that the daily summary job handler works correctly."""
    from unittest.mock import patch

    from companion_memory.daily_summary_scheduler import DailySummaryHandler, DailySummaryPayload

    # Mock the timezone function and logging
    with (
        patch('companion_memory.summarizer._get_user_timezone') as mock_get_tz,
        patch('logging.getLogger') as mock_get_logger,
    ):
        from zoneinfo import ZoneInfo

        mock_get_tz.return_value = ZoneInfo('America/New_York')
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Create the handler instance
        handler = DailySummaryHandler()

        # Test the handler with a valid payload
        payload = DailySummaryPayload(user_id='user123')

        handler.handle(payload)

        # Verify timezone was fetched and logging occurred
        mock_get_tz.assert_called_once_with('user123')
        mock_logger.info.assert_called_once()

        # Check that the log message format is correct
        log_call_args = mock_logger.info.call_args[0]
        assert log_call_args[0] == 'Would send daily summary to user %s for %s'
        assert log_call_args[1] == 'user123'


def test_daily_summary_handler_type_error() -> None:
    """Test that the handler raises TypeError for invalid payload type."""
    from pydantic import BaseModel

    from companion_memory.daily_summary_scheduler import DailySummaryHandler

    class WrongPayload(BaseModel):
        wrong_field: str

    handler = DailySummaryHandler()
    wrong_payload = WrongPayload(wrong_field='test')

    with pytest.raises(TypeError, match='Expected DailySummaryPayload'):
        handler.handle(wrong_payload)
