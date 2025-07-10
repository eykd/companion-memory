"""Tests for distributed scheduler."""

from unittest.mock import MagicMock, patch

import pytest

from companion_memory.scheduler import (
    DistributedScheduler,
    SchedulerLock,
    get_scheduler,
    get_slack_client,
)


def test_scheduler_lock_key_format() -> None:
    """Test that scheduler lock uses correct table key format."""
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
    # Clear any existing singleton
    if hasattr(get_scheduler, '_instance'):
        delattr(get_scheduler, '_instance')

    scheduler1 = get_scheduler()
    scheduler2 = get_scheduler()

    assert scheduler1 is scheduler2


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
    """Test scheduler start success."""
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
        mock_scheduler.add_job.assert_called_once()
        mock_acquire.assert_called_once()


def test_distributed_scheduler_start_already_started() -> None:
    """Test scheduler start when already started."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')
        scheduler.started = True

        result = scheduler.start()

        assert result is True


def test_distributed_scheduler_start_failure() -> None:
    """Test scheduler start failure (lock not acquired)."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')

        # Mock failed lock acquisition
        mock_acquire = MagicMock(return_value=False)
        with patch.object(scheduler.lock, 'acquire', mock_acquire):
            result = scheduler.start()

        assert result is False
        assert scheduler.started is False
        mock_acquire.assert_called_once()


def test_distributed_scheduler_refresh_lock_success() -> None:
    """Test scheduler refresh lock success."""
    with patch('boto3.resource'):
        scheduler = DistributedScheduler('TestTable')
        mock_refresh = MagicMock(return_value=True)
        with patch.object(scheduler.lock, 'refresh', mock_refresh):
            # Access private method for testing
            scheduler._refresh_lock()  # noqa: SLF001

            mock_refresh.assert_called_once()


def test_distributed_scheduler_refresh_lock_failure() -> None:
    """Test scheduler refresh lock failure."""
    with patch('boto3.resource'), patch('companion_memory.scheduler.logger') as mock_logger:
        scheduler = DistributedScheduler('TestTable')
        mock_refresh = MagicMock(return_value=False)
        mock_shutdown = MagicMock()
        with patch.object(scheduler.lock, 'refresh', mock_refresh), patch.object(scheduler, 'shutdown', mock_shutdown):
            # Access private method for testing
            scheduler._refresh_lock()  # noqa: SLF001

            mock_refresh.assert_called_once()
            mock_logger.warning.assert_called_once()
            mock_shutdown.assert_called_once()


def test_distributed_scheduler_add_job_when_started() -> None:
    """Test adding job when scheduler is started."""
    with patch('boto3.resource'), patch('companion_memory.scheduler.BackgroundScheduler') as mock_scheduler_class:
        mock_scheduler = MagicMock()
        mock_scheduler_class.return_value = mock_scheduler

        scheduler = DistributedScheduler('TestTable')
        scheduler.started = True
        scheduler.scheduler = mock_scheduler

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

    with patch('companion_memory.scheduler.SchedulerLock.acquire') as mock_acquire:
        mock_acquire.return_value = True

        # Create app - this should start the scheduler
        app = create_app()

        # Verify we can access the status endpoint
        with app.test_client() as client:
            response = client.get('/scheduler/status')
            assert response.status_code == 200

        # Clean up
        scheduler = get_scheduler()
        scheduler.shutdown()


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
