"""Tests for work sampling handler."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from companion_memory.job_models import ScheduledJob, WorkSamplingPayload
from companion_memory.work_sampling_handler import WorkSamplingHandler


def test_work_sampling_handler_payload_model() -> None:
    """Test that WorkSamplingHandler returns correct payload model."""
    assert WorkSamplingHandler.payload_model() == WorkSamplingPayload


def test_work_sampling_handler_registration() -> None:
    """Test that WorkSamplingHandler is properly registered with dispatcher."""
    # Check if the handler is registered globally (via decorator)
    from companion_memory.job_dispatcher import global_dispatcher

    # Test registration by trying to dispatch a job (this tests the private attribute safely)
    job = ScheduledJob(
        job_id=UUID('12345678-1234-5678-9abc-123456789abc'),
        job_type='work_sampling_prompt',
        payload={'user_id': 'U123456', 'slot_index': 2},
        scheduled_for=datetime(2025, 7, 12, 14, 30, 0, tzinfo=UTC),
        status='pending',
        attempts=0,
        created_at=datetime(2025, 7, 12, 14, 0, 0, tzinfo=UTC),
    )

    # This should succeed if registration worked
    handler_instance = global_dispatcher.dispatch(job)
    assert isinstance(handler_instance, WorkSamplingHandler)


def test_work_sampling_handler_dispatch() -> None:
    """Test that dispatcher calls WorkSamplingHandler for work_sampling_prompt jobs."""
    from companion_memory.job_dispatcher import global_dispatcher

    # Create a work sampling job
    job = ScheduledJob(
        job_id=UUID('12345678-1234-5678-9abc-123456789abc'),
        job_type='work_sampling_prompt',
        payload={'user_id': 'U123456', 'slot_index': 2},
        scheduled_for=datetime(2025, 7, 12, 14, 30, 0, tzinfo=UTC),
        status='pending',
        attempts=0,
        created_at=datetime(2025, 7, 12, 14, 0, 0, tzinfo=UTC),
    )

    # Dispatch the job
    handler_instance = global_dispatcher.dispatch(job)

    # Verify the correct handler was used
    assert isinstance(handler_instance, WorkSamplingHandler)


def test_work_sampling_handler_validation_error() -> None:
    """Test that WorkSamplingHandler raises TypeError for wrong payload type."""
    handler = WorkSamplingHandler()

    # Create an invalid payload (different type)
    from companion_memory.job_models import ScheduledJob

    invalid_payload = ScheduledJob(
        job_id=UUID('12345678-1234-5678-9abc-123456789abc'),
        job_type='work_sampling_prompt',
        payload={'user_id': 'U123456', 'slot_index': 2},
        scheduled_for=datetime(2025, 7, 12, 14, 30, 0, tzinfo=UTC),
        status='pending',
        attempts=0,
        created_at=datetime(2025, 7, 12, 14, 0, 0, tzinfo=UTC),
    )

    with pytest.raises(TypeError, match='Expected WorkSamplingPayload'):
        handler.handle(invalid_payload)


def test_work_sampling_handler_with_valid_payload() -> None:
    """Test that WorkSamplingHandler handles valid payload without error."""
    handler = WorkSamplingHandler()
    payload = WorkSamplingPayload(user_id='U123456', slot_index=2)

    # This should not raise any errors (currently a no-op)
    handler.handle(payload)
