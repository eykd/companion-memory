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
    updated_job = job_table.get_job_by_id(job_id, now)
    assert updated_job is not None
    assert updated_job.status == 'in_progress'


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


@mock_aws
def test_get_due_jobs_filters_out_failed_jobs() -> None:
    """Test that get_due_jobs only returns pending jobs, not failed ones."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    now = datetime.now(UTC)

    # Create pending job
    pending_job = ScheduledJob(
        job_id=uuid4(),
        job_type='heartbeat_event',
        payload={'heartbeat_uuid': 'test-pending'},
        scheduled_for=now - timedelta(minutes=10),
        status='pending',
        attempts=0,
        created_at=now,
    )

    # Create failed job (older, should be returned first without filter)
    failed_job = ScheduledJob(
        job_id=uuid4(),
        job_type='heartbeat_event',
        payload={'heartbeat_uuid': 'test-failed'},
        scheduled_for=now - timedelta(hours=1),
        status='failed',
        attempts=3,
        created_at=now - timedelta(hours=1),
    )

    # Create completed job
    completed_job = ScheduledJob(
        job_id=uuid4(),
        job_type='heartbeat_event',
        payload={'heartbeat_uuid': 'test-completed'},
        scheduled_for=now - timedelta(minutes=30),
        status='completed',
        attempts=1,
        created_at=now - timedelta(minutes=30),
    )

    # Store all jobs
    job_table.put_job(pending_job)
    job_table.put_job(failed_job)
    job_table.put_job(completed_job)

    # Should only return the pending job
    due_jobs = job_table.get_due_jobs(now)
    assert len(due_jobs) == 1
    assert due_jobs[0].job_id == pending_job.job_id
    assert due_jobs[0].status == 'pending'


@mock_aws
def test_cleanup_old_jobs() -> None:
    """Test that cleanup_old_jobs removes old completed, failed, and dead_letter jobs."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    now = datetime.now(UTC)
    old_date = now - timedelta(days=10)  # Older than 7 days
    recent_date = now - timedelta(days=3)  # Newer than 7 days

    # Create old jobs that should be deleted
    old_failed_job = ScheduledJob(
        job_id=uuid4(),
        job_type='heartbeat_event',
        payload={'heartbeat_uuid': 'old-failed'},
        scheduled_for=old_date,
        status='failed',
        attempts=3,
        created_at=old_date,
    )

    old_completed_job = ScheduledJob(
        job_id=uuid4(),
        job_type='daily_summary',
        payload={'user_id': 'U123'},
        scheduled_for=old_date,
        status='completed',
        attempts=1,
        created_at=old_date,
    )

    old_dead_letter_job = ScheduledJob(
        job_id=uuid4(),
        job_type='work_sampling',
        payload={'user_id': 'U456'},
        scheduled_for=old_date,
        status='dead_letter',
        attempts=5,
        created_at=old_date,
    )

    # Create recent jobs that should NOT be deleted
    recent_failed_job = ScheduledJob(
        job_id=uuid4(),
        job_type='heartbeat_event',
        payload={'heartbeat_uuid': 'recent-failed'},
        scheduled_for=recent_date,
        status='failed',
        attempts=2,
        created_at=recent_date,
    )

    recent_pending_job = ScheduledJob(
        job_id=uuid4(),
        job_type='daily_summary',
        payload={'user_id': 'U789'},
        scheduled_for=now + timedelta(hours=1),
        status='pending',
        attempts=0,
        created_at=now,
    )

    old_pending_job = ScheduledJob(
        job_id=uuid4(),
        job_type='work_sampling',
        payload={'user_id': 'U999'},
        scheduled_for=old_date,
        status='pending',  # Should NOT be deleted even if old
        attempts=0,
        created_at=old_date,
    )

    # Store all jobs
    jobs_to_store = [
        old_failed_job,
        old_completed_job,
        old_dead_letter_job,
        recent_failed_job,
        recent_pending_job,
        old_pending_job,
    ]

    for job in jobs_to_store:
        job_table.put_job(job)

    # Run cleanup
    deleted_count = job_table.cleanup_old_jobs(older_than_days=7)

    # Should delete 3 old jobs with cleanup statuses
    assert deleted_count == 3

    # Verify the correct jobs were deleted and preserved by trying to retrieve each individually
    # These should be deleted (get_job_by_id should return None)
    assert job_table.get_job_by_id(old_failed_job.job_id, old_failed_job.scheduled_for) is None
    assert job_table.get_job_by_id(old_completed_job.job_id, old_completed_job.scheduled_for) is None
    assert job_table.get_job_by_id(old_dead_letter_job.job_id, old_dead_letter_job.scheduled_for) is None

    # These should remain (get_job_by_id should return the job)
    assert job_table.get_job_by_id(recent_failed_job.job_id, recent_failed_job.scheduled_for) is not None
    assert job_table.get_job_by_id(recent_pending_job.job_id, recent_pending_job.scheduled_for) is not None
    assert job_table.get_job_by_id(old_pending_job.job_id, old_pending_job.scheduled_for) is not None


@mock_aws
def test_cleanup_old_jobs_with_custom_days() -> None:
    """Test cleanup_old_jobs with custom retention period."""
    job_table = JobTable()
    job_table.create_table_for_testing()

    now = datetime.now(UTC)
    old_date = now - timedelta(days=5)  # 5 days old

    old_failed_job = ScheduledJob(
        job_id=uuid4(),
        job_type='heartbeat_event',
        payload={'heartbeat_uuid': 'old-failed'},
        scheduled_for=old_date,
        status='failed',
        attempts=3,
        created_at=old_date,
    )

    job_table.put_job(old_failed_job)

    # Should not delete with 7-day retention
    deleted_count = job_table.cleanup_old_jobs(older_than_days=7)
    assert deleted_count == 0

    # Should delete with 3-day retention
    deleted_count = job_table.cleanup_old_jobs(older_than_days=3)
    assert deleted_count == 1
