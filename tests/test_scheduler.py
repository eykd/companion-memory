"""Tests for scheduler functionality."""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from companion_memory.scheduler import create_scheduler


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
