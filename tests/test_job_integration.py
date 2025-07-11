"""Integration tests for complete job scheduling and processing pipeline."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from moto import mock_aws
from pydantic import BaseModel

from companion_memory.deduplication import DeduplicationIndex
from companion_memory.job_dispatcher import BaseJobHandler
from companion_memory.job_models import ScheduledJob
from companion_memory.job_table import JobTable
from companion_memory.job_worker import JobWorker


class TestIntegrationPayload(BaseModel):
    """Test payload for integration tests."""

    message: str
    user_id: str


class IntegrationTestHandler(BaseJobHandler):
    """Test handler that tracks processed jobs."""

    def __init__(self) -> None:
        """Initialize handler with tracking."""
        self.processed_jobs: list[TestIntegrationPayload] = []

    @classmethod
    def payload_model(cls) -> type[BaseModel]:
        """Return payload model."""
        return TestIntegrationPayload

    def handle(self, payload: BaseModel) -> None:
        """Handle job and track it."""
        if isinstance(payload, TestIntegrationPayload):
            self.processed_jobs.append(payload)


@mock_aws
def test_complete_job_lifecycle_schedule_to_completion() -> None:
    """Test complete job lifecycle from scheduling to successful completion."""
    # Setup infrastructure
    job_table = JobTable()
    job_table.create_table_for_testing()

    deduplication = DeduplicationIndex('CompanionMemory')
    deduplication.create_table_for_testing()
    worker = JobWorker(job_table)

    # Register our test handler
    worker.register_handler('integration_test', IntegrationTestHandler)

    now = datetime.now(UTC)

    # 1. Schedule a job using deduplication (simulates real usage)
    logical_id = 'test-user-daily-summary'
    date_str = now.strftime('%Y-%m-%d')

    job = ScheduledJob(
        job_id=uuid4(),
        job_type='integration_test',
        payload={'message': 'Hello Integration Test', 'user_id': 'U123456'},
        scheduled_for=now - timedelta(minutes=5),  # Due 5 minutes ago
        status='pending',
        attempts=0,
        created_at=now,
    )

    # Schedule the job with deduplication
    success = deduplication.schedule_if_needed(
        job=job,
        job_table=job_table,
        logical_id=logical_id,
        date=date_str,
    )
    assert success is True  # First scheduling should succeed

    # 2. Verify job was stored
    due_jobs = job_table.get_due_jobs(now)
    assert len(due_jobs) == 1
    stored_job = due_jobs[0]
    assert stored_job.job_type == 'integration_test'
    assert stored_job.status == 'pending'

    # 3. Worker processes the job
    processed_count = worker.poll_and_process_jobs(now)
    assert processed_count == 1

    # 4. Verify job was handled by checking completion status
    # (We can't easily verify handler execution without shared instance)

    # 5. Verify job status updated to completed
    all_jobs = job_table.get_due_jobs(now + timedelta(hours=1))
    completed_job = None
    for j in all_jobs:
        if j.job_id == job.job_id and j.status == 'completed':
            completed_job = j
            break

    assert completed_job is not None
    assert completed_job.status == 'completed'
    assert completed_job.completed_at is not None
    assert completed_job.locked_by is None  # Lock should be released


@mock_aws
def test_complete_job_lifecycle_with_failure_and_retry() -> None:
    """Test complete job lifecycle with failure and retry scheduling."""

    class FailingHandler(BaseJobHandler):
        """Handler that always fails to test retry logic."""

        @classmethod
        def payload_model(cls) -> type[BaseModel]:
            return TestIntegrationPayload

        def handle(self, payload: BaseModel) -> None:
            raise RuntimeError('Handler always fails')

    # Setup
    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table, base_delay_seconds=1)  # Fast retry for testing
    worker.register_handler('failing_job', FailingHandler)

    now = datetime.now(UTC)

    # Schedule job
    job = ScheduledJob(
        job_id=uuid4(),
        job_type='failing_job',
        payload={'message': 'Retry Test', 'user_id': 'U789012'},
        scheduled_for=now - timedelta(minutes=1),
        status='pending',
        attempts=0,
        created_at=now,
    )

    job_table.put_job(job)

    # First processing - should fail and reschedule
    processed_count = worker.poll_and_process_jobs(now)
    assert processed_count == 1

    # Check that job was rescheduled with incremented attempts
    future_time = now + timedelta(minutes=2)
    rescheduled_jobs = job_table.get_due_jobs(future_time)

    retry_job = None
    for j in rescheduled_jobs:
        if j.job_id == job.job_id and j.status == 'pending' and j.attempts == 1:
            retry_job = j
            break

    assert retry_job is not None
    assert retry_job.attempts == 1
    assert retry_job.last_error is not None
    assert 'Handler always fails' in retry_job.last_error

    # Verify retry was scheduled for the future with backoff
    assert retry_job.scheduled_for > now


@mock_aws
def test_complete_job_lifecycle_with_deduplication() -> None:
    """Test that deduplication prevents duplicate job scheduling."""
    # Setup
    job_table = JobTable()
    job_table.create_table_for_testing()

    deduplication = DeduplicationIndex('CompanionMemory')
    deduplication.create_table_for_testing()

    now = datetime.now(UTC)
    logical_id = 'user-U123456-daily-summary'
    date_str = now.strftime('%Y-%m-%d')

    # Schedule first job
    job1 = ScheduledJob(
        job_id=uuid4(),
        job_type='test_job',
        payload={'message': 'First job', 'user_id': 'U123456'},
        scheduled_for=now,
        status='pending',
        attempts=0,
        created_at=now,
    )

    success1 = deduplication.schedule_if_needed(job1, job_table, logical_id, date_str)
    assert success1 is True

    # Try to schedule duplicate job
    job2 = ScheduledJob(
        job_id=uuid4(),
        job_type='test_job',
        payload={'message': 'Duplicate job', 'user_id': 'U123456'},
        scheduled_for=now,
        status='pending',
        attempts=0,
        created_at=now,
    )

    success2 = deduplication.schedule_if_needed(job2, job_table, logical_id, date_str)
    assert success2 is False  # Should be prevented by deduplication

    # Verify only one job exists
    due_jobs = job_table.get_due_jobs(now + timedelta(minutes=1))
    assert len(due_jobs) == 1
    assert due_jobs[0].job_id == job1.job_id  # Original job should remain


@mock_aws
def test_worker_handles_multiple_concurrent_jobs() -> None:
    """Test that worker can handle multiple jobs in a single poll."""
    # Setup
    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table, polling_limit=10)
    worker.register_handler('batch_job', IntegrationTestHandler)

    now = datetime.now(UTC)

    # Schedule multiple jobs
    job_ids = []
    for i in range(5):
        job = ScheduledJob(
            job_id=uuid4(),
            job_type='batch_job',
            payload={'message': f'Job {i}', 'user_id': f'U{i:06d}'},
            scheduled_for=now - timedelta(minutes=1),
            status='pending',
            attempts=0,
            created_at=now,
        )
        job_table.put_job(job)
        job_ids.append(job.job_id)

    # Process all jobs in one poll
    processed_count = worker.poll_and_process_jobs(now)
    assert processed_count == 5

    # Verify all jobs were processed (can't check handler state directly)

    # Verify all jobs are completed
    all_jobs = job_table.get_due_jobs(now + timedelta(hours=1))
    completed_jobs = [j for j in all_jobs if j.status == 'completed']
    assert len(completed_jobs) == 5

    # Verify all original job IDs are represented
    completed_job_ids = {j.job_id for j in completed_jobs}
    assert completed_job_ids == set(job_ids)


@mock_aws
def test_job_reaches_dead_letter_after_max_retries() -> None:
    """Test complete failure path where job becomes dead letter."""

    class AlwaysFailingHandler(BaseJobHandler):
        """Handler that always fails."""

        @classmethod
        def payload_model(cls) -> type[BaseModel]:
            return TestIntegrationPayload

        def handle(self, payload: BaseModel) -> None:
            raise RuntimeError('Always fails')

    # Setup with low max attempts for faster testing
    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table, max_attempts=2, base_delay_seconds=1)
    worker.register_handler('failing_job', AlwaysFailingHandler)

    now = datetime.now(UTC)

    # Schedule job that will fail
    job = ScheduledJob(
        job_id=uuid4(),
        job_type='failing_job',
        payload={'message': 'Will fail', 'user_id': 'U999999'},
        scheduled_for=now - timedelta(minutes=1),
        status='pending',
        attempts=0,
        created_at=now,
    )

    job_table.put_job(job)

    # First failure - should reschedule for retry
    processed_count = worker.poll_and_process_jobs(now)
    assert processed_count == 1

    # Find rescheduled job
    future_jobs = job_table.get_due_jobs(now + timedelta(minutes=5))
    retry_job = None
    for j in future_jobs:
        if j.job_id == job.job_id and j.status == 'pending' and j.attempts == 1:
            retry_job = j
            break

    assert retry_job is not None

    # Second failure - should go to dead letter
    retry_time = retry_job.scheduled_for + timedelta(seconds=1)
    processed_count = worker.poll_and_process_jobs(retry_time)
    assert processed_count == 1

    # Find dead letter job
    all_jobs = job_table.get_due_jobs(retry_time + timedelta(hours=1))
    dead_letter_job = None
    for j in all_jobs:
        if j.job_id == job.job_id and j.status == 'dead_letter':
            dead_letter_job = j
            break

    assert dead_letter_job is not None
    assert dead_letter_job.status == 'dead_letter'
    assert dead_letter_job.attempts == 2
    assert dead_letter_job.last_error is not None
    assert 'Always fails' in dead_letter_job.last_error
