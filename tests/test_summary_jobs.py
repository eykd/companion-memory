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


def test_get_summary_invalid_range_raises_error() -> None:
    """Test that get_summary raises ValueError for invalid range."""
    from companion_memory.summary_jobs import get_summary

    # Mock dependencies
    mock_log_store = MagicMock()
    mock_llm = MagicMock()

    # Test with invalid range
    with pytest.raises(ValueError, match='Unknown range: invalid'):
        get_summary('user123', 'invalid', mock_log_store, mock_llm)


def test_get_summary_yesterday_range() -> None:
    """Test that get_summary calls summarize_yesterday for yesterday range."""
    from companion_memory.summary_jobs import get_summary

    # Mock dependencies
    mock_log_store = MagicMock()
    mock_llm = MagicMock()

    # Mock summary generation
    expected_summary = 'Yesterday summary for user123'
    with patch('companion_memory.summary_jobs.summarize_yesterday', return_value=expected_summary) as mock_summarize:
        # Call the function we're testing
        result = get_summary('user123', 'yesterday', mock_log_store, mock_llm)

        # Assert correct function was called
        mock_summarize.assert_called_once_with(user_id='user123', log_store=mock_log_store, llm=mock_llm)
        assert result == expected_summary


def test_get_summary_lastweek_range() -> None:
    """Test that get_summary calls summarize_week for lastweek range."""
    from companion_memory.summary_jobs import get_summary

    # Mock dependencies
    mock_log_store = MagicMock()
    mock_llm = MagicMock()

    # Mock summary generation
    expected_summary = 'Week summary for user123'
    with patch('companion_memory.summary_jobs.summarize_week', return_value=expected_summary) as mock_summarize:
        # Call the function we're testing
        result = get_summary('user123', 'lastweek', mock_log_store, mock_llm)

        # Assert correct function was called
        mock_summarize.assert_called_once_with(user_id='user123', log_store=mock_log_store, llm=mock_llm)
        assert result == expected_summary


def test_generate_summary_handler_payload_model() -> None:
    """Test that GenerateSummaryHandler returns correct payload model."""
    from companion_memory.summary_jobs import GenerateSummaryHandler, GenerateSummaryPayload

    # Test payload model method
    assert GenerateSummaryHandler.payload_model() == GenerateSummaryPayload


def test_generate_summary_handler_with_valid_payload() -> None:
    """Test GenerateSummaryHandler with valid payload."""
    from companion_memory.summary_jobs import GenerateSummaryHandler, GenerateSummaryPayload

    # Create valid payload
    payload = GenerateSummaryPayload(user_id='user123', summary_range='today')

    # Mock dependencies
    with (
        patch('companion_memory.app.get_log_store') as mock_get_log_store,
        patch('companion_memory.job_table.JobTable') as mock_job_table_class,
        patch('companion_memory.llm_client.LLMLClient') as mock_llm_class,
        patch('companion_memory.summary_jobs.generate_summary_job') as mock_generate,
    ):
        mock_log_store = MagicMock()
        mock_get_log_store.return_value = mock_log_store
        mock_job_table = MagicMock()
        mock_job_table_class.return_value = mock_job_table
        mock_llm = MagicMock()
        mock_llm_class.return_value = mock_llm

        # Create and use handler
        handler = GenerateSummaryHandler()
        handler.handle(payload)

        # Verify dependencies were created correctly
        mock_get_log_store.assert_called_once()
        mock_job_table_class.assert_called_once()
        mock_llm_class.assert_called_once()

        # Verify business logic was called
        mock_generate.assert_called_once_with(
            user_id='user123',
            summary_range='today',
            job_table=mock_job_table,
            log_store=mock_log_store,
            llm=mock_llm,
        )


def test_generate_summary_handler_with_invalid_payload() -> None:
    """Test GenerateSummaryHandler with invalid payload type."""
    from companion_memory.summary_jobs import GenerateSummaryHandler

    # Create invalid payload
    invalid_payload = MagicMock()

    # Test with invalid payload type
    handler = GenerateSummaryHandler()
    with pytest.raises(TypeError, match='Expected GenerateSummaryPayload'):
        handler.handle(invalid_payload)


def test_send_slack_message_handler_payload_model() -> None:
    """Test that SendSlackMessageHandler returns correct payload model."""
    from companion_memory.summary_jobs import SendSlackMessageHandler, SendSlackMessagePayload

    # Test payload model method
    assert SendSlackMessageHandler.payload_model() == SendSlackMessagePayload


def test_send_slack_message_handler_with_valid_payload() -> None:
    """Test SendSlackMessageHandler with valid payload."""
    from companion_memory.summary_jobs import SendSlackMessageHandler, SendSlackMessagePayload

    # Create valid payload
    payload = SendSlackMessagePayload(slack_user_id='U123456789', message='Test message', job_uuid='test-uuid-123')

    # Mock the business logic function
    with patch('companion_memory.summary_jobs.send_slack_message_job') as mock_send:
        # Create and use handler
        handler = SendSlackMessageHandler()
        handler.handle(payload)

        # Verify business logic was called with correct parameters
        mock_send.assert_called_once_with({
            'slack_user_id': 'U123456789',
            'message': 'Test message',
            'job_uuid': 'test-uuid-123',
        })


def test_send_slack_message_handler_with_invalid_payload() -> None:
    """Test SendSlackMessageHandler with invalid payload type."""
    from companion_memory.summary_jobs import SendSlackMessageHandler

    # Create invalid payload
    invalid_payload = MagicMock()

    # Test with invalid payload type
    handler = SendSlackMessageHandler()
    with pytest.raises(TypeError, match='Expected SendSlackMessagePayload'):
        handler.handle(invalid_payload)
