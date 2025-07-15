"""Tests for heartbeat functionality."""

import os
from unittest.mock import MagicMock, patch


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


def test_scheduler_registers_heartbeat_cron_job_when_enabled() -> None:
    """Test that scheduler registers heartbeat cron job when ENABLE_HEARTBEAT=1."""
    from companion_memory.scheduler import DistributedScheduler

    with (
        patch.dict(os.environ, {'ENABLE_HEARTBEAT': '1'}),
        patch('boto3.resource'),
        patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class,
    ):
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')
        scheduler.scheduler = mock_scheduler
        scheduler.lock.lock_acquired = True  # Simulate having the lock

        # Manually call _add_active_jobs to trigger job registration
        scheduler._add_active_jobs()  # noqa: SLF001

        # Should add heartbeat cron job
        heartbeat_calls = [
            call
            for call in mock_scheduler.add_job.call_args_list
            if len(call[0]) > 0 and 'schedule_heartbeat_job' in str(call[0][0])
        ]
        assert len(heartbeat_calls) == 1

        # Verify it's a cron job that runs every minute
        call_args = heartbeat_calls[0]
        # APScheduler.add_job(func, trigger, **trigger_args)
        assert call_args[0][1] == 'cron'  # Second positional arg should be 'cron'
        assert 'minute' in call_args[1]  # Should have minute in kwargs


def test_run_heartbeat_timed_job_generates_uuid_and_logs() -> None:
    """Test that run_heartbeat_timed_job generates UUIDv1 and logs correctly."""
    from unittest.mock import patch

    from companion_memory.heartbeat import run_heartbeat_timed_job

    with (
        patch('companion_memory.heartbeat.uuid.uuid1') as mock_uuid1,
        patch('companion_memory.heartbeat.schedule_event_heartbeat_job') as mock_schedule_event,
        patch('companion_memory.heartbeat.logger') as mock_logger,
    ):
        # Mock UUID generation
        test_uuid = '01D3B4F8-1F35-11EF-AC22-7B4E4C2AD94E'
        mock_uuid1.return_value = test_uuid

        # Call the function
        run_heartbeat_timed_job()

        # Verify UUID generation
        mock_uuid1.assert_called_once()

        # Verify logging
        mock_logger.info.assert_called_once_with('Heartbeat (timed): UUID=%s', test_uuid)

        # Verify event job scheduling
        mock_schedule_event.assert_called_once_with(test_uuid)


def test_run_heartbeat_event_job_logs_with_uuid() -> None:
    """Test that run_heartbeat_event_job logs correctly with provided UUID."""
    from unittest.mock import patch

    from companion_memory.heartbeat import run_heartbeat_event_job

    test_uuid = '01D3B4F8-1F35-11EF-AC22-7B4E4C2AD94E'

    with patch('companion_memory.heartbeat.logger') as mock_logger:
        # Call the function
        run_heartbeat_event_job(test_uuid)

        # Verify logging
        mock_logger.info.assert_called_once_with('Heartbeat (event): UUID=%s', test_uuid)
