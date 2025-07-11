"""Job worker for polling and processing scheduled jobs."""

import traceback
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from companion_memory.job_dispatcher import BaseJobHandler, JobDispatcher
from companion_memory.job_models import ScheduledJob

if TYPE_CHECKING:  # pragma: no cover
    from companion_memory.job_table import JobTable


class JobWorker:
    """Worker for polling and processing scheduled jobs."""

    def __init__(
        self,
        job_table: 'JobTable',
        worker_id: str | None = None,
        polling_limit: int = 25,
        lock_timeout_minutes: int = 10,
    ) -> None:
        """Initialize the job worker.

        Args:
            job_table: Job table instance for job operations
            worker_id: Unique identifier for this worker instance
            polling_limit: Maximum number of jobs to fetch per poll
            lock_timeout_minutes: How long to hold job locks

        """
        self._job_table = job_table
        self._worker_id = worker_id or f'worker-{uuid.uuid4().hex[:8]}'
        self._polling_limit = polling_limit
        self._lock_timeout = timedelta(minutes=lock_timeout_minutes)
        self._dispatcher = JobDispatcher()

    def register_handler(self, job_type: str, handler_class: type[BaseJobHandler]) -> None:
        """Register a handler for a specific job type.

        Args:
            job_type: The job type string
            handler_class: The handler class

        """
        self._dispatcher.register(job_type, handler_class)

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
                continue

            # Claim and run the job
            if self._claim_and_run(job, now):
                processed_count += 1

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
            return False

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
        except Exception:  # noqa: BLE001
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

        except Exception as e:  # noqa: BLE001
            # Mark job as failed and record error
            error_message = f'{type(e).__name__}: {e}\n{traceback.format_exc()}'

            self._job_table.update_job_status(
                job.job_id,
                job.scheduled_for,
                'failed',
                attempts=job.attempts + 1,
                last_error=error_message,
                locked_by=None,
                lock_expires_at=None,
            )
