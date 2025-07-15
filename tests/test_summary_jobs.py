"""Tests for summary job handlers."""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.block_network


def test_generate_summary_enqueues_send_job() -> None:
    """Test that generate_summary_job enqueues a send_slack_message job."""
    from companion_memory.summary_jobs import generate_summary_job

    # Mock dependencies
    mock_job_table = MagicMock()
    mock_log_store = MagicMock()
    mock_llm = MagicMock()

    # Mock summary generation
    expected_summary = 'Daily summary for user123'
    with patch('companion_memory.summary_jobs.summarize_today', return_value=expected_summary):
        # Call the function we're testing
        generate_summary_job(
            user_id='user123', summary_range='today', job_table=mock_job_table, log_store=mock_log_store, llm=mock_llm
        )

    # Assert that a send_slack_message job was enqueued
    mock_job_table.put_job.assert_called_once()

    # Get the job that was enqueued
    enqueued_job = mock_job_table.put_job.call_args[0][0]

    # Verify it's a send_slack_message job
    assert enqueued_job.job_type == 'send_slack_message'
    assert enqueued_job.payload['slack_user_id'] == 'user123'
    assert enqueued_job.payload['message'] == expected_summary
    assert 'job_uuid' in enqueued_job.payload
