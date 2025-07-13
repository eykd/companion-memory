"""Tests for job data models and utilities."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from companion_memory.job_models import ScheduledJob, WorkSamplingPayload, make_job_sk, parse_job_sk


def test_job_model_serializes_correctly() -> None:
    """Test that ScheduledJob model serializes and validates correctly."""
    job_id = UUID('12345678-1234-5678-9abc-123456789abc')
    scheduled_for = datetime(2025, 7, 11, 12, 0, 0, tzinfo=UTC)

    job = ScheduledJob(
        job_id=job_id,
        job_type='daily_summary',
        payload={'user_id': 'U123456'},
        scheduled_for=scheduled_for,
        status='pending',
        attempts=0,
        created_at=scheduled_for,
    )

    # Test serialization
    data = job.model_dump()
    assert data['job_id'] == job_id  # Pydantic keeps UUID as UUID object
    assert data['job_type'] == 'daily_summary'
    assert data['payload'] == {'user_id': 'U123456'}
    assert data['status'] == 'pending'
    assert data['attempts'] == 0

    # Test deserialization
    restored = ScheduledJob.model_validate(data)
    assert restored.job_id == job_id
    assert restored.job_type == 'daily_summary'
    assert restored.payload == {'user_id': 'U123456'}
    assert restored.status == 'pending'


def test_make_job_sk() -> None:
    """Test that make_job_sk creates the correct sort key format."""
    job_id = UUID('12345678-1234-5678-9abc-123456789abc')
    scheduled_for = datetime(2025, 7, 11, 12, 0, 0, tzinfo=UTC)

    sk = make_job_sk(scheduled_for, job_id)

    expected = 'scheduled#2025-07-11T12:00:00+00:00#12345678-1234-5678-9abc-123456789abc'
    assert sk == expected


def test_parse_job_sk() -> None:
    """Test that parse_job_sk correctly extracts timestamp and UUID."""
    sk = 'scheduled#2025-07-11T12:00:00+00:00#12345678-1234-5678-9abc-123456789abc'

    timestamp, job_id = parse_job_sk(sk)

    assert timestamp == datetime(2025, 7, 11, 12, 0, 0, tzinfo=UTC)
    assert job_id == UUID('12345678-1234-5678-9abc-123456789abc')


def test_parse_job_sk_invalid_format() -> None:
    """Test that parse_job_sk raises error for invalid format."""
    with pytest.raises(ValueError, match='Invalid sort key format'):
        parse_job_sk('invalid#format')

    with pytest.raises(ValueError, match='Invalid sort key format'):
        parse_job_sk('scheduled#invalid-timestamp#uuid')


def test_work_sampling_payload_validation() -> None:
    """Test that WorkSamplingPayload validates correctly."""
    # Valid payload
    payload = WorkSamplingPayload(user_id='U123456', slot_index=2)
    assert payload.user_id == 'U123456'
    assert payload.slot_index == 2

    # Test serialization
    data = payload.model_dump()
    assert data['user_id'] == 'U123456'
    assert data['slot_index'] == 2

    # Test deserialization
    restored = WorkSamplingPayload.model_validate(data)
    assert restored.user_id == 'U123456'
    assert restored.slot_index == 2

    # Test invalid data (should raise validation error)
    with pytest.raises(ValueError, match='slot_index'):
        WorkSamplingPayload.model_validate({'user_id': 'U123456'})  # Missing slot_index
