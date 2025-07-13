"""Tests for work sampling scheduler."""

from datetime import UTC, datetime, time
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from companion_memory.work_sampling_scheduler import schedule_work_sampling_jobs


@pytest.fixture
def mock_user_settings_store() -> MagicMock:
    """Mock user settings store fixture."""
    store = MagicMock()
    store.get_user_settings.side_effect = lambda user_id: {
        'user1': {'timezone': 'America/New_York'},
        'user2': {'timezone': 'Europe/London'},
        'user3': {'timezone': 'Asia/Tokyo'},
        'user4': {},  # No timezone set
    }.get(user_id, {})
    return store


@pytest.fixture
def mock_job_table() -> MagicMock:
    """Mock job table fixture."""
    return MagicMock()


@pytest.fixture
def mock_deduplication_index() -> MagicMock:
    """Mock deduplication index fixture."""
    index = MagicMock()
    index.try_reserve.return_value = True  # Allow scheduling by default
    return index


def test_schedule_work_sampling_jobs_single_user(
    mock_user_settings_store: MagicMock,
    mock_job_table: MagicMock,
    mock_deduplication_index: MagicMock,
) -> None:
    """Test scheduling work sampling jobs for a single user."""
    # Mock getting all users to return one user
    with (
        patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_user_settings_store),
        patch('companion_memory.job_table.JobTable', return_value=mock_job_table),
        patch('companion_memory.deduplication.DeduplicationIndex', return_value=mock_deduplication_index),
    ):
        # Mock getting users from user settings store (we need to implement this)
        mock_user_settings_store.get_all_users = MagicMock(return_value=['user1'])

        # Fixed time for testing: midnight UTC on July 12, 2025
        test_time = datetime(2025, 7, 12, 0, 0, 0, tzinfo=UTC)

        schedule_work_sampling_jobs(now_utc=test_time)

        # Should schedule 5 jobs for the user (WORK_SAMPLING_PROMPTS_PER_DAY)
        assert mock_job_table.put_job.call_count == 5

        # Check that all jobs are work sampling type
        for call in mock_job_table.put_job.call_args_list:
            job = call[0][0]  # First positional argument
            assert job.job_type == 'work_sampling_prompt'
            assert job.payload['user_id'] == 'user1'
            assert 'slot_index' in job.payload


def test_schedule_work_sampling_jobs_multiple_users(
    mock_user_settings_store: MagicMock,
    mock_job_table: MagicMock,
    mock_deduplication_index: MagicMock,
) -> None:
    """Test scheduling work sampling jobs for multiple users."""
    with (
        patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_user_settings_store),
        patch('companion_memory.job_table.JobTable', return_value=mock_job_table),
        patch('companion_memory.deduplication.DeduplicationIndex', return_value=mock_deduplication_index),
    ):
        # Mock getting all users
        mock_user_settings_store.get_all_users = MagicMock(return_value=['user1', 'user2', 'user3'])

        test_time = datetime(2025, 7, 12, 0, 0, 0, tzinfo=UTC)

        schedule_work_sampling_jobs(now_utc=test_time)

        # Should schedule 5 jobs per user = 15 total jobs
        assert mock_job_table.put_job.call_count == 15


def test_schedule_work_sampling_jobs_timezone_handling(
    mock_user_settings_store: MagicMock,
    mock_job_table: MagicMock,
    mock_deduplication_index: MagicMock,
) -> None:
    """Test that jobs are scheduled correctly for different timezones."""
    with (
        patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_user_settings_store),
        patch('companion_memory.job_table.JobTable', return_value=mock_job_table),
        patch('companion_memory.deduplication.DeduplicationIndex', return_value=mock_deduplication_index),
    ):
        mock_user_settings_store.get_all_users = MagicMock(return_value=['user1', 'user2'])

        test_time = datetime(2025, 7, 12, 0, 0, 0, tzinfo=UTC)

        schedule_work_sampling_jobs(now_utc=test_time)

        # Verify jobs are scheduled at appropriate UTC times for each timezone
        job_calls = mock_job_table.put_job.call_args_list

        # Should have jobs for both users
        user1_jobs = [call[0][0] for call in job_calls if call[0][0].payload['user_id'] == 'user1']
        user2_jobs = [call[0][0] for call in job_calls if call[0][0].payload['user_id'] == 'user2']

        assert len(user1_jobs) == 5  # WORK_SAMPLING_PROMPTS_PER_DAY
        assert len(user2_jobs) == 5

        # All jobs should be scheduled during the 8-17 workday in the user's local timezone
        ny_tz = ZoneInfo('America/New_York')
        london_tz = ZoneInfo('Europe/London')

        for job in user1_jobs:
            local_time = job.scheduled_for.astimezone(ny_tz).time()
            assert time(8, 0) <= local_time <= time(17, 0)

        for job in user2_jobs:
            local_time = job.scheduled_for.astimezone(london_tz).time()
            assert time(8, 0) <= local_time <= time(17, 0)


def test_schedule_work_sampling_jobs_deduplication(
    mock_user_settings_store: MagicMock,
    mock_job_table: MagicMock,
    mock_deduplication_index: MagicMock,
) -> None:
    """Test that deduplication prevents duplicate job scheduling."""
    with (
        patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_user_settings_store),
        patch('companion_memory.job_table.JobTable', return_value=mock_job_table),
        patch('companion_memory.deduplication.DeduplicationIndex', return_value=mock_deduplication_index),
    ):
        mock_user_settings_store.get_all_users = MagicMock(return_value=['user1'])

        # Make deduplication prevent some jobs
        mock_deduplication_index.try_reserve.side_effect = [True, False, True, False, True]

        test_time = datetime(2025, 7, 12, 0, 0, 0, tzinfo=UTC)

        schedule_work_sampling_jobs(now_utc=test_time)

        # Should only schedule jobs where deduplication succeeded
        assert mock_job_table.put_job.call_count == 3


def test_schedule_work_sampling_jobs_deterministic_seeding(
    mock_user_settings_store: MagicMock,
    mock_job_table: MagicMock,
    mock_deduplication_index: MagicMock,
) -> None:
    """Test that random scheduling is deterministic with proper seeding."""
    with (
        patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_user_settings_store),
        patch('companion_memory.job_table.JobTable', return_value=mock_job_table),
        patch('companion_memory.deduplication.DeduplicationIndex', return_value=mock_deduplication_index),
    ):
        mock_user_settings_store.get_all_users = MagicMock(return_value=['user1'])

        test_time = datetime(2025, 7, 12, 0, 0, 0, tzinfo=UTC)

        # Schedule jobs twice with same parameters
        schedule_work_sampling_jobs(now_utc=test_time)
        first_run_jobs = [call[0][0] for call in mock_job_table.put_job.call_args_list]

        # Reset and run again
        mock_job_table.reset_mock()
        schedule_work_sampling_jobs(now_utc=test_time)
        second_run_jobs = [call[0][0] for call in mock_job_table.put_job.call_args_list]

        # Jobs should be scheduled at identical times (deterministic)
        assert len(first_run_jobs) == len(second_run_jobs)
        for job1, job2 in zip(first_run_jobs, second_run_jobs, strict=False):
            assert job1.scheduled_for == job2.scheduled_for
            assert job1.payload == job2.payload


def test_schedule_work_sampling_jobs_logical_job_ids(
    mock_user_settings_store: MagicMock,
    mock_job_table: MagicMock,
    mock_deduplication_index: MagicMock,
) -> None:
    """Test that logical job IDs are correctly formatted for deduplication."""
    with (
        patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_user_settings_store),
        patch('companion_memory.job_table.JobTable', return_value=mock_job_table),
        patch('companion_memory.deduplication.DeduplicationIndex', return_value=mock_deduplication_index),
    ):
        mock_user_settings_store.get_all_users = MagicMock(return_value=['user1'])

        test_time = datetime(2025, 7, 12, 0, 0, 0, tzinfo=UTC)

        schedule_work_sampling_jobs(now_utc=test_time)

        # Check that try_reserve was called with correct logical IDs
        dedup_calls = mock_deduplication_index.try_reserve.call_args_list
        assert len(dedup_calls) == 5  # One per slot

        for i, call in enumerate(dedup_calls):
            logical_id = call[0][0]  # First argument to try_reserve
            expected_id = f'work_sampling_prompt:user1:2025-07-12:{i}'
            assert logical_id == expected_id


def test_schedule_work_sampling_jobs_utc_default_timezone(
    mock_user_settings_store: MagicMock,
    mock_job_table: MagicMock,
    mock_deduplication_index: MagicMock,
) -> None:
    """Test that users without timezone setting default to UTC."""
    with (
        patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_user_settings_store),
        patch('companion_memory.job_table.JobTable', return_value=mock_job_table),
        patch('companion_memory.deduplication.DeduplicationIndex', return_value=mock_deduplication_index),
    ):
        mock_user_settings_store.get_all_users = MagicMock(return_value=['user4'])  # No timezone

        test_time = datetime(2025, 7, 12, 0, 0, 0, tzinfo=UTC)

        schedule_work_sampling_jobs(now_utc=test_time)

        # Should still schedule 5 jobs
        assert mock_job_table.put_job.call_count == 5

        # Jobs should be scheduled during 8-17 UTC
        for call in mock_job_table.put_job.call_args_list:
            job = call[0][0]
            utc_time = job.scheduled_for.time()
            assert time(8, 0) <= utc_time <= time(17, 0)
