"""Tests for log summarization functionality."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from companion_memory.summarizer import summarize_week


def test_summarize_week_generates_summary_with_llm() -> None:
    """Test that summarize_week() fetches logs and generates summary with LLM."""
    # Mock log store
    mock_log_store = MagicMock()

    # Mock logs for past week
    mock_logs = [
        {
            'user_id': 'U123456789',
            'timestamp': '2024-01-15T10:00:00+00:00',
            'text': 'Working on unit tests',
            'log_id': 'log-1',
        },
        {
            'user_id': 'U123456789',
            'timestamp': '2024-01-15T14:00:00+00:00',
            'text': 'Debugging API integration',
            'log_id': 'log-2',
        },
        {
            'user_id': 'U123456789',
            'timestamp': '2024-01-16T09:00:00+00:00',
            'text': 'Code review and planning',
            'log_id': 'log-3',
        },
    ]
    mock_log_store.fetch_logs.return_value = mock_logs

    # Mock LLM client
    mock_llm = MagicMock()
    mock_llm.complete.return_value = 'This week you focused on testing, debugging, and code review activities.'

    # Test summarize_week
    summary = summarize_week(user_id='U123456789', log_store=mock_log_store, llm=mock_llm)

    # Verify log store was called with correct date range (7 days ago)
    mock_log_store.fetch_logs.assert_called_once()
    call_args = mock_log_store.fetch_logs.call_args
    assert call_args[0][0] == 'U123456789'  # user_id
    # since should be approximately 7 days ago
    since_date = call_args[0][1]
    expected_since = datetime.now(UTC) - timedelta(days=7)
    assert abs((since_date - expected_since).total_seconds()) < 60  # Within 1 minute

    # Verify LLM was called with logs
    mock_llm.complete.assert_called_once()
    llm_call_args = mock_llm.complete.call_args[0][0]
    assert 'Working on unit tests' in llm_call_args
    assert 'Debugging API integration' in llm_call_args
    assert 'Code review and planning' in llm_call_args

    # Verify summary is returned
    assert summary == 'This week you focused on testing, debugging, and code review activities.'
