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


def test_send_slack_message_sends_text() -> None:
    """Test that send_slack_message_job sends message to Slack."""
    from companion_memory.summary_jobs import send_slack_message_job

    # Create test payload
    payload = {'slack_user_id': 'U123456789', 'message': 'Test summary message', 'job_uuid': 'test-uuid-123'}

    # Mock get_slack_client
    with patch('companion_memory.summary_jobs.get_slack_client') as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock successful response
        mock_response = MagicMock()
        mock_response.get.return_value = True  # success
        mock_client.chat_postMessage.return_value = mock_response

        # Call the function we're testing
        send_slack_message_job(payload)

        # Assert Slack client was called correctly
        mock_client.chat_postMessage.assert_called_once_with(channel='U123456789', text='Test summary message')


def test_summary_today_endpoint_enqueues_job() -> None:
    """Test that /slack/today endpoint enqueues a job and returns 204."""
    from companion_memory.app import create_app

    # Create test app with mocked dependencies
    with patch('companion_memory.app.get_log_store') as mock_get_log_store:
        mock_log_store = MagicMock()
        mock_get_log_store.return_value = mock_log_store

        with patch('companion_memory.app.schedule_summary_job') as mock_schedule_job:
            app = create_app(enable_scheduler=False)
            app.config['TESTING'] = True

            with (
                app.test_client() as client,
                patch('companion_memory.app.validate_slack_signature', return_value=True),
            ):
                # Make request to endpoint
                response = client.post('/slack/today', data={'text': '', 'user_id': 'U123456789'})

                # Assert response is 204 No Content
                assert response.status_code == 204
                assert response.data == b''

                # Assert job was scheduled
                mock_schedule_job.assert_called_once_with('U123456789', 'today')
