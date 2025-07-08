"""Tests for scheduler functionality."""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

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


def test_create_scheduler_blocking_mode() -> None:
    """Test that create_scheduler returns BlockingScheduler when blocking=True."""
    from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]

    scheduler = create_scheduler(blocking=True)
    assert isinstance(scheduler, BlockingScheduler)


def test_get_slack_client_missing_token() -> None:
    """Test that get_slack_client raises ValueError when SLACK_BOT_TOKEN is missing."""
    import os

    from companion_memory.scheduler import get_slack_client

    # Remove the token if it exists
    original_token = os.environ.get('SLACK_BOT_TOKEN')
    if 'SLACK_BOT_TOKEN' in os.environ:
        del os.environ['SLACK_BOT_TOKEN']

    try:
        with pytest.raises(ValueError, match='SLACK_BOT_TOKEN environment variable is required'):
            get_slack_client()
    finally:
        # Restore original token
        if original_token is not None:
            os.environ['SLACK_BOT_TOKEN'] = original_token


def test_get_slack_client_with_token() -> None:
    """Test that get_slack_client returns WebClient when token is present."""
    import os

    from slack_sdk import WebClient

    from companion_memory.scheduler import get_slack_client

    # Set a test token
    os.environ['SLACK_BOT_TOKEN'] = 'test-token'  # noqa: S105

    try:
        client = get_slack_client()
        assert isinstance(client, WebClient)
    finally:
        # Clean up
        if 'SLACK_BOT_TOKEN' in os.environ:
            del os.environ['SLACK_BOT_TOKEN']
