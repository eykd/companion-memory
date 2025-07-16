"""Tests for distributed scheduler."""

from unittest.mock import MagicMock, patch

import pytest

from companion_memory.scheduler import (
    DistributedScheduler,
    SchedulerLock,
    get_scheduler,
    get_slack_client,
)

pytestmark = pytest.mark.block_network


def test_scheduler_lock_key_format() -> None:
    """Test that scheduler lock uses correct table key format."""
    with patch('boto3.resource'):
        lock = SchedulerLock('TestTable')

        assert lock.partition_key == 'system#scheduler'
        assert lock.sort_key == 'lock#main'
        assert lock.table_name == 'TestTable'


def test_scheduler_lock_acquire_with_mocked_dynamodb() -> None:
    """Test scheduler lock acquisition with mocked DynamoDB."""
    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')

        # Mock successful lock acquisition
        mock_table.put_item.return_value = None

        result = lock.acquire()

        assert result is True
        assert lock.lock_acquired is True

        # Verify put_item was called with correct structure
        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args

        item = call_args[1]['Item']
        assert item['PK'] == 'system#scheduler'
        assert item['SK'] == 'lock#main'
        assert 'process_id' in item
        assert 'timestamp' in item
        assert 'ttl' in item
        assert 'instance_info' in item
        assert item['lock_type'] == 'scheduler'


def test_scheduler_lock_acquire_failure_with_mocked_dynamodb() -> None:
    """Test scheduler lock acquisition failure (lock already held)."""
    from botocore.exceptions import ClientError

    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')

        # Mock conditional check failure (lock already exists)
        mock_table.put_item.side_effect = ClientError({'Error': {'Code': 'ConditionalCheckFailedException'}}, 'PutItem')

        result = lock.acquire()

        assert result is False
        assert lock.lock_acquired is False


def test_scheduler_lock_acquire_other_client_error() -> None:
    """Test scheduler lock acquisition with other ClientError."""
    from botocore.exceptions import ClientError

    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')

        # Mock other ClientError (not ConditionalCheckFailedException)
        mock_table.put_item.side_effect = ClientError(
            {'Error': {'Code': 'ProvisionedThroughputExceededException'}}, 'PutItem'
        )

        with pytest.raises(ClientError):
            lock.acquire()


def test_scheduler_lock_refresh_success() -> None:
    """Test scheduler lock refresh success."""
    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')
        lock.lock_acquired = True  # Simulate already acquired lock

        # Mock successful refresh
        mock_table.update_item.return_value = None

        result = lock.refresh()

        assert result is True
        mock_table.update_item.assert_called_once()


def test_scheduler_lock_refresh_not_acquired() -> None:
    """Test scheduler lock refresh when lock not acquired."""
    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')
        lock.lock_acquired = False  # Simulate not acquired lock

        result = lock.refresh()

        assert result is False
        mock_table.update_item.assert_not_called()


def test_scheduler_lock_refresh_failure() -> None:
    """Test scheduler lock refresh failure (lock lost)."""
    from botocore.exceptions import ClientError

    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')
        lock.lock_acquired = True  # Simulate already acquired lock

        # Mock conditional check failure (lock lost)
        mock_table.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ConditionalCheckFailedException'}}, 'UpdateItem'
        )

        result = lock.refresh()

        assert result is False
        assert lock.lock_acquired is False


def test_scheduler_lock_refresh_other_client_error() -> None:
    """Test scheduler lock refresh with other ClientError."""
    from botocore.exceptions import ClientError

    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')
        lock.lock_acquired = True  # Simulate already acquired lock

        # Mock other ClientError (not ConditionalCheckFailedException)
        mock_table.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ProvisionedThroughputExceededException'}}, 'UpdateItem'
        )

        with pytest.raises(ClientError):
            lock.refresh()


def test_scheduler_lock_release_success() -> None:
    """Test scheduler lock release success."""
    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')
        lock.lock_acquired = True  # Simulate acquired lock

        # Mock successful release
        mock_table.delete_item.return_value = None

        lock.release()

        assert lock.lock_acquired is False
        mock_table.delete_item.assert_called_once()


def test_scheduler_lock_release_not_acquired() -> None:
    """Test scheduler lock release when lock not acquired."""
    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')
        lock.lock_acquired = False  # Simulate not acquired lock

        lock.release()

        assert lock.lock_acquired is False
        mock_table.delete_item.assert_not_called()


def test_scheduler_lock_release_failure() -> None:
    """Test scheduler lock release failure (lock already taken)."""
    from botocore.exceptions import ClientError

    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')
        lock.lock_acquired = True  # Simulate acquired lock

        # Mock conditional check failure (lock already taken by another process)
        mock_table.delete_item.side_effect = ClientError(
            {'Error': {'Code': 'ConditionalCheckFailedException'}}, 'DeleteItem'
        )

        lock.release()

        assert lock.lock_acquired is False


def test_scheduler_lock_release_other_client_error() -> None:
    """Test scheduler lock release with other ClientError."""
    from botocore.exceptions import ClientError

    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')
        lock.lock_acquired = True  # Simulate acquired lock

        # Mock other ClientError (not ConditionalCheckFailedException)
        mock_table.delete_item.side_effect = ClientError(
            {'Error': {'Code': 'ProvisionedThroughputExceededException'}}, 'DeleteItem'
        )

        lock.release()

        assert lock.lock_acquired is False


def test_scheduler_lock_get_current_lock_holder_success() -> None:
    """Test getting current lock holder successfully."""
    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')
        mock_item = {'PK': 'system#scheduler', 'SK': 'lock#main', 'process_id': 'test-process'}
        mock_table.get_item.return_value = {'Item': mock_item}

        result = lock.get_current_lock_holder()

        assert result == mock_item
        mock_table.get_item.assert_called_once()


def test_scheduler_lock_get_current_lock_holder_no_item() -> None:
    """Test getting current lock holder when no lock exists."""
    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')
        mock_table.get_item.return_value = {}

        result = lock.get_current_lock_holder()

        assert result is None


def test_scheduler_lock_get_current_lock_holder_client_error() -> None:
    """Test getting current lock holder with ClientError."""
    from botocore.exceptions import ClientError

    with patch('boto3.resource') as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        lock = SchedulerLock('TestTable')
        mock_table.get_item.side_effect = ClientError(
            {'Error': {'Code': 'ProvisionedThroughputExceededException'}}, 'GetItem'
        )

        result = lock.get_current_lock_holder()

        assert result is None


def test_scheduler_singleton_pattern() -> None:
    """Test that get_scheduler maintains singleton pattern."""
    from companion_memory import scheduler

    # Clear any existing singleton
    original_instance = scheduler._scheduler_instance  # noqa: SLF001
    scheduler._scheduler_instance = None  # noqa: SLF001

    with patch('boto3.resource'):
        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()

        assert scheduler1 is scheduler2

    # Restore original singleton for other tests
    scheduler._scheduler_instance = original_instance  # noqa: SLF001


def test_distributed_scheduler_status() -> None:
    """Test scheduler status method."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')

        status = scheduler.get_status()

        assert 'scheduler_started' in status
        assert 'lock_acquired' in status
        assert 'process_id' in status
        assert 'current_lock_holder' in status
        assert 'instance_info' in status

        assert status['scheduler_started'] is False
        assert status['lock_acquired'] is False


def test_distributed_scheduler_start_success() -> None:
    """Test scheduler start success with immediate lock acquisition."""
    with patch('boto3.resource'), patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')

        # Mock successful lock acquisition
        mock_acquire = MagicMock(return_value=True)
        with patch.object(scheduler.lock, 'acquire', mock_acquire):
            result = scheduler.start()

        assert result is True
        assert scheduler.started is True
        mock_scheduler.start.assert_called_once()
        assert (
            mock_scheduler.add_job.call_count == 6
        )  # lock_manager + user_timezone_sync + daily_summary_scheduler + work_sampling_scheduler + job_worker_poller + job_cleanup
        mock_acquire.assert_called_once()


def test_distributed_scheduler_start_already_started() -> None:
    """Test scheduler start when already started."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')
        scheduler.started = True

        result = scheduler.start()

        assert result is True


def test_distributed_scheduler_start_without_immediate_lock() -> None:
    """Test scheduler start when lock is not immediately acquired."""
    with patch('boto3.resource'), patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')

        # Mock failed lock acquisition
        mock_acquire = MagicMock(return_value=False)
        with patch.object(scheduler.lock, 'acquire', mock_acquire):
            result = scheduler.start()

        assert result is True  # Scheduler always starts successfully
        assert scheduler.started is True
        mock_scheduler.start.assert_called_once()
        assert mock_scheduler.add_job.call_count == 1  # Only lock_manager job added
        mock_acquire.assert_called_once()


def test_distributed_scheduler_manage_lock_with_lock_held() -> None:
    """Test scheduler manage lock when lock is held."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = True  # Simulate holding the lock
        mock_refresh = MagicMock(return_value=True)
        with patch.object(scheduler.lock, 'refresh', mock_refresh):
            # Access private method for testing
            scheduler._manage_lock()  # noqa: SLF001

            mock_refresh.assert_called_once()


def test_distributed_scheduler_manage_lock_loses_lock() -> None:
    """Test scheduler manage lock when lock is lost during refresh."""
    with patch('boto3.resource'), patch('companion_memory.scheduler.logger') as mock_logger:
        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = True  # Simulate holding the lock
        scheduler._jobs_added = True  # Simulate having active jobs  # noqa: SLF001
        mock_refresh = MagicMock(return_value=False)
        mock_remove_jobs = MagicMock()
        with (
            patch.object(scheduler.lock, 'refresh', mock_refresh),
            patch.object(scheduler, '_remove_active_jobs', mock_remove_jobs),
        ):
            # Access private method for testing
            scheduler._manage_lock()  # noqa: SLF001

            mock_refresh.assert_called_once()
            mock_logger.warning.assert_called_once()
            mock_remove_jobs.assert_called_once()


def test_distributed_scheduler_manage_lock_without_lock() -> None:
    """Test scheduler manage lock when lock is not held."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = False  # Simulate not holding the lock
        mock_acquire = MagicMock(return_value=False)
        with patch.object(scheduler.lock, 'acquire', mock_acquire):
            # Access private method for testing
            scheduler._manage_lock()  # noqa: SLF001

            mock_acquire.assert_called_once()


def test_distributed_scheduler_add_job_when_started() -> None:
    """Test adding job when scheduler is started and has lock."""
    with patch('boto3.resource'), patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')
        scheduler.started = True
        scheduler.scheduler = mock_scheduler
        scheduler.lock.lock_acquired = True  # Must have lock to add jobs

        def test_job() -> None:
            pass

        scheduler.add_job(test_job, 'interval', seconds=30)

        mock_scheduler.add_job.assert_called_once_with(test_job, 'interval', seconds=30)


def test_distributed_scheduler_add_job_when_not_started() -> None:
    """Test adding job when scheduler is not started."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')
        scheduler.started = False

        def test_job() -> None:
            pass

        scheduler.add_job(test_job, 'interval', seconds=30)

        # Should not call scheduler.add_job since not started


def test_distributed_scheduler_add_job_without_lock() -> None:
    """Test adding job when scheduler is started but doesn't have lock."""
    with patch('boto3.resource'), patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')
        scheduler.started = True
        scheduler.scheduler = mock_scheduler
        scheduler.lock.lock_acquired = False  # No lock

        def test_job() -> None:
            pass

        scheduler.add_job(test_job, 'interval', seconds=30)

        # Should not call scheduler.add_job since no lock
        mock_scheduler.add_job.assert_not_called()


def test_distributed_scheduler_add_active_jobs_when_already_added() -> None:
    """Test _add_active_jobs when jobs are already added."""
    with patch('boto3.resource'), patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')
        scheduler.scheduler = mock_scheduler
        scheduler._jobs_added = True  # Jobs already added  # noqa: SLF001

        # Call the method - should return early
        scheduler._add_active_jobs()  # noqa: SLF001

        # Should not add any jobs since already added
        mock_scheduler.add_job.assert_not_called()


def test_distributed_scheduler_add_active_jobs_without_scheduler() -> None:
    """Test _add_active_jobs when scheduler is None."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')
        scheduler.scheduler = None
        scheduler._jobs_added = False  # noqa: SLF001

        # Call the method - should return early
        scheduler._add_active_jobs()  # noqa: SLF001

        # No exception should be raised


def test_distributed_scheduler_remove_active_jobs() -> None:
    """Test _remove_active_jobs method."""
    with patch('boto3.resource'), patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')
        scheduler.scheduler = mock_scheduler
        scheduler._jobs_added = True  # noqa: SLF001

        # Call the method
        scheduler._remove_active_jobs()  # noqa: SLF001

        # Should remove four jobs
        assert mock_scheduler.remove_job.call_count == 4
        mock_scheduler.remove_job.assert_any_call('daily_summary_scheduler')
        mock_scheduler.remove_job.assert_any_call('work_sampling_scheduler')
        mock_scheduler.remove_job.assert_any_call('job_worker_poller')
        mock_scheduler.remove_job.assert_any_call('job_cleanup')
        assert scheduler._jobs_added is False  # noqa: SLF001


def test_distributed_scheduler_remove_active_jobs_with_exception() -> None:
    """Test _remove_active_jobs when job removal raises exception."""
    with patch('boto3.resource'), patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler.remove_job.side_effect = Exception('Job not found')
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')
        scheduler.scheduler = mock_scheduler
        scheduler._jobs_added = True  # noqa: SLF001

        # Call the method - should not raise exception
        scheduler._remove_active_jobs()  # noqa: SLF001

        # Should still mark jobs as removed despite exception
        assert scheduler._jobs_added is False  # noqa: SLF001


def test_distributed_scheduler_configure_dependencies() -> None:
    """Test scheduler dependency configuration."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')
        mock_log_store = MagicMock()
        mock_llm = MagicMock()

        scheduler.configure_dependencies(mock_log_store, mock_llm)

        assert scheduler._log_store is mock_log_store  # noqa: SLF001
        assert scheduler._llm is mock_llm  # noqa: SLF001


def test_distributed_scheduler_shutdown_with_scheduler() -> None:
    """Test scheduler shutdown with active scheduler."""
    with patch('boto3.resource'), patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')
        scheduler.started = True
        scheduler.scheduler = mock_scheduler
        mock_release = MagicMock()
        with patch.object(scheduler.lock, 'release', mock_release):
            scheduler.shutdown()

            mock_scheduler.shutdown.assert_called_once_with(wait=True)
            assert scheduler.started is False
            mock_release.assert_called_once()


def test_distributed_scheduler_shutdown_with_exception() -> None:
    """Test scheduler shutdown with exception during shutdown."""
    from botocore.exceptions import ClientError

    with (
        patch('boto3.resource'),
        patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class,
        patch('companion_memory.scheduler.logger') as mock_logger,
    ):
        mock_scheduler = MagicMock()
        mock_scheduler.shutdown.side_effect = ClientError({'Error': {'Code': 'TestException'}}, 'Shutdown')
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')
        scheduler.started = True
        scheduler.scheduler = mock_scheduler
        mock_release = MagicMock()
        with patch.object(scheduler.lock, 'release', mock_release):
            scheduler.shutdown()

            mock_scheduler.shutdown.assert_called_once_with(wait=True)
            assert scheduler.started is False
            mock_release.assert_called_once()
            mock_logger.exception.assert_called_once()


def test_distributed_scheduler_shutdown_without_scheduler() -> None:
    """Test scheduler shutdown without active scheduler."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')
        scheduler.started = False
        scheduler.scheduler = None
        mock_release = MagicMock()
        with patch.object(scheduler.lock, 'release', mock_release):
            scheduler.shutdown()

            assert scheduler.started is False
            mock_release.assert_called_once()


def test_flask_app_integration() -> None:
    """Test Flask app integrates with distributed scheduler."""
    from companion_memory.app import create_app

    with (
        patch('companion_memory.scheduler.SchedulerLock.acquire') as mock_acquire,
        patch('boto3.resource') as mock_boto3,
        patch('companion_memory.app.get_scheduler') as mock_get_scheduler,
    ):
        mock_acquire.return_value = True
        mock_table = MagicMock()
        mock_boto3.return_value.Table.return_value = mock_table

        # Mock scheduler with a proper status response
        mock_scheduler = MagicMock()
        mock_scheduler.start.return_value = True
        mock_scheduler.get_status.return_value = {
            'scheduler_started': True,
            'lock_acquired': True,
            'process_id': 'test-process',
            'current_lock_holder': None,
            'instance_info': {'test': 'info'},
        }
        mock_get_scheduler.return_value = mock_scheduler

        # Create app - this should start the scheduler
        app = create_app()

        # Verify we can access the status endpoint
        with app.test_client() as client:
            response = client.get('/scheduler/status')
            assert response.status_code == 200
            data = response.get_json()
            assert data['scheduler_started'] is True


def test_get_slack_client_success() -> None:
    """Test getting Slack client with valid token."""
    with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'test-token'}):
        client = get_slack_client()
        assert client is not None


def test_get_slack_client_missing_token() -> None:
    """Test getting Slack client with missing token."""
    with (
        patch.dict('os.environ', {}, clear=True),
        pytest.raises(ValueError, match='SLACK_BOT_TOKEN environment variable is required'),
    ):
        get_slack_client()


def test_distributed_scheduler_poll_and_process_jobs_without_lock() -> None:
    """Test _poll_and_process_jobs when lock is not held."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = False

        # Call the method - should return early
        scheduler._poll_and_process_jobs()  # noqa: SLF001

        # Should not have initialized job worker
        assert scheduler._job_worker is None  # noqa: SLF001


def test_distributed_scheduler_poll_and_process_jobs_with_lock() -> None:
    """Test _poll_and_process_jobs when lock is held."""
    with (
        patch('boto3.resource'),
        patch('companion_memory.job_table.JobTable') as mock_job_table_class,
        patch('companion_memory.job_worker.JobWorker') as mock_job_worker_class,
    ):
        mock_job_table = MagicMock()
        mock_job_table_class.return_value = mock_job_table

        mock_job_worker = MagicMock()
        mock_job_worker.poll_and_process_jobs.return_value = 3  # Processed 3 jobs
        mock_job_worker_class.return_value = mock_job_worker

        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = True

        # Call the method
        scheduler._poll_and_process_jobs()  # noqa: SLF001

        # Should have initialized job worker
        assert scheduler._job_worker is mock_job_worker  # noqa: SLF001
        mock_job_table_class.assert_called_once()
        mock_job_worker_class.assert_called_once_with(mock_job_table)
        mock_job_worker.poll_and_process_jobs.assert_called_once()
        # Verify job worker was properly initialized and used


def test_distributed_scheduler_poll_and_process_jobs_no_jobs_processed() -> None:
    """Test _poll_and_process_jobs when no jobs are processed."""
    with (
        patch('boto3.resource'),
        patch('companion_memory.job_table.JobTable') as mock_job_table_class,
        patch('companion_memory.job_worker.JobWorker') as mock_job_worker_class,
    ):
        mock_job_table = MagicMock()
        mock_job_table_class.return_value = mock_job_table

        mock_job_worker = MagicMock()
        mock_job_worker.poll_and_process_jobs.return_value = 0  # No jobs processed
        mock_job_worker_class.return_value = mock_job_worker

        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = True

        # Call the method
        scheduler._poll_and_process_jobs()  # noqa: SLF001

        # Verify job worker was initialized and called
        mock_job_worker.poll_and_process_jobs.assert_called_once()


def test_distributed_scheduler_poll_and_process_jobs_debug_logging_with_due_jobs() -> None:
    """Test _poll_and_process_jobs debug logging when jobs are found but not processed."""
    from datetime import UTC, datetime
    from uuid import UUID

    from companion_memory.job_models import ScheduledJob

    with (
        patch('boto3.resource'),
        patch('companion_memory.job_table.JobTable') as mock_job_table_class,
        patch('companion_memory.job_worker.JobWorker') as mock_job_worker_class,
    ):
        # Create mock due jobs
        due_job1 = ScheduledJob(
            job_id=UUID('12345678-1234-5678-9abc-123456789abc'),
            job_type='test_job',
            payload={'test': 'data'},
            scheduled_for=datetime.now(UTC),
            status='pending',
            attempts=0,
            created_at=datetime.now(UTC),
        )
        due_job2 = ScheduledJob(
            job_id=UUID('87654321-4321-8765-cba9-987654321abc'),
            job_type='another_job',
            payload={'other': 'data'},
            scheduled_for=datetime.now(UTC),
            status='pending',
            attempts=0,
            created_at=datetime.now(UTC),
        )

        # Mock job table with due jobs
        mock_job_table = MagicMock()
        mock_job_table.get_due_jobs.return_value = [due_job1, due_job2]
        mock_job_table_class.return_value = mock_job_table

        # Mock job worker that processes 0 jobs
        mock_job_worker = MagicMock()
        mock_job_worker.poll_and_process_jobs.return_value = 0  # No jobs processed
        mock_job_worker_class.return_value = mock_job_worker

        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = True

        # Call the method
        scheduler._poll_and_process_jobs()  # noqa: SLF001

        # Verify job worker was called
        mock_job_worker.poll_and_process_jobs.assert_called_once()


def test_distributed_scheduler_poll_and_process_jobs_no_due_jobs_found() -> None:
    """Test _poll_and_process_jobs debug logging when no due jobs are found."""
    with (
        patch('boto3.resource'),
        patch('companion_memory.job_table.JobTable') as mock_job_table_class,
        patch('companion_memory.job_worker.JobWorker') as mock_job_worker_class,
    ):
        # Mock job table with no due jobs
        mock_job_table = MagicMock()
        mock_job_table.get_due_jobs.return_value = []  # No jobs found
        mock_job_table_class.return_value = mock_job_table

        # Mock job worker that processes 0 jobs
        mock_job_worker = MagicMock()
        mock_job_worker.poll_and_process_jobs.return_value = 0  # No jobs processed
        mock_job_worker_class.return_value = mock_job_worker

        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = True

        # Call the method
        scheduler._poll_and_process_jobs()  # noqa: SLF001

        # Verify job worker was called
        mock_job_worker.poll_and_process_jobs.assert_called_once()


def test_distributed_scheduler_poll_and_process_jobs_exception() -> None:
    """Test _poll_and_process_jobs when an exception occurs."""
    with (
        patch('boto3.resource'),
        patch('companion_memory.job_table.JobTable') as mock_job_table_class,
        patch('companion_memory.scheduler.logger') as mock_logger,
    ):
        mock_job_table_class.side_effect = Exception('Job table error')

        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = True

        # Call the method - should not raise exception
        scheduler._poll_and_process_jobs()  # noqa: SLF001

        # Should log the exception
        mock_logger.exception.assert_called_once_with('Error in job worker polling')


def test_distributed_scheduler_job_worker_disabled() -> None:
    """Test scheduler when job worker is disabled."""
    with patch('boto3.resource'), patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')
        scheduler._job_worker_enabled = False  # noqa: SLF001

        # Mock successful lock acquisition
        mock_acquire = MagicMock(return_value=True)
        with patch.object(scheduler.lock, 'acquire', mock_acquire):
            scheduler.start()

        # Should only add 6 jobs (not including job worker poller)
        assert (
            mock_scheduler.add_job.call_count == 5
        )  # lock_manager + user_timezone_sync + daily_summary_scheduler + work_sampling_scheduler + job_cleanup


def test_distributed_scheduler_remove_job_worker_poller() -> None:
    """Test that job worker poller is removed when losing lock."""
    with patch('boto3.resource'), patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')
        scheduler.scheduler = mock_scheduler
        scheduler._jobs_added = True  # noqa: SLF001

        # Call the method
        scheduler._remove_active_jobs()  # noqa: SLF001

        # Should attempt to remove all scheduler jobs
        mock_scheduler.remove_job.assert_any_call('daily_summary_scheduler')
        mock_scheduler.remove_job.assert_any_call('work_sampling_scheduler')
        mock_scheduler.remove_job.assert_any_call('job_worker_poller')


def test_distributed_scheduler_schedule_daily_summaries_without_lock() -> None:
    """Test _schedule_daily_summaries when lock is not held."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = False

        # Call the method - should return early
        scheduler._schedule_daily_summaries()  # noqa: SLF001

        # Should not try to import or create any dependencies


def test_distributed_scheduler_schedule_daily_summaries_success() -> None:
    """Test _schedule_daily_summaries successful execution."""
    with (
        patch('boto3.resource'),
        patch('companion_memory.scheduler.logger') as mock_logger,
        patch('companion_memory.user_settings.DynamoUserSettingsStore') as mock_settings_store_class,
        patch('companion_memory.job_table.JobTable') as mock_job_table_class,
        patch('companion_memory.deduplication.DeduplicationIndex') as mock_dedup_class,
        patch('companion_memory.daily_summary_scheduler.schedule_daily_summaries') as mock_schedule_fn,
    ):
        # Set up mocks
        mock_settings_store = MagicMock()
        mock_job_table = MagicMock()
        mock_dedup_index = MagicMock()

        mock_settings_store_class.return_value = mock_settings_store
        mock_job_table_class.return_value = mock_job_table
        mock_dedup_class.return_value = mock_dedup_index

        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = True

        # Call the method
        scheduler._schedule_daily_summaries()  # noqa: SLF001

        # Should call the schedule function with correct dependencies
        mock_schedule_fn.assert_called_once_with(
            user_settings_store=mock_settings_store,
            job_table=mock_job_table,
            deduplication_index=mock_dedup_index,
        )

        # Should log success
        mock_logger.info.assert_called_once_with('Scheduled daily summary jobs')


def test_distributed_scheduler_schedule_daily_summaries_exception() -> None:
    """Test _schedule_daily_summaries when an exception occurs."""
    with (
        patch('boto3.resource'),
        patch('companion_memory.scheduler.logger') as mock_logger,
    ):
        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = True

        # Mock DynamoUserSettingsStore to raise an exception
        with patch('companion_memory.user_settings.DynamoUserSettingsStore', side_effect=Exception('Import error')):
            # Call the method - should not raise exception
            scheduler._schedule_daily_summaries()  # noqa: SLF001

            # Should log the exception
            mock_logger.exception.assert_called_once_with('Error scheduling daily summaries')


def test_distributed_scheduler_schedule_work_sampling_jobs_without_lock() -> None:
    """Test _schedule_work_sampling_jobs when lock is not held."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = False

        # Call the method - should return early
        scheduler._schedule_work_sampling_jobs()  # noqa: SLF001


def test_distributed_scheduler_schedule_work_sampling_jobs_with_lock() -> None:
    """Test _schedule_work_sampling_jobs when lock is held."""
    with (
        patch('boto3.resource'),
        patch('companion_memory.work_sampling_scheduler.schedule_work_sampling_jobs') as mock_schedule_fn,
        patch('companion_memory.user_settings.DynamoUserSettingsStore') as mock_settings_store,
        patch('companion_memory.job_table.JobTable') as mock_job_table,
        patch('companion_memory.deduplication.DeduplicationIndex') as mock_dedup_index,
    ):
        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = True

        # Call the method
        scheduler._schedule_work_sampling_jobs()  # noqa: SLF001

        # Verify components were created
        mock_settings_store.assert_called_once()
        mock_job_table.assert_called_once()
        mock_dedup_index.assert_called_once()

        # Verify scheduling function was called with proper dependencies
        mock_schedule_fn.assert_called_once_with(
            user_settings_store=mock_settings_store.return_value,
            job_table=mock_job_table.return_value,
            deduplication_index=mock_dedup_index.return_value,
        )

        # Verify scheduling function was called (success logging removed)


def test_distributed_scheduler_schedule_work_sampling_jobs_exception() -> None:
    """Test _schedule_work_sampling_jobs when an exception occurs."""
    with (
        patch('boto3.resource'),
        patch('companion_memory.scheduler.logger') as mock_logger,
    ):
        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = True

        # Mock DynamoUserSettingsStore to raise an exception
        with patch('companion_memory.user_settings.DynamoUserSettingsStore', side_effect=Exception('Import error')):
            # Call the method - should not raise exception
            scheduler._schedule_work_sampling_jobs()  # noqa: SLF001

            # Should log the exception
            mock_logger.exception.assert_called_once_with('Error scheduling work sampling jobs')


def test_distributed_scheduler_cleanup_old_jobs_with_lock() -> None:
    """Test _cleanup_old_jobs when lock is held."""
    with (
        patch('boto3.resource'),
        patch('companion_memory.scheduler.logger') as mock_logger,
    ):
        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = True

        # Mock JobTable and its cleanup method
        mock_job_table = MagicMock()
        mock_job_table.cleanup_old_jobs.return_value = 42  # Deleted 42 jobs

        with patch('companion_memory.job_table.JobTable', return_value=mock_job_table):
            # Call the method
            scheduler._cleanup_old_jobs()  # noqa: SLF001

            # Should create JobTable and call cleanup
            mock_job_table.cleanup_old_jobs.assert_called_once_with(older_than_days=7)

            # Should log success
            mock_logger.info.assert_called_with('Job cleanup completed: deleted %d old jobs', 42)


def test_distributed_scheduler_cleanup_old_jobs_without_lock() -> None:
    """Test _cleanup_old_jobs when lock is not held."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = False

        # Mock JobTable
        mock_job_table = MagicMock()

        with patch('companion_memory.job_table.JobTable', return_value=mock_job_table):
            # Call the method
            scheduler._cleanup_old_jobs()  # noqa: SLF001

            # Should not call cleanup when lock is not held
            mock_job_table.cleanup_old_jobs.assert_not_called()


def test_distributed_scheduler_cleanup_old_jobs_exception() -> None:
    """Test _cleanup_old_jobs when an exception occurs."""
    with (
        patch('boto3.resource'),
        patch('companion_memory.scheduler.logger') as mock_logger,
    ):
        scheduler = DistributedScheduler('TestTable')
        scheduler.lock.lock_acquired = True

        # Mock JobTable to raise an exception
        with patch('companion_memory.job_table.JobTable', side_effect=Exception('Import error')):
            # Call the method - should not raise exception
            scheduler._cleanup_old_jobs()  # noqa: SLF001

            # Should log the exception
            mock_logger.exception.assert_called_once_with('Error during job cleanup')


def test_distributed_scheduler_adds_cleanup_job() -> None:
    """Test that scheduler adds cleanup job when acquiring lock."""
    with (
        patch('boto3.resource'),
        patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class,
    ):
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')
        scheduler.scheduler = mock_scheduler
        scheduler.lock.lock_acquired = True

        # Call _add_active_jobs
        scheduler._add_active_jobs()  # noqa: SLF001

        # Should add cleanup job
        cleanup_calls = [
            call for call in mock_scheduler.add_job.call_args_list if len(call[0]) > 0 and 'cleanup' in str(call[0][0])
        ]
        assert len(cleanup_calls) == 1

        # Verify it's a cron job scheduled for 2 AM UTC
        call_args = cleanup_calls[0]
        assert call_args[0][1] == 'cron'  # Second positional arg should be 'cron'
        assert call_args[1]['hour'] == 2  # Should run at 2 AM
        assert call_args[1]['minute'] == 0  # Should run at :00 minutes
        assert call_args[1]['id'] == 'job_cleanup'


def test_distributed_scheduler_removes_cleanup_job() -> None:
    """Test that scheduler removes cleanup job when losing lock."""
    with (
        patch('boto3.resource'),
        patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class,
    ):
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')
        scheduler.scheduler = mock_scheduler
        scheduler._jobs_added = True  # Simulate jobs were added  # noqa: SLF001

        # Call _remove_active_jobs
        scheduler._remove_active_jobs()  # noqa: SLF001

        # Should remove cleanup job
        remove_calls = [call for call in mock_scheduler.remove_job.call_args_list if call[0][0] == 'job_cleanup']
        assert len(remove_calls) == 1
