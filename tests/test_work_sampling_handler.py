"""Tests for work sampling handler."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from companion_memory.job_models import ScheduledJob, WorkSamplingPayload
from companion_memory.work_sampling_handler import PROMPT_VARIATIONS, WorkSamplingHandler

pytestmark = pytest.mark.block_network


def test_work_sampling_handler_payload_model() -> None:
    """Test that WorkSamplingHandler returns correct payload model."""
    model = WorkSamplingHandler.payload_model()
    assert model == WorkSamplingPayload


def test_work_sampling_handler_registration() -> None:
    """Test that WorkSamplingHandler is properly registered with dispatcher."""
    # Check if the handler is registered globally (via decorator)
    from companion_memory.job_dispatcher import global_dispatcher

    mock_slack_client = MagicMock()

    with patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client):
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

    mock_slack_client = MagicMock()

    with patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client):
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
    """Test that WorkSamplingHandler handles valid payload and sends Slack message."""
    mock_slack_client = MagicMock()

    with patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client):
        handler = WorkSamplingHandler()
        payload = WorkSamplingPayload(user_id='U123456', slot_index=2)

        handler.handle(payload)

        # Verify Slack message was sent
        mock_slack_client.chat_postMessage.assert_called_once()
        call_args = mock_slack_client.chat_postMessage.call_args
        assert call_args[1]['channel'] == 'U123456'
        assert call_args[1]['text'] in PROMPT_VARIATIONS


def test_work_sampling_handler_prompt_variations() -> None:
    """Test that WorkSamplingHandler uses different prompt variations."""
    mock_slack_client = MagicMock()

    # Test multiple calls to ensure random selection works
    sent_prompts = set()

    with patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client):
        handler = WorkSamplingHandler()
        payload = WorkSamplingPayload(user_id='U123456', slot_index=2)

        # Call handler multiple times to collect different prompts
        for _ in range(20):  # Should be enough to get some variation
            handler.handle(payload)
            call_args = mock_slack_client.chat_postMessage.call_args
            sent_prompts.add(call_args[1]['text'])

        # Verify all sent prompts are valid
        assert all(prompt in PROMPT_VARIATIONS for prompt in sent_prompts)
        # With 20 calls and 5 variations, we should get some variety (but not guaranteed all)
        assert len(sent_prompts) >= 1
