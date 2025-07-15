"""Tests for retry policy and backoff logic."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from moto import mock_aws
from pydantic import BaseModel

from companion_memory.job_dispatcher import BaseJobHandler
from companion_memory.job_models import ScheduledJob
from companion_memory.job_table import JobTable
from companion_memory.job_worker import JobWorker
from companion_memory.retry_policy import RetryPolicy

pytestmark = pytest.mark.block_network


class TestPayload(BaseModel):
    """Test payload."""

    message: str


class FailingHandler(BaseJobHandler):
    """Handler that always fails for testing."""

    @classmethod
    def payload_model(cls) -> type[BaseModel]:
        """Return payload model."""
        return TestPayload

    def handle(self, payload: BaseModel) -> None:
        """Always fail."""
        raise RuntimeError('Simulated failure')


def test_backoff_applied_after_failure() -> None:
    """Test that exponential backoff is applied after job failures."""
    policy = RetryPolicy(base_delay_seconds=60, max_attempts=5)

    now = datetime.now(UTC)

    # Test exponential backoff calculation
    delay1 = policy.calculate_delay(1)  # First retry
    delay2 = policy.calculate_delay(2)  # Second retry
    delay3 = policy.calculate_delay(3)  # Third retry

    assert delay1 == timedelta(seconds=60)  # base * 2^(1-1) = 60 * 1
    assert delay2 == timedelta(seconds=120)  # base * 2^(2-1) = 60 * 2
    assert delay3 == timedelta(seconds=240)  # base * 2^(3-1) = 60 * 4

    # Test next run time calculation
    next_run1 = policy.calculate_next_run(now, 1)
    next_run2 = policy.calculate_next_run(now, 2)

    assert next_run1 == now + timedelta(seconds=60)
    assert next_run2 == now + timedelta(seconds=120)


def test_retry_policy_determines_dead_letter() -> None:
    """Test that retry policy correctly identifies when jobs should go to dead letter."""
    policy = RetryPolicy(max_attempts=3)

    assert policy.should_retry(1) is True  # First failure, should retry
    assert policy.should_retry(2) is True  # Second failure, should retry
    assert policy.should_retry(3) is False  # Third failure, max reached, dead letter
    assert policy.should_retry(4) is False  # Beyond max, definitely dead letter


@mock_aws
def test_worker_applies_backoff_on_failure() -> None:
    """Test that worker applies backoff when jobs fail."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table)
    worker.register_handler('failing_job', FailingHandler)

    now = datetime.now(UTC)
    job = ScheduledJob(
        job_id=uuid4(),
        job_type='failing_job',
        payload={'message': 'test'},
        scheduled_for=now - timedelta(minutes=1),  # Due now
        status='pending',
        attempts=0,
        created_at=now,
    )

    job_table.put_job(job)

    # Process the job (should fail and apply backoff)
    processed = worker.poll_and_process_jobs(now)
    assert processed == 1

    # Should create a rescheduled job for later execution
    future_time = now + timedelta(hours=2)
    future_jobs = job_table.get_due_jobs(future_time)

    # Find the rescheduled job (status pending, attempts 1)
    rescheduled_job = None
    for j in future_jobs:
        if j.job_id == job.job_id and j.status == 'pending' and j.attempts == 1:
            rescheduled_job = j
            break

    assert rescheduled_job is not None
    assert rescheduled_job.status == 'pending'
    assert rescheduled_job.attempts == 1
    assert rescheduled_job.scheduled_for > now  # Should be rescheduled for later
    assert rescheduled_job.last_error is not None  # Should have error recorded


@mock_aws
def test_job_becomes_dead_letter_after_max_attempts() -> None:
    """Test that jobs become dead letter after maximum retry attempts."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    # Use a worker with very low max attempts for testing
    worker = JobWorker(job_table, max_attempts=2)
    worker.register_handler('failing_job', FailingHandler)

    now = datetime.now(UTC)
    job = ScheduledJob(
        job_id=uuid4(),
        job_type='failing_job',
        payload={'message': 'test'},
        scheduled_for=now - timedelta(minutes=1),
        status='pending',
        attempts=1,  # Already failed once
        created_at=now,
    )

    job_table.put_job(job)

    # Process the job (should fail again and go to dead letter)
    processed = worker.poll_and_process_jobs(now)
    assert processed == 1

    # Find the job in any state
    all_jobs = job_table.get_due_jobs(now + timedelta(days=1))
    updated_job = None
    for j in all_jobs:
        if j.job_id == job.job_id:
            updated_job = j
            break

    assert updated_job is not None
    assert updated_job.status == 'dead_letter'
    assert updated_job.attempts == 2


@mock_aws
def test_retry_policy_configurable_parameters() -> None:
    """Test that retry policy parameters are configurable."""
    policy = RetryPolicy(base_delay_seconds=30, max_attempts=10)

    # Test custom base delay
    delay1 = policy.calculate_delay(1)
    assert delay1 == timedelta(seconds=30)

    # Test custom max attempts
    assert policy.should_retry(9) is True  # Under limit
    assert policy.should_retry(10) is False  # At limit
    assert policy.should_retry(11) is False  # Over limit

    # Test that delay calculation uses custom base
    delay2 = policy.calculate_delay(2)
    assert delay2 == timedelta(seconds=60)  # 30 * 2^(2-1) = 30 * 2

    # Test max_attempts property
    assert policy.max_attempts == 10
