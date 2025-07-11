"""Tests for job deduplication index logic."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from moto import mock_aws

from companion_memory.deduplication import DeduplicationIndex
from companion_memory.job_models import ScheduledJob, make_job_sk


@mock_aws
def test_deduplication_prevents_duplicate_scheduling() -> None:
    """Test that deduplication prevents scheduling identical logical jobs."""
    # Setup
    dedup_index = DeduplicationIndex()
    dedup_index.create_table_for_testing()

    logical_id = 'summary#U123456'
    date = '2025-07-11'
    job_id = uuid4()
    scheduled_for = datetime.now(UTC)
    job_sk = make_job_sk(scheduled_for, job_id)

    # First attempt should succeed
    result = dedup_index.try_reserve(logical_id, date, 'job', job_sk)
    assert result is True

    # Second attempt should fail (already reserved)
    result = dedup_index.try_reserve(logical_id, date, 'job', job_sk)
    assert result is False


@mock_aws
def test_deduplication_allows_different_dates() -> None:
    """Test that deduplication allows same logical job on different dates."""
    dedup_index = DeduplicationIndex()
    dedup_index.create_table_for_testing()

    logical_id = 'summary#U123456'
    job_id = uuid4()
    scheduled_for = datetime.now(UTC)
    job_sk = make_job_sk(scheduled_for, job_id)

    # Reserve for first date
    result1 = dedup_index.try_reserve(logical_id, '2025-07-11', 'job', job_sk)
    assert result1 is True

    # Reserve for second date should also succeed
    result2 = dedup_index.try_reserve(logical_id, '2025-07-12', 'job', job_sk)
    assert result2 is True


@mock_aws
def test_deduplication_allows_different_logical_ids() -> None:
    """Test that deduplication allows different logical IDs on same date."""
    dedup_index = DeduplicationIndex()
    dedup_index.create_table_for_testing()

    date = '2025-07-11'
    job_id = uuid4()
    scheduled_for = datetime.now(UTC)
    job_sk = make_job_sk(scheduled_for, job_id)

    # Reserve for first logical ID
    result1 = dedup_index.try_reserve('summary#U123456', date, 'job', job_sk)
    assert result1 is True

    # Reserve for second logical ID should also succeed
    result2 = dedup_index.try_reserve('summary#U789012', date, 'job', job_sk)
    assert result2 is True


@mock_aws
def test_schedule_if_needed_with_deduplication() -> None:
    """Test high-level schedule_if_needed function."""
    from companion_memory.job_table import JobTable

    dedup_index = DeduplicationIndex()
    job_table = JobTable()

    # Setup both tables
    dedup_index.create_table_for_testing()
    job_table.create_table_for_testing()

    job = ScheduledJob(
        job_id=uuid4(),
        job_type='daily_summary',
        payload={'user_id': 'U123456'},
        scheduled_for=datetime(2025, 7, 11, 9, 0, 0, tzinfo=UTC),
        status='pending',
        attempts=0,
        created_at=datetime.now(UTC),
    )

    # First scheduling should succeed
    result = dedup_index.schedule_if_needed(job, job_table, 'summary#U123456', '2025-07-11')
    assert result is True

    # Second scheduling should be skipped due to deduplication
    duplicate_job = ScheduledJob(
        job_id=uuid4(),
        job_type='daily_summary',
        payload={'user_id': 'U123456'},
        scheduled_for=datetime(2025, 7, 11, 9, 0, 0, tzinfo=UTC),
        status='pending',
        attempts=0,
        created_at=datetime.now(UTC),
    )

    result = dedup_index.schedule_if_needed(duplicate_job, job_table, 'summary#U123456', '2025-07-11')
    assert result is False


@mock_aws
def test_deduplication_reraises_non_conditional_errors() -> None:
    """Test that deduplication re-raises non-conditional check exceptions."""
    from unittest.mock import Mock

    from botocore.exceptions import ClientError

    deduplication = DeduplicationIndex('CompanionMemory')
    deduplication.create_table_for_testing()

    # Mock the table.put_item to raise a non-conditional error
    original_put_item = deduplication._table.put_item  # noqa: SLF001

    # Create a non-conditional check error
    error_response = {
        'Error': {
            'Code': 'ValidationException',  # Not ConditionalCheckFailedException
            'Message': 'Some other error',
        }
    }

    deduplication._table.put_item = Mock(side_effect=ClientError(error_response, 'PutItem'))  # noqa: SLF001

    try:
        # Should re-raise the non-conditional error (covers line 73)
        with pytest.raises(ClientError) as exc_info:
            deduplication.try_reserve('test-id', '2025-07-11', 'job', 'scheduled#2025-07-11T09:00:00')

        # Verify it's the same error we injected
        assert exc_info.value.response['Error']['Code'] == 'ValidationException'

    finally:
        # Restore original method
        deduplication._table.put_item = original_put_item  # noqa: SLF001
