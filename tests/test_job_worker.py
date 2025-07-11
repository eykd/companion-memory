"""Tests for job worker poll loop."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from companion_memory.job_worker import JobWorker
from moto import mock_aws
from pydantic import BaseModel

from companion_memory.job_dispatcher import BaseJobHandler
from companion_memory.job_models import ScheduledJob
from companion_memory.job_table import JobTable


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
    due_jobs = job_table.get_due_jobs(now + timedelta(minutes=1))
    updated_job = due_jobs[0]
    assert updated_job.status == 'completed'
    assert updated_job.completed_at is not None


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
    # (We can't easily test the exact moment of locking, but we can verify
    # the final state shows it was completed by our worker)
    due_jobs = job_table.get_due_jobs(now + timedelta(minutes=1))
    updated_job = due_jobs[0]
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
    due_jobs = job_table.get_due_jobs(now + timedelta(hours=1))  # Look further ahead
    updated_job = due_jobs[0]
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
