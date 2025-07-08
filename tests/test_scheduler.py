"""Tests for scheduler functionality."""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from companion_memory.scheduler import create_scheduler, send_sampling_prompt


def test_scheduler_runs_job_after_delay() -> None:
    """Test that scheduler can run a job after a short delay."""
    # Create a mock job function
    mock_job = MagicMock()

    # Create scheduler (non-blocking for testing)
    scheduler = create_scheduler(blocking=False)

    # Add a job to run after a short delay
    run_time = datetime.now(UTC) + timedelta(milliseconds=100)
    scheduler.add_job(func=mock_job, trigger='date', run_date=run_time)

    # Start scheduler
    scheduler.start()

    try:
        # Wait for job to execute
        time.sleep(0.2)

        # Verify job was called
        mock_job.assert_called_once()
    finally:
        # Always shut down scheduler
        scheduler.shutdown(wait=False)


def test_scheduler_sends_sampling_dm() -> None:
    """Test that scheduler can send a sampling DM via mocked Slack client."""
    from unittest.mock import MagicMock, patch

    # Mock Slack client
    mock_slack_client = MagicMock()

    # Create scheduler (non-blocking for testing)
    scheduler = create_scheduler(blocking=False)

    with patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client):
        # Add a job to send sampling DM
        run_time = datetime.now(UTC) + timedelta(milliseconds=100)
        scheduler.add_job(func=send_sampling_prompt, trigger='date', run_date=run_time, args=['U123456789'])

        # Start scheduler
        scheduler.start()

        try:
            # Wait for job to execute
            time.sleep(0.2)

            # Verify Slack client was called
            mock_slack_client.chat_postMessage.assert_called_once()
            call_args = mock_slack_client.chat_postMessage.call_args
            assert call_args[1]['channel'] == 'U123456789'
            assert 'What are you doing right now?' in call_args[1]['text']
        finally:
            # Always shut down scheduler
            scheduler.shutdown(wait=False)
