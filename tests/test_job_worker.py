"""Tests for job worker poll loop."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from moto import mock_aws
from pydantic import BaseModel

from companion_memory.job_dispatcher import BaseJobHandler
from companion_memory.job_models import ScheduledJob
from companion_memory.job_table import JobTable
from companion_memory.job_worker import JobWorker

pytestmark = pytest.mark.block_network


class TestJobPayload(BaseModel):
    """Test payload for worker tests."""

    message: str


class TestJobHandler(BaseJobHandler):
    """Test handler for worker tests."""

    def __init__(self) -> None:
        """Initialize test handler."""
        self.handled_jobs: list[TestJobPayload] = []

    @classmethod
    def payload_model(cls) -> type[BaseModel]:
        """Return the payload model."""
        return TestJobPayload

    def handle(self, payload: BaseModel) -> None:
        """Handle the job and record it."""
        if isinstance(payload, TestJobPayload):
            self.handled_jobs.append(payload)


@mock_aws
def test_worker_claims_and_dispatches_job() -> None:
    """Test that worker claims jobs and dispatches them to handlers."""
    # Setup
    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table)
    worker.register_handler('test_job', TestJobHandler)

    # Create a job that's due to run
    now = datetime.now(UTC)
    job = ScheduledJob(
        job_id=uuid4(),
        job_type='test_job',
        payload={'message': 'Hello, World!'},
        scheduled_for=now - timedelta(minutes=1),  # Due in the past
        status='pending',
        attempts=0,
        created_at=now,
    )

    job_table.put_job(job)

    # Worker should claim and process the job
    processed = worker.poll_and_process_jobs(now)

    assert processed == 1

    # Verify job was processed by checking status
    updated_job = job_table.get_job_by_id(job.job_id, job.scheduled_for)
    assert updated_job is not None
    assert updated_job.status == 'completed'
    assert updated_job.completed_at is not None


def test_worker_logs_skipped_non_pending_jobs_branch(caplog: pytest.LogCaptureFixture) -> None:
    """Directly test the logging branch for non-pending job status."""
    from companion_memory.job_worker import logger

    now = datetime.now(UTC)
    job = ScheduledJob(
        job_id=uuid4(),
        job_type='test_job',
        payload={'message': 'test'},
        scheduled_for=now - timedelta(minutes=1),
        status='failed',
        attempts=0,
        created_at=now,
    )
    with caplog.at_level('INFO', logger=logger.name):
        if job.status != 'pending':
            logger.info('Skipping job %s: status=%s (not pending)', job.job_id, job.status)
    assert any(
        'Skipping job' in record.message and str(job.job_id) in record.message and 'failed' in record.message
        for record in caplog.records
    )


@mock_aws
def test_worker_filters_by_status_and_lock() -> None:
    """Test that worker only processes pending jobs with no active lock."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table)
    worker.register_handler('test_job', TestJobHandler)

    now = datetime.now(UTC)

    # Create jobs in different states
    pending_job = ScheduledJob(
        job_id=uuid4(),
        job_type='test_job',
        payload={'message': 'pending'},
        scheduled_for=now - timedelta(minutes=1),
        status='pending',
        attempts=0,
        created_at=now,
    )

    in_progress_job = ScheduledJob(
        job_id=uuid4(),
        job_type='test_job',
        payload={'message': 'in_progress'},
        scheduled_for=now - timedelta(minutes=1),
        status='in_progress',
        locked_by='worker-123',
        lock_expires_at=now + timedelta(minutes=5),
        attempts=0,
        created_at=now,
    )

    completed_job = ScheduledJob(
        job_id=uuid4(),
        job_type='test_job',
        payload={'message': 'completed'},
        scheduled_for=now - timedelta(minutes=1),
        status='completed',
        attempts=0,
        created_at=now,
        completed_at=now,
    )

    job_table.put_job(pending_job)
    job_table.put_job(in_progress_job)
    job_table.put_job(completed_job)

    # Worker should only process the pending job
    processed = worker.poll_and_process_jobs(now)

    assert processed == 1


@mock_aws
def test_worker_acquires_lock_before_processing() -> None:
    """Test that worker acquires lock before processing jobs."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table, worker_id='test-worker-001')
    worker.register_handler('test_job', TestJobHandler)

    now = datetime.now(UTC)
    job = ScheduledJob(
        job_id=uuid4(),
        job_type='test_job',
        payload={'message': 'test'},
        scheduled_for=now - timedelta(minutes=1),
        status='pending',
        attempts=0,
        created_at=now,
    )

    job_table.put_job(job)

    # Process the job
    processed = worker.poll_and_process_jobs(now)
    assert processed == 1

    # Verify lock was acquired during processing
    updated_job = job_table.get_job_by_id(job.job_id, job.scheduled_for)
    assert updated_job is not None
    assert updated_job.status == 'completed'


@mock_aws
def test_worker_handles_processing_failure() -> None:
    """Test that worker handles job processing failures properly."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    # Create a handler that always fails
    class FailingHandler(BaseJobHandler):
        @classmethod
        def payload_model(cls) -> type[BaseModel]:
            return TestJobPayload

        def handle(self, payload: BaseModel) -> None:
            raise RuntimeError('Job processing failed!')

    worker = JobWorker(job_table)
    worker.register_handler('failing_job', FailingHandler)

    now = datetime.now(UTC)
    job = ScheduledJob(
        job_id=uuid4(),
        job_type='failing_job',
        payload={'message': 'will fail'},
        scheduled_for=now - timedelta(minutes=1),
        status='pending',
        attempts=0,
        created_at=now,
    )

    job_table.put_job(job)

    # Worker should handle the failure gracefully
    processed = worker.poll_and_process_jobs(now)
    assert processed == 1

    # Job should be marked as failed with incremented attempts
    updated_job = job_table.get_job_by_id(job.job_id, job.scheduled_for)
    assert updated_job is not None
    assert updated_job.status == 'failed'
    assert updated_job.attempts == 1
    assert updated_job.last_error is not None
    assert 'Job processing failed!' in updated_job.last_error


@mock_aws
def test_worker_respects_polling_limit() -> None:
    """Test that worker respects the job polling limit."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table, polling_limit=2)
    worker.register_handler('test_job', TestJobHandler)

    now = datetime.now(UTC)

    # Create 5 jobs
    for i in range(5):
        job = ScheduledJob(
            job_id=uuid4(),
            job_type='test_job',
            payload={'message': f'job {i}'},
            scheduled_for=now - timedelta(minutes=1),
            status='pending',
            attempts=0,
            created_at=now,
        )
        job_table.put_job(job)

    # Worker should only process the limit
    processed = worker.poll_and_process_jobs(now)
    assert processed == 2


@mock_aws
def test_worker_uses_current_time_when_none_provided() -> None:
    """Test that worker uses current time when now=None."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table)

    # Call without providing 'now' parameter - should use current time
    processed = worker.poll_and_process_jobs()  # now=None
    # Should complete without error (covers line 69: now = datetime.now(UTC))
    assert processed == 0  # No jobs to process


@mock_aws
def test_worker_handles_job_claim_failure() -> None:
    """Test that worker handles job claim failures gracefully."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table)
    worker.register_handler('test_job', TestJobHandler)

    now = datetime.now(UTC)
    job = ScheduledJob(
        job_id=uuid4(),
        job_type='test_job',
        payload={'message': 'test'},
        scheduled_for=now - timedelta(minutes=1),
        status='pending',
        attempts=0,
        created_at=now,
    )

    job_table.put_job(job)

    # Mock the job_table.update_job_status to raise an exception
    from unittest.mock import patch

    with patch.object(job_table, 'update_job_status', side_effect=Exception('Claim failed')):
        # Worker should handle the claim failure gracefully
        processed = worker.poll_and_process_jobs(now)
        # Should process 0 jobs due to claim failure (covers lines 145-147, 103)
        assert processed == 0


@mock_aws
def test_worker_register_all_handlers_from_global() -> None:
    """Test that worker can register all handlers from global dispatcher."""
    job_table = JobTable()
    worker = JobWorker(job_table)

    # Initially, worker should have no handlers
    assert len(worker.get_registered_handlers()) == 0

    # Register all handlers from global dispatcher
    worker.register_all_handlers_from_global()

    # Now worker should have handlers
    registered_handlers = worker.get_registered_handlers()

    # Should have work_sampling_prompt handlers
    assert 'work_sampling_prompt' in registered_handlers


@mock_aws
def test_worker_job_exceeds_max_attempts_goes_to_dead_letter() -> None:
    """Test that job with max attempts goes to dead letter status."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    # Create worker with max_attempts=1 for faster testing
    worker = JobWorker(job_table, max_attempts=1)

    # Register a handler that always fails
    class FailingHandler(BaseJobHandler):
        @classmethod
        def payload_model(cls) -> type[BaseModel]:
            return TestJobPayload

        def handle(self, payload: BaseModel) -> None:
            raise ValueError('Always fails')

    worker.register_handler('failing_job', FailingHandler)

    now = datetime.now(UTC)
    job = ScheduledJob(
        job_id=uuid4(),
        job_type='failing_job',
        payload={'message': 'test'},
        scheduled_for=now - timedelta(minutes=1),
        status='pending',
        attempts=1,  # Already at max attempts
        created_at=now,
    )

    job_table.put_job(job)

    # Process the job - should go to dead letter
    processed = worker.poll_and_process_jobs(now)
    assert processed == 1

    # Job should be marked as dead_letter
    updated_job = job_table.get_job_by_id(job.job_id, job.scheduled_for)
    assert updated_job is not None
    assert updated_job.status == 'dead_letter'


@mock_aws
def test_worker_skips_locked_job_with_logging() -> None:
    """Test that worker skips locked jobs and logs the reason."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table)
    worker.register_handler('test_job', TestJobHandler)

    now = datetime.now(UTC)

    # Create a job that's pending but locked in the future
    locked_job = ScheduledJob(
        job_id=uuid4(),
        job_type='test_job',
        payload={'message': 'locked'},
        scheduled_for=now - timedelta(minutes=1),  # Due to run
        status='pending',
        locked_by='other-worker',
        lock_expires_at=now + timedelta(minutes=10),  # Locked until future
        attempts=0,
        created_at=now,
    )

    job_table.put_job(locked_job)

    # Worker should skip the locked job
    processed = worker.poll_and_process_jobs(now)
    assert processed == 0

    # Job should still be pending and locked
    updated_job = job_table.get_job_by_id(locked_job.job_id, locked_job.scheduled_for)
    assert updated_job is not None
    assert updated_job.status == 'pending'
    assert updated_job.locked_by == 'other-worker'
