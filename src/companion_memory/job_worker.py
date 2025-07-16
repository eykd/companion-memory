"""Job worker for polling and processing scheduled jobs."""

import logging
import traceback
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import sentry_sdk

from companion_memory.job_dispatcher import BaseJobHandler, JobDispatcher
from companion_memory.job_models import ScheduledJob
from companion_memory.retry_policy import RetryPolicy

if TYPE_CHECKING:  # pragma: no cover
    from companion_memory.job_table import JobTable

logger = logging.getLogger(__name__)


class JobWorker:
    """Worker for polling and processing scheduled jobs."""

    def __init__(
        self,
        job_table: 'JobTable',
        worker_id: str | None = None,
        polling_limit: int = 25,
        lock_timeout_minutes: int = 10,
        max_attempts: int = 5,
        base_delay_seconds: int = 60,
    ) -> None:
        """Initialize the job worker.

        Args:
            job_table: Job table instance for job operations
            worker_id: Unique identifier for this worker instance
            polling_limit: Maximum number of jobs to fetch per poll
            lock_timeout_minutes: How long to hold job locks
            max_attempts: Maximum retry attempts before dead letter
            base_delay_seconds: Base delay for exponential backoff

        """
        self._job_table = job_table
        self._worker_id = worker_id or f'worker-{uuid.uuid4().hex[:8]}'
        self._polling_limit = polling_limit
        self._lock_timeout = timedelta(minutes=lock_timeout_minutes)
        self._dispatcher = JobDispatcher()
        self._retry_policy = RetryPolicy(base_delay_seconds, max_attempts)

    def register_handler(self, job_type: str, handler_class: type[BaseJobHandler]) -> None:
        """Register a handler for a specific job type.

        Args:
            job_type: The job type string
            handler_class: The handler class

        """
        self._dispatcher.register(job_type, handler_class)

    def register_all_handlers_from_global(self) -> None:
        """Register all handlers from the global dispatcher."""
        # Import handler modules to ensure decorators are executed
        import companion_memory.summary_jobs
        import companion_memory.work_sampling_handler  # noqa: F401
        from companion_memory.job_dispatcher import register_all_handlers

        register_all_handlers(self._dispatcher)

    def get_registered_handlers(self) -> dict[str, type[BaseJobHandler]]:
        """Get all registered handlers from this worker's dispatcher.

        Returns:
            Dictionary mapping job types to handler classes

        """
        return self._dispatcher.get_registered_handlers()

    def poll_and_process_jobs(self, now: datetime | None = None) -> int:
        """Poll for due jobs and process them.

        Args:
            now: Current time for polling (defaults to datetime.now(UTC))

        Returns:
            Number of jobs processed

        """
        if now is None:
            now = datetime.now(UTC)

        # Fetch due jobs
        due_jobs = self._job_table.get_due_jobs(now, limit=self._polling_limit)

        processed_count = 0

        for job in due_jobs:
            # Filter jobs that are eligible for processing
            if not self._is_job_eligible(job, now):
                # Log why job was skipped
                # Job skipped (debug logging removed)
                continue

            # Claim and run the job
            if self._claim_and_run(job, now):
                processed_count += 1
                logger.info('Job completed: %s', job.job_id)
            else:
                pass  # Failed to claim job (debug logging removed)

        return processed_count

    def _claim_and_run(self, job: ScheduledJob, now: datetime) -> bool:
        """Claim a job and run it, handling both success and failure.

        Args:
            job: The job to claim and run
            now: Current time

        Returns:
            True if job was successfully claimed and processed

        """
        # Try to claim the job
        if self._try_claim_job(job, now):
            # Process the job
            self._process_job(job, now)
            return True
        return False

    def _is_job_eligible(self, job: ScheduledJob, now: datetime) -> bool:
        """Check if a job is eligible for processing.

        Args:
            job: The job to check
            now: Current time

        Returns:
            True if job can be processed

        """
        # Only process pending jobs
        if job.status != 'pending':
            return False  # pragma: no cover

        # Check if lock has expired (job is eligible if lock is None or expired)
        return not (job.lock_expires_at is not None and job.lock_expires_at > now)

    def _try_claim_job(self, job: ScheduledJob, now: datetime) -> bool:
        """Try to claim a job by acquiring a lock.

        Args:
            job: The job to claim
            now: Current time

        Returns:
            True if job was successfully claimed

        """
        try:
            # Update job to in_progress with our worker ID and lock expiration
            lock_expires_at = now + self._lock_timeout

            self._job_table.update_job_status(
                job.job_id,
                job.scheduled_for,
                'in_progress',
                locked_by=self._worker_id,
                lock_expires_at=lock_expires_at.isoformat(),
            )
        except Exception:  # noqa: BLE001  # pragma: no cover
            # Failed to claim (likely due to race condition)
            return False
        else:
            return True

    def _process_job(self, job: ScheduledJob, now: datetime) -> None:
        """Process a claimed job.

        Args:
            job: The job to process
            now: Current time

        """
        try:
            # Dispatch job to handler
            self._dispatcher.dispatch(job)

            # Mark job as completed
            self._job_table.update_job_status(
                job.job_id,
                job.scheduled_for,
                'completed',
                completed_at=now.isoformat(),
                locked_by=None,
                lock_expires_at=None,
            )

        except Exception as e:  # pragma: no cover
            # Handle job failure with retry policy
            logger.exception('Job %s failed during processing', job.job_id)
            self._handle_job_failure(job, e, now)

    def _handle_job_failure(self, job: ScheduledJob, error: Exception, now: datetime) -> None:
        """Handle job failure with retry policy and backoff.

        Args:
            job: The failed job
            error: The exception that occurred
            now: Current time

        """
        error_message = f'{type(error).__name__}: {error}\n{traceback.format_exc()}'
        new_attempts = job.attempts + 1

        # Job failure (debug logging removed)

        # Report error to Sentry with full job context
        self._report_to_sentry(job, error)

        # Determine if job should be retried or go to dead letter
        if self._retry_policy.should_retry(new_attempts):
            # Calculate next run time with exponential backoff
            next_run = self._retry_policy.calculate_next_run(now, new_attempts)

            # Reschedule the job for later
            self._reschedule_job(job, next_run, new_attempts, error_message)
        else:
            # Job dead letter (debug logging removed)
            # Job has exceeded max attempts, send to dead letter
            self._job_table.update_job_status(
                job.job_id,
                job.scheduled_for,
                'dead_letter',
                attempts=new_attempts,
                last_error=error_message,
                locked_by=None,
                lock_expires_at=None,
            )

    def _reschedule_job(self, job: ScheduledJob, next_run: datetime, attempts: int, error_message: str) -> None:
        """Reschedule a failed job for later execution.

        Args:
            job: The original job
            next_run: When the job should run next
            attempts: Number of attempts
            error_message: Error message to record

        """
        # Update the current job to mark it as failed
        self._job_table.update_job_status(
            job.job_id,
            job.scheduled_for,
            'failed',
            attempts=attempts,
            last_error=error_message,
            locked_by=None,
            lock_expires_at=None,
        )

        # Create a new job with updated scheduled_for time
        rescheduled_job = ScheduledJob(
            job_id=job.job_id,
            job_type=job.job_type,
            payload=job.payload,
            scheduled_for=next_run,
            status='pending',
            attempts=attempts,
            last_error=error_message,
            created_at=job.created_at,
        )

        # Store the rescheduled job
        self._job_table.put_job(rescheduled_job)

    def _report_to_sentry(self, job: ScheduledJob, error: Exception) -> None:
        """Report job failure to Sentry with full context.

        Args:
            job: The failed job
            error: The exception that occurred

        """
        # Set job context for Sentry
        sentry_sdk.set_context(
            'job',
            {
                'job_id': str(job.job_id),
                'job_type': job.job_type,
                'attempts': job.attempts,
                'payload': job.payload,
                'scheduled_for': job.scheduled_for.isoformat(),
            },
        )

        # Capture the exception
        sentry_sdk.capture_exception(error)
