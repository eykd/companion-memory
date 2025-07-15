"""Tests for Sentry error reporting integration."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from moto import mock_aws
from pydantic import BaseModel

from companion_memory.job_dispatcher import BaseJobHandler
from companion_memory.job_models import ScheduledJob
from companion_memory.job_table import JobTable
from companion_memory.job_worker import JobWorker

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
        raise RuntimeError('Simulated failure for Sentry testing')


@mock_aws
@patch('sentry_sdk.capture_exception')
def test_job_failures_reported_to_sentry(mock_capture: Mock) -> None:
    """Test that job failures are automatically reported to Sentry."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table)
    worker.register_handler('failing_job', FailingHandler)

    now = datetime.now(UTC)
    job = ScheduledJob(
        job_id=uuid4(),
        job_type='failing_job',
        payload={'message': 'test'},
        scheduled_for=now - timedelta(minutes=1),
        status='pending',
        attempts=0,
        created_at=now,
    )

    job_table.put_job(job)

    # Process the job (should fail and report to Sentry)
    processed = worker.poll_and_process_jobs(now)
    assert processed == 1

    # Verify Sentry was called with the exception
    mock_capture.assert_called_once()
    captured_exception = mock_capture.call_args[0][0]
    assert isinstance(captured_exception, RuntimeError)
    assert str(captured_exception) == 'Simulated failure for Sentry testing'


@mock_aws
@patch('sentry_sdk.set_context')
@patch('sentry_sdk.capture_exception')
def test_sentry_context_includes_job_details(mock_capture: Mock, mock_set_context: Mock) -> None:
    """Test that Sentry context includes full job details."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table)
    worker.register_handler('failing_job', FailingHandler)

    now = datetime.now(UTC)
    job_id = uuid4()
    job = ScheduledJob(
        job_id=job_id,
        job_type='failing_job',
        payload={'message': 'test payload', 'user_id': 'U123456'},
        scheduled_for=now - timedelta(minutes=1),
        status='pending',
        attempts=0,
        created_at=now,
    )

    job_table.put_job(job)

    # Process the job (should fail and report to Sentry with context)
    processed = worker.poll_and_process_jobs(now)
    assert processed == 1

    # Verify Sentry context was set with job details
    mock_set_context.assert_called_once_with(
        'job',
        {
            'job_id': str(job_id),
            'job_type': 'failing_job',
            'attempts': 0,
            'payload': {'message': 'test payload', 'user_id': 'U123456'},
            'scheduled_for': job.scheduled_for.isoformat(),
        },
    )

    # Verify exception was captured
    mock_capture.assert_called_once()


@mock_aws
@patch('sentry_sdk.capture_exception')
def test_successful_jobs_not_reported_to_sentry(mock_capture: Mock) -> None:
    """Test that successful jobs are not reported to Sentry."""

    class SuccessHandler(BaseJobHandler):
        @classmethod
        def payload_model(cls) -> type[BaseModel]:
            return TestPayload

        def handle(self, payload: BaseModel) -> None:
            # Success - do nothing
            pass

    job_table = JobTable()
    job_table.create_table_for_testing()

    worker = JobWorker(job_table)
    worker.register_handler('success_job', SuccessHandler)

    now = datetime.now(UTC)
    job = ScheduledJob(
        job_id=uuid4(),
        job_type='success_job',
        payload={'message': 'test'},
        scheduled_for=now - timedelta(minutes=1),
        status='pending',
        attempts=0,
        created_at=now,
    )

    job_table.put_job(job)

    # Process the job (should succeed)
    processed = worker.poll_and_process_jobs(now)
    assert processed == 1

    # Verify no Sentry calls for successful jobs
    mock_capture.assert_not_called()
