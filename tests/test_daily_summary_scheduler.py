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
                    # Check it has the right interval schedule (hourly)
                    assert 'interval' in args or kwargs.get('trigger') == 'interval'
                    assert kwargs.get('hours') == 1 or (len(args) > 2 and 'hours' in str(args[2]))
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


def test_end_to_end_daily_summary_workflow(
    mock_user_settings_store: MagicMock, mock_job_table: MagicMock, mock_deduplication_index: MagicMock
) -> None:
    """Test the complete daily summary workflow from scheduling to execution."""
    from datetime import UTC, datetime
    from unittest.mock import patch

    from companion_memory.daily_summary_scheduler import (
        DailySummaryHandler,
        schedule_daily_summaries,
    )

    # Mock timezone function and logging for handler test
    with (
        patch('companion_memory.summarizer._get_user_timezone') as mock_get_tz,
        patch('logging.getLogger') as mock_get_logger,
        patch.dict('os.environ', {'DAILY_SUMMARY_USERS': 'user1,user2'}),
    ):
        from zoneinfo import ZoneInfo

        mock_get_tz.return_value = ZoneInfo('America/New_York')
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Step 1: Schedule daily summaries (this would run at midnight UTC)
        now_utc = datetime(2025, 1, 15, 0, 0, tzinfo=UTC)  # Midnight UTC
        schedule_daily_summaries(
            user_settings_store=mock_user_settings_store,
            job_table=mock_job_table,
            deduplication_index=mock_deduplication_index,
            now_utc=now_utc,
        )

        # Verify jobs were scheduled
        assert mock_job_table.put_job.call_count == 2  # Two users
        scheduled_jobs = [call[0][0] for call in mock_job_table.put_job.call_args_list]

        # Check job types and payloads
        for job in scheduled_jobs:
            assert job.job_type == 'daily_summary'
            assert job.payload['user_id'] in ['user1', 'user2']
            assert job.status == 'pending'

        # Step 2: Process one of the jobs (this would happen when job worker runs)
        test_job = scheduled_jobs[0]  # Take the first job
        handler = DailySummaryHandler()

        # Create payload from job
        from companion_memory.daily_summary_scheduler import DailySummaryPayload

        payload = DailySummaryPayload(**test_job.payload)

        # Execute the handler
        handler.handle(payload)

        # Verify the handler executed properly
        mock_get_tz.assert_called_with(payload.user_id)
        mock_logger.info.assert_called_once()

        # Check that logging happened with correct message
        log_call_args = mock_logger.info.call_args[0]
        assert log_call_args[0] == 'Would send daily summary to user %s for %s'
        assert log_call_args[1] == payload.user_id


def test_schedule_daily_summaries_uses_current_time_when_now_utc_is_none(
    mock_user_settings_store: MagicMock, mock_job_table: MagicMock, mock_deduplication_index: MagicMock
) -> None:
    """Test that schedule_daily_summaries uses current time when now_utc is None."""
    from unittest.mock import patch

    from companion_memory.daily_summary_scheduler import schedule_daily_summaries

    with patch.dict('os.environ', {'DAILY_SUMMARY_USERS': 'user1'}):
        # Just verify it doesn't crash when now_utc is None
        # This will exercise the datetime.now(UTC) path
        schedule_daily_summaries(
            user_settings_store=mock_user_settings_store,
            job_table=mock_job_table,
            deduplication_index=mock_deduplication_index,
            now_utc=None,  # This should trigger the datetime.now(UTC) call
        )

        # Should have called the store methods
        mock_user_settings_store.get_user_settings.assert_called_once_with('user1')
        mock_deduplication_index.try_reserve.assert_called_once()
        mock_job_table.put_job.assert_called_once()


def test_schedule_daily_summaries_returns_early_when_no_users_configured(
    mock_user_settings_store: MagicMock, mock_job_table: MagicMock, mock_deduplication_index: MagicMock
) -> None:
    """Test that schedule_daily_summaries returns early when DAILY_SUMMARY_USERS is empty."""
    from unittest.mock import patch

    from companion_memory.daily_summary_scheduler import schedule_daily_summaries

    # Test with empty environment variable
    with patch.dict('os.environ', {'DAILY_SUMMARY_USERS': ''}):
        schedule_daily_summaries(
            user_settings_store=mock_user_settings_store,
            job_table=mock_job_table,
            deduplication_index=mock_deduplication_index,
            now_utc=datetime(2025, 1, 15, 0, 0, tzinfo=UTC),
        )

        # Should not call any store methods
        mock_user_settings_store.get_user_settings.assert_not_called()
        mock_deduplication_index.try_reserve.assert_not_called()
        mock_job_table.put_job.assert_not_called()

    # Test with missing environment variable
    with patch.dict('os.environ', {}, clear=True):
        schedule_daily_summaries(
            user_settings_store=mock_user_settings_store,
            job_table=mock_job_table,
            deduplication_index=mock_deduplication_index,
            now_utc=datetime(2025, 1, 15, 0, 0, tzinfo=UTC),
        )

        # Should not call any store methods
        mock_user_settings_store.get_user_settings.assert_not_called()
        mock_deduplication_index.try_reserve.assert_not_called()
        mock_job_table.put_job.assert_not_called()


def test_schedule_daily_summaries_handles_invalid_timezone(
    mock_user_settings_store: MagicMock, mock_job_table: MagicMock, mock_deduplication_index: MagicMock
) -> None:
    """Test that schedule_daily_summaries handles invalid timezone gracefully."""
    from unittest.mock import patch
    from zoneinfo import ZoneInfo

    from companion_memory.daily_summary_scheduler import schedule_daily_summaries

    # Configure store to return invalid timezone that will raise ZoneInfo exception
    mock_user_settings_store.get_user_settings.return_value = {'timezone': 'Not/A/Real/Timezone'}

    with (
        patch.dict('os.environ', {'DAILY_SUMMARY_USERS': 'user1'}),
        patch('companion_memory.daily_summary_scheduler.ZoneInfo') as mock_zoneinfo,
    ):
        # Mock ZoneInfo to raise exception for invalid timezone but work for UTC
        def zoneinfo_side_effect(tz_name: str) -> ZoneInfo:
            if tz_name == 'Not/A/Real/Timezone':
                raise ValueError('Invalid timezone')
            return ZoneInfo(tz_name)

        mock_zoneinfo.side_effect = zoneinfo_side_effect

        schedule_daily_summaries(
            user_settings_store=mock_user_settings_store,
            job_table=mock_job_table,
            deduplication_index=mock_deduplication_index,
            now_utc=datetime(2025, 1, 15, 0, 0, tzinfo=UTC),
        )

        # Should still process the job but with UTC timezone as fallback
        mock_deduplication_index.try_reserve.assert_called_once()
        mock_job_table.put_job.assert_called_once()

        # Check that the job was created (with UTC as fallback timezone)
        job_call = mock_job_table.put_job.call_args[0][0]
        assert job_call.payload == {'user_id': 'user1'}


def test_schedule_daily_summaries_handles_missing_timezone(
    mock_user_settings_store: MagicMock, mock_job_table: MagicMock, mock_deduplication_index: MagicMock
) -> None:
    """Test that schedule_daily_summaries handles missing timezone gracefully."""
    from unittest.mock import patch

    from companion_memory.daily_summary_scheduler import schedule_daily_summaries

    # Configure store to return settings without timezone
    mock_user_settings_store.get_user_settings.return_value = {}

    with patch.dict('os.environ', {'DAILY_SUMMARY_USERS': 'user1'}):
        schedule_daily_summaries(
            user_settings_store=mock_user_settings_store,
            job_table=mock_job_table,
            deduplication_index=mock_deduplication_index,
            now_utc=datetime(2025, 1, 15, 0, 0, tzinfo=UTC),
        )

        # Should still process the job but with UTC timezone as fallback
        mock_deduplication_index.try_reserve.assert_called_once()
        mock_job_table.put_job.assert_called_once()

        # Check that the job was created (with UTC as fallback timezone)
        job_call = mock_job_table.put_job.call_args[0][0]
        assert job_call.payload == {'user_id': 'user1'}


def test_daily_summary_handler_payload_model() -> None:
    """Test that DailySummaryHandler.payload_model returns correct type."""
    from companion_memory.daily_summary_scheduler import DailySummaryHandler, DailySummaryPayload

    result = DailySummaryHandler.payload_model()
    assert result is DailySummaryPayload


def test_daily_summary_handler_exception_handling() -> None:
    """Test that DailySummaryHandler handles exceptions gracefully."""
    from unittest.mock import patch

    from companion_memory.daily_summary_scheduler import DailySummaryHandler, DailySummaryPayload

    # Mock the _get_user_timezone function to raise an exception
    with (
        patch('companion_memory.summarizer._get_user_timezone', side_effect=Exception('Test error')),
        patch('logging.getLogger') as mock_get_logger,
    ):
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        handler = DailySummaryHandler()
        payload = DailySummaryPayload(user_id='user123')

        # Should not raise exception
        handler.handle(payload)

        # Should log the exception
        mock_logger.exception.assert_called_once_with('Error processing daily summary for user %s', 'user123')


def test_legacy_daily_summary_checker_is_disabled() -> None:
    """Test that the legacy daily summary checker is disabled."""
    from unittest.mock import patch

    # Verify that the scheduler does not register the old daily_summary_checker job
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

            # Check that no daily_summary_checker job is registered
            job_calls = mock_scheduler.add_job.call_args_list

            daily_summary_checker_found = False
            for call in job_calls:
                _args, kwargs = call
                job_id = kwargs.get('id', '')
                if job_id == 'daily_summary_checker':
                    daily_summary_checker_found = True
                    break

            assert not daily_summary_checker_found, 'Legacy daily_summary_checker job should not be registered'
