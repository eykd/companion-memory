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


def test_scheduler_registers_heartbeat_cron_job_when_enabled() -> None:
    """Test that scheduler registers heartbeat cron job when ENABLE_HEARTBEAT=1."""
    from unittest.mock import MagicMock

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
