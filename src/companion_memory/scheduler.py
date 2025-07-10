"""Distributed scheduler for coordinating background tasks across workers."""

import logging
import os
import time
import uuid
from collections.abc import Callable
from typing import Any

import boto3
from apscheduler.schedulers.background import BackgroundScheduler
from botocore.exceptions import ClientError
from slack_sdk import WebClient

logger = logging.getLogger(__name__)


class SchedulerLock:
    """DynamoDB-based distributed lock for scheduler coordination."""

    def __init__(self, table_name: str = 'CompanionMemory') -> None:
        """Initialize the scheduler lock using existing single table.

        Args:
            table_name: Name of the existing DynamoDB table

        """
        self.table_name = table_name
        self.partition_key = 'system#scheduler'
        self.sort_key = 'lock#main'
        self.process_id = f'{os.getpid()}-{uuid.uuid4()}'
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.lock_acquired = False

        # Get instance metadata for debugging
        self.instance_info = self._get_instance_info()

    def _get_instance_info(self) -> dict[str, Any]:
        """Get instance information for debugging and monitoring."""
        info = {
            'worker_pid': os.getpid(),
            'hostname': os.environ.get('HOSTNAME', 'unknown'),
            'timestamp': int(time.time()),
        }

        # Add Fly.io specific metadata if available
        if 'FLY_REGION' in os.environ:  # pragma: no cover
            info.update({
                'fly_region': os.environ.get('FLY_REGION'),
                'fly_app_name': os.environ.get('FLY_APP_NAME'),
                'fly_alloc_id': os.environ.get('FLY_ALLOC_ID'),
            })

        return info  # pragma: no cover

    def acquire(self) -> bool:
        """Attempt to acquire the distributed scheduler lock.

        Returns:
            True if lock was acquired, False otherwise

        """
        current_time = int(time.time())
        stale_time = current_time - 60  # Consider locks older than 60 seconds stale

        try:
            # Try to acquire lock with conditional write using single table keys
            self.table.put_item(
                Item={
                    'PK': self.partition_key,
                    'SK': self.sort_key,
                    'process_id': self.process_id,
                    'timestamp': current_time,
                    'ttl': current_time + 300,  # Auto-expire after 5 minutes
                    'instance_info': self.instance_info,
                    'lock_type': 'scheduler',  # For future different lock types
                },
                # Only succeed if no lock exists OR existing lock is stale
                ConditionExpression='attribute_not_exists(PK) OR #ts < :stale_time',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={':stale_time': stale_time},
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # Lock is held by another process
                return False
            # Re-raise other errors
            raise
        else:
            self.lock_acquired = True
            return True

    def refresh(self) -> bool:
        """Refresh the lock to indicate we're still alive.

        Returns:
            True if refresh was successful, False if we lost the lock

        """
        if not self.lock_acquired:
            return False

        current_time = int(time.time())

        try:
            # Update timestamp only if we still hold the lock
            self.table.update_item(
                Key={'PK': self.partition_key, 'SK': self.sort_key},
                UpdateExpression='SET #ts = :current_time, #ttl = :ttl, instance_info = :info',
                ConditionExpression='process_id = :process_id',
                ExpressionAttributeNames={'#ts': 'timestamp', '#ttl': 'ttl'},
                ExpressionAttributeValues={
                    ':current_time': current_time,
                    ':ttl': current_time + 300,
                    ':process_id': self.process_id,
                    ':info': self.instance_info,
                },
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # We lost the lock to another process
                self.lock_acquired = False
                return False
            # Re-raise other errors
            raise
        else:
            return True

    def release(self) -> None:
        """Release the scheduler lock."""
        if not self.lock_acquired:
            return

        try:
            # Delete lock only if we hold it
            self.table.delete_item(
                Key={'PK': self.partition_key, 'SK': self.sort_key},
                ConditionExpression='process_id = :process_id',
                ExpressionAttributeValues={':process_id': self.process_id},
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # Lock was already taken by another process
                pass
            else:
                # Log error but don't fail - cleanup is best-effort
                logger.warning('Failed to release scheduler lock: %s', e)
        finally:
            self.lock_acquired = False

    def get_current_lock_holder(self) -> dict[str, Any] | None:
        """Get information about the current lock holder (for debugging).

        Returns:
            Lock information if it exists, None otherwise

        """
        try:
            response = self.table.get_item(Key={'PK': self.partition_key, 'SK': self.sort_key})
            item = response.get('Item')
        except ClientError:
            return None
        else:
            return item if item is not None else None


class DistributedScheduler:
    """Distributed scheduler using DynamoDB for coordination across workers."""

    def __init__(self, table_name: str = 'CompanionMemory') -> None:
        """Initialize the distributed scheduler.

        Args:
            table_name: DynamoDB table name (reuses existing table)

        """
        self.scheduler: BackgroundScheduler | None = None
        self.lock = SchedulerLock(table_name)
        self.started = False
        self._refresh_interval = 30  # Refresh lock every 30 seconds

    def start(self) -> bool:
        """Start the scheduler if we can acquire the distributed lock.

        Returns:
            True if scheduler was started, False if another instance is running

        """
        if self.started:
            return True

        if self.lock.acquire():
            self.scheduler = BackgroundScheduler()
            self.scheduler.start()
            self.started = True

            # Schedule lock refresh job
            self.scheduler.add_job(
                self._refresh_lock, 'interval', seconds=self._refresh_interval, id='lock_refresh', max_instances=1
            )

            # Schedule heartbeat logger
            self.scheduler.add_job(
                self._heartbeat_logger, 'interval', seconds=60, id='heartbeat_logger', max_instances=1
            )

            return True

        return False

    def _refresh_lock(self) -> None:
        """Refresh the distributed lock to maintain ownership."""
        if not self.lock.refresh():
            # We lost the lock - shut down scheduler
            logger.warning('Lost scheduler lock, shutting down...')
            self.shutdown()

    def _heartbeat_logger(self) -> None:
        """Log a heartbeat message to indicate scheduler is active."""
        logger.info('Scheduler heartbeat - process %s active', self.lock.process_id)

    def add_job(self, func: Callable[..., Any], trigger: str, **kwargs: str | int | bool | None) -> None:
        """Add a job to the scheduler.

        Args:
            func: Function to schedule
            trigger: Trigger type (e.g., 'interval', 'cron')
            **kwargs: Additional arguments for the job

        """
        if self.scheduler and self.started:
            self.scheduler.add_job(func, trigger, **kwargs)

    def shutdown(self) -> None:
        """Shutdown the scheduler and release the distributed lock."""
        if self.scheduler and self.started:
            try:
                self.scheduler.shutdown(wait=True)
            except Exception:
                logger.exception('Error shutting down scheduler')
            finally:
                self.started = False

        self.lock.release()

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status for monitoring/debugging.

        Returns:
            Status information including lock holder details

        """
        current_lock = self.lock.get_current_lock_holder()

        return {
            'scheduler_started': self.started,
            'lock_acquired': self.lock.lock_acquired,
            'process_id': self.lock.process_id,
            'current_lock_holder': current_lock,
            'instance_info': self.lock.instance_info,
        }


_scheduler_instance: DistributedScheduler | None = None


def get_scheduler() -> DistributedScheduler:
    """Get the distributed scheduler instance.

    Returns:
        DistributedScheduler instance

    """
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = DistributedScheduler()
    return _scheduler_instance


def get_slack_client() -> WebClient:
    """Get the Slack client instance.

    Returns:
        WebClient instance configured with bot token from environment

    Raises:
        ValueError: If SLACK_BOT_TOKEN environment variable is not set

    """
    bot_token = os.environ.get('SLACK_BOT_TOKEN')
    if not bot_token:
        msg = 'SLACK_BOT_TOKEN environment variable is required'
        raise ValueError(msg)

    return WebClient(token=bot_token)
