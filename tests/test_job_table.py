"""Tests for job table DynamoDB client."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from moto import mock_aws

from companion_memory.job_models import ScheduledJob
from companion_memory.job_table import JobTable

pytestmark = pytest.mark.block_network


@mock_aws
def test_job_persistence_round_trip() -> None:
    """Test that jobs can be written to and read from DynamoDB."""
    # Setup
    job_table = JobTable()
    job_table.create_table_for_testing()  # Create table for testing

    job_id = uuid4()
    now = datetime.now(UTC)

    job = ScheduledJob(
        job_id=job_id,
        job_type='daily_summary',
        payload={'user_id': 'U123456'},
        scheduled_for=now,
        status='pending',
        attempts=0,
        created_at=now,
    )

    # Test put_job
    job_table.put_job(job)

    # Test get_due_jobs
    due_jobs = job_table.get_due_jobs(now + timedelta(minutes=1))

    assert len(due_jobs) == 1
    retrieved_job = due_jobs[0]
    assert retrieved_job.job_id == job_id
    assert retrieved_job.job_type == 'daily_summary'
    assert retrieved_job.payload == {'user_id': 'U123456'}
    assert retrieved_job.status == 'pending'
    assert retrieved_job.attempts == 0


@mock_aws
def test_update_job_status() -> None:
    """Test that job status can be updated."""
    # Setup
    job_table = JobTable()
    job_table.create_table_for_testing()

    job_id = uuid4()
    now = datetime.now(UTC)

    job = ScheduledJob(
        job_id=job_id,
        job_type='daily_summary',
        payload={'user_id': 'U123456'},
        scheduled_for=now,
        status='pending',
        attempts=0,
        created_at=now,
    )

    job_table.put_job(job)

    # Test update_job_status
    job_table.update_job_status(job_id, now, 'in_progress')

    # Verify update
    due_jobs = job_table.get_due_jobs(now + timedelta(minutes=1))
    assert len(due_jobs) == 1
    assert due_jobs[0].status == 'in_progress'


@mock_aws
def test_get_due_jobs_filters_by_time() -> None:
    """Test that get_due_jobs only returns jobs scheduled before the given time."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    now = datetime.now(UTC)
    past_job = ScheduledJob(
        job_id=uuid4(),
        job_type='daily_summary',
        payload={'user_id': 'U123456'},
        scheduled_for=now - timedelta(hours=1),
        status='pending',
        attempts=0,
        created_at=now,
    )

    future_job = ScheduledJob(
        job_id=uuid4(),
        job_type='user_sync',
        payload={'user_id': 'U789012'},
        scheduled_for=now + timedelta(hours=1),
        status='pending',
        attempts=0,
        created_at=now,
    )

    job_table.put_job(past_job)
    job_table.put_job(future_job)

    # Should only return the past job
    due_jobs = job_table.get_due_jobs(now)
    assert len(due_jobs) == 1
    assert due_jobs[0].job_id == past_job.job_id
