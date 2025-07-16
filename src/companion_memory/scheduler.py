"""Distributed scheduler for coordinating background tasks across workers."""

import contextlib
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

from companion_memory.storage import LogStore
from companion_memory.summarizer import LLMClient
from companion_memory.user_sync import sync_user_timezone

logger = logging.getLogger(__name__)

# Configure APScheduler logging to reduce verbosity
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)


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
        # Use specified region or default to us-east-1 for testing
        region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
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
        self._lock_check_interval = 30  # Check lock every 30 seconds
        self._jobs_added = False  # Track if we've added active jobs
        self._log_store: LogStore | None = None  # Will be injected by Flask app
        self._llm: LLMClient | None = None  # Will be injected by Flask app
        self._job_worker_enabled = True  # Enable job worker by default
        self._job_worker_polling_interval = 30  # Poll for jobs every 30 seconds
        self._job_worker: Any = None  # Will be lazily initialized

    def start(self) -> bool:
        """Start the scheduler and begin competing for the distributed lock.

        Always starts the scheduler. Workers compete for the DynamoDB lock,
        and only the lock holder executes jobs. Workers without the lock
        periodically attempt to acquire it.

        Returns:
            True (always succeeds in starting the scheduler infrastructure)

        """
        if self.started:
            return True

        # Always start the BackgroundScheduler
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.started = True

        # Add the lock management job that runs on all workers
        self.scheduler.add_job(
            self._manage_lock, 'interval', seconds=self._lock_check_interval, id='lock_manager', max_instances=1
        )

        # Try to acquire lock immediately and add jobs if successful
        self._attempt_lock_acquisition()

        return True

    def _manage_lock(self) -> None:
        """Manage the distributed lock - refresh if held, attempt to acquire if not held."""
        if self.lock.lock_acquired:
            # We have the lock - try to refresh it
            if not self.lock.refresh():
                # We lost the lock - remove active jobs but keep trying to reacquire
                logger.warning('Lost scheduler lock, removing jobs but continuing to compete for lock')
                self._remove_active_jobs()
        else:
            # We don't have the lock - try to acquire it
            self._attempt_lock_acquisition()

    def _attempt_lock_acquisition(self) -> None:
        """Attempt to acquire the distributed lock and add jobs if successful."""
        if self.lock.acquire():
            logger.info('Acquired scheduler lock - process %s now active', self.lock.process_id)
            self._add_active_jobs()

    def _add_active_jobs(self) -> None:
        """Add active jobs when we acquire the lock."""
        if self._jobs_added or not self.scheduler:
            return

        # Schedule user time zone sync every 6 hours
        self.scheduler.add_job(sync_user_timezone, 'interval', hours=6, id='user_timezone_sync', max_instances=1)

        # Schedule daily summary scheduling job (runs hourly)
        self.scheduler.add_job(
            self._schedule_daily_summaries, 'interval', hours=1, id='daily_summary_scheduler', max_instances=1
        )

        # Schedule work sampling prompt scheduling job (runs hourly)
        self.scheduler.add_job(
            self._schedule_work_sampling_jobs, 'interval', hours=1, id='work_sampling_scheduler', max_instances=1
        )

        # Schedule job worker polling if enabled
        if self._job_worker_enabled:
            self.scheduler.add_job(
                self._poll_and_process_jobs,
                'interval',
                seconds=self._job_worker_polling_interval,
                id='job_worker_poller',
                max_instances=1,
            )

        # Schedule job cleanup (runs daily at 2 AM UTC)
        self.scheduler.add_job(
            self._cleanup_old_jobs,
            'cron',
            hour=2,
            minute=0,
            id='job_cleanup',
            max_instances=1,
        )

        self._jobs_added = True

    def _remove_active_jobs(self) -> None:
        """Remove active jobs when we lose the lock."""
        if not self._jobs_added or not self.scheduler:
            return

        # Remove daily summary scheduler
        with contextlib.suppress(Exception):
            self.scheduler.remove_job('daily_summary_scheduler')

        # Remove work sampling scheduler
        with contextlib.suppress(Exception):
            self.scheduler.remove_job('work_sampling_scheduler')

        # Remove job worker poller
        with contextlib.suppress(Exception):
            self.scheduler.remove_job('job_worker_poller')

        # Remove job cleanup
        with contextlib.suppress(Exception):
            self.scheduler.remove_job('job_cleanup')

        self._jobs_added = False

    def _poll_and_process_jobs(self) -> None:
        """Poll and process scheduled jobs from the job queue."""
        # Double-check we still have the lock before processing
        if not self.lock.lock_acquired:
            return

        try:
            # Lazy initialize job worker to avoid circular imports
            if self._job_worker is None:  # pragma: no branch
                from companion_memory.job_table import JobTable
                from companion_memory.job_worker import JobWorker

                job_table = JobTable()
                self._job_worker = JobWorker(job_table)

                # Register all handlers with the job worker
                self._job_worker.register_all_handlers_from_global()

            # Poll and process jobs
            self._job_worker.poll_and_process_jobs()

        except Exception:
            logger.exception('Error in job worker polling')

    def _schedule_daily_summaries(self) -> None:
        """Schedule daily summary jobs for all configured users."""
        # Double-check we still have the lock before processing
        if not self.lock.lock_acquired:
            return

        try:
            # Lazy import to avoid circular imports
            from companion_memory.daily_summary_scheduler import schedule_daily_summaries
            from companion_memory.deduplication import DeduplicationIndex
            from companion_memory.job_table import JobTable
            from companion_memory.user_settings import DynamoUserSettingsStore

            # Set up dependencies
            user_settings_store = DynamoUserSettingsStore()
            job_table = JobTable()
            deduplication_index = DeduplicationIndex()

            # Schedule daily summaries
            schedule_daily_summaries(
                user_settings_store=user_settings_store,
                job_table=job_table,
                deduplication_index=deduplication_index,
            )
            logger.info('Scheduled daily summary jobs')

        except Exception:
            logger.exception('Error scheduling daily summaries')

    def _schedule_work_sampling_jobs(self) -> None:
        """Schedule work sampling prompt jobs for all users."""
        # Double-check we still have the lock before processing
        if not self.lock.lock_acquired:
            return

        try:
            # Lazy import to avoid circular imports
            from companion_memory.deduplication import DeduplicationIndex
            from companion_memory.job_table import JobTable
            from companion_memory.user_settings import DynamoUserSettingsStore
            from companion_memory.work_sampling_scheduler import schedule_work_sampling_jobs

            # Set up dependencies
            user_settings_store = DynamoUserSettingsStore()
            job_table = JobTable()
            deduplication_index = DeduplicationIndex()

            # Schedule work sampling jobs
            schedule_work_sampling_jobs(
                user_settings_store=user_settings_store,
                job_table=job_table,
                deduplication_index=deduplication_index,
            )

        except Exception:
            logger.exception('Error scheduling work sampling jobs')

    def _cleanup_old_jobs(self) -> None:
        """Clean up old completed, failed, and dead_letter jobs."""
        # Double-check we still have the lock before processing
        if not self.lock.lock_acquired:
            return

        try:
            # Lazy import to avoid circular imports
            from companion_memory.job_table import JobTable

            job_table = JobTable()
            deleted_count = job_table.cleanup_old_jobs(older_than_days=7)
            logger.info('Job cleanup completed: deleted %d old jobs', deleted_count)

        except Exception:
            logger.exception('Error during job cleanup')

    def configure_dependencies(self, log_store: LogStore, llm: LLMClient) -> None:
        """Configure log store and LLM dependencies for scheduler jobs.

        Args:
            log_store: Storage implementation for fetching logs
            llm: LLM client for generating summaries

        """
        self._log_store = log_store
        self._llm = llm

    def add_job(self, func: Callable[..., Any], trigger: str, **kwargs: str | int | bool | None) -> None:
        """Add a job to the scheduler (only executes if this worker holds the lock).

        Args:
            func: Function to schedule
            trigger: Trigger type (e.g., 'interval', 'cron')
            **kwargs: Additional arguments for the job

        """
        if self.scheduler and self.started and self.lock.lock_acquired:
            self.scheduler.add_job(func, trigger, **kwargs)

    def shutdown(self) -> None:
        """Shutdown the scheduler and release the distributed lock."""
        if self.scheduler and self.started:
            try:
                # Remove active jobs first
                self._remove_active_jobs()
                # Shutdown the scheduler
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
