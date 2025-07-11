"""Tests for job handler dispatcher system."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import BaseModel

from companion_memory.job_dispatcher import BaseJobHandler, JobDispatcher, register_handler
from companion_memory.job_models import ScheduledJob


class DailySummaryPayload(BaseModel):
    """Payload for daily summary jobs."""

    user_id: str
    date: str


class UserSyncPayload(BaseModel):
    """Payload for user sync jobs."""

    user_id: str
    force_update: bool = False


class TestDailySummaryHandler(BaseJobHandler):
    """Test handler for daily summary jobs."""

    @classmethod
    def payload_model(cls) -> type[BaseModel]:
        """Return the payload model for this handler."""
        return DailySummaryPayload

    def handle(self, payload: BaseModel) -> None:
        """Handle the job."""
        # For testing, just store the payload
        self.handled_payload = payload


class TestUserSyncHandler(BaseJobHandler):
    """Test handler for user sync jobs."""

    @classmethod
    def payload_model(cls) -> type[BaseModel]:
        """Return the payload model for this handler."""
        return UserSyncPayload

    def handle(self, payload: BaseModel) -> None:
        """Handle the job."""
        # For testing, just store the payload
        self.handled_payload = payload


def test_dispatch_calls_correct_handler() -> None:
    """Test that dispatcher calls the correct handler for each job type."""
    dispatcher = JobDispatcher()

    # Register handlers
    dispatcher.register('daily_summary', TestDailySummaryHandler)
    dispatcher.register('user_sync', TestUserSyncHandler)

    # Create a daily summary job
    summary_job = ScheduledJob(
        job_id=UUID('12345678-1234-5678-9abc-123456789abc'),
        job_type='daily_summary',
        payload={'user_id': 'U123456', 'date': '2025-07-11'},
        scheduled_for=datetime(2025, 7, 11, 9, 0, 0, tzinfo=UTC),
        status='pending',
        attempts=0,
        created_at=datetime(2025, 7, 11, 8, 0, 0, tzinfo=UTC),
    )

    # Dispatch the job
    handler_instance = dispatcher.dispatch(summary_job)

    # Verify the correct handler was used
    assert isinstance(handler_instance, TestDailySummaryHandler)
    assert hasattr(handler_instance, 'handled_payload')

    # Verify payload was validated and passed correctly
    payload = handler_instance.handled_payload
    assert isinstance(payload, DailySummaryPayload)
    assert payload.user_id == 'U123456'
    assert payload.date == '2025-07-11'


def test_dispatcher_validates_payload() -> None:
    """Test that dispatcher validates payload using handler's model."""
    dispatcher = JobDispatcher()
    dispatcher.register('daily_summary', TestDailySummaryHandler)

    # Create job with invalid payload (missing required field)
    invalid_job = ScheduledJob(
        job_id=UUID('12345678-1234-5678-9abc-123456789abc'),
        job_type='daily_summary',
        payload={'user_id': 'U123456'},  # Missing 'date' field
        scheduled_for=datetime(2025, 7, 11, 9, 0, 0, tzinfo=UTC),
        status='pending',
        attempts=0,
        created_at=datetime(2025, 7, 11, 8, 0, 0, tzinfo=UTC),
    )

    # Dispatch should raise validation error
    with pytest.raises(ValueError, match='Payload validation failed for job type'):
        dispatcher.dispatch(invalid_job)


def test_dispatcher_handles_unknown_job_type() -> None:
    """Test that dispatcher raises error for unknown job types."""
    dispatcher = JobDispatcher()

    unknown_job = ScheduledJob(
        job_id=UUID('12345678-1234-5678-9abc-123456789abc'),
        job_type='unknown_type',
        payload={'some': 'data'},
        scheduled_for=datetime(2025, 7, 11, 9, 0, 0, tzinfo=UTC),
        status='pending',
        attempts=0,
        created_at=datetime(2025, 7, 11, 8, 0, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match='No handler registered for job type'):
        dispatcher.dispatch(unknown_job)


def test_register_handler_decorator() -> None:
    """Test the register_handler decorator functionality."""

    @register_handler('test_job')
    class TestDecoratedHandler(BaseJobHandler):
        @classmethod
        def payload_model(cls) -> type[BaseModel]:
            return DailySummaryPayload

        def handle(self, payload: BaseModel) -> None:
            self.handled_payload = payload

    # The global dispatcher should now have this handler registered
    from companion_memory.job_dispatcher import global_dispatcher

    test_job = ScheduledJob(
        job_id=UUID('12345678-1234-5678-9abc-123456789abc'),
        job_type='test_job',
        payload={'user_id': 'U123456', 'date': '2025-07-11'},
        scheduled_for=datetime(2025, 7, 11, 9, 0, 0, tzinfo=UTC),
        status='pending',
        attempts=0,
        created_at=datetime(2025, 7, 11, 8, 0, 0, tzinfo=UTC),
    )

    handler_instance = global_dispatcher.dispatch(test_job)
    assert isinstance(handler_instance, TestDecoratedHandler)
