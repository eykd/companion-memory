"""Tests for log summarization functionality."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from companion_memory.summarizer import send_summary_message, summarize_day, summarize_week


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


def test_summarize_day_generates_summary_with_llm() -> None:
    """Test that summarize_day() fetches logs and generates summary with LLM."""
    # Mock log store
    mock_log_store = MagicMock()

    # Mock logs for past day
    mock_logs = [
        {
            'user_id': 'U123456789',
            'timestamp': '2024-01-15T10:00:00+00:00',
            'text': 'Morning standup',
            'log_id': 'log-1',
        },
        {
            'user_id': 'U123456789',
            'timestamp': '2024-01-15T14:00:00+00:00',
            'text': 'Code review session',
            'log_id': 'log-2',
        },
    ]
    mock_log_store.fetch_logs.return_value = mock_logs

    # Mock LLM client
    mock_llm = MagicMock()
    mock_llm.complete.return_value = 'Today you participated in standup and code reviews.'

    # Test summarize_day
    summary = summarize_day(user_id='U123456789', log_store=mock_log_store, llm=mock_llm)

    # Verify log store was called with correct date range (1 day ago)
    mock_log_store.fetch_logs.assert_called_once()
    call_args = mock_log_store.fetch_logs.call_args
    assert call_args[0][0] == 'U123456789'  # user_id
    # since should be approximately 1 day ago
    since_date = call_args[0][1]
    expected_since = datetime.now(UTC) - timedelta(days=1)
    assert abs((since_date - expected_since).total_seconds()) < 60  # Within 1 minute

    # Verify LLM was called with logs
    mock_llm.complete.assert_called_once()
    llm_call_args = mock_llm.complete.call_args[0][0]
    assert 'Morning standup' in llm_call_args
    assert 'Code review session' in llm_call_args
    assert 'past day' in llm_call_args  # Should use "past day" in prompt

    # Verify summary is returned
    assert summary == 'Today you participated in standup and code reviews.'


def test_send_summary_message_combines_summaries_and_sends_slack() -> None:
    """Test that send_summary_message() generates both summaries and sends to Slack."""
    from unittest.mock import patch

    # Mock log store
    mock_log_store = MagicMock()

    # Mock LLM client
    mock_llm = MagicMock()
    mock_llm.complete.side_effect = [
        'Weekly summary: Focused on testing and development.',
        'Daily summary: Attended meetings and completed code reviews.',
    ]

    # Mock Slack client
    mock_slack_client = MagicMock()

    # Test send_summary_message
    with patch('companion_memory.summarizer.get_slack_client', return_value=mock_slack_client):
        send_summary_message(user_id='U123456789', log_store=mock_log_store, llm=mock_llm)

    # Verify LLM was called twice (for week and day summaries)
    assert mock_llm.complete.call_count == 2

    # Verify Slack client was called to send message
    mock_slack_client.chat_postMessage.assert_called_once()
    call_args = mock_slack_client.chat_postMessage.call_args

    # Check message was sent to correct user
    assert call_args[1]['channel'] == 'U123456789'

    # Check message contains both summaries
    message_text = call_args[1]['text']
    assert 'Weekly summary: Focused on testing and development.' in message_text
    assert 'Daily summary: Attended meetings and completed code reviews.' in message_text


def test_summarize_yesterday_with_timezone() -> None:
    """Test that summarize_yesterday() fetches logs for yesterday in user's timezone."""
    from unittest.mock import patch

    # Mock log store
    mock_log_store = MagicMock()

    # Mock logs for yesterday
    mock_logs = [
        {
            'user_id': 'U123456789',
            'timestamp': '2024-01-15T10:00:00+00:00',
            'text': 'Working on timezone handling',
            'log_id': 'log-1',
        },
        {
            'user_id': 'U123456789',
            'timestamp': '2024-01-15T14:00:00+00:00',
            'text': 'Testing date calculations',
            'log_id': 'log-2',
        },
    ]
    mock_log_store.fetch_logs.return_value = mock_logs

    # Mock LLM client
    mock_llm = MagicMock()
    mock_llm.complete.return_value = 'Yesterday you focused on timezone handling and date calculations.'

    # Mock Slack client for timezone discovery
    mock_slack_client = MagicMock()
    mock_slack_client.users_info.return_value = {'ok': True, 'user': {'tz': 'America/New_York', 'tz_offset': -18000}}

    # Import the function we're testing
    from companion_memory.summarizer import summarize_yesterday

    # Test summarize_yesterday with timezone
    with patch('companion_memory.summarizer._get_user_timezone') as mock_get_tz:
        import zoneinfo

        mock_get_tz.return_value = zoneinfo.ZoneInfo('America/New_York')
        summary = summarize_yesterday(user_id='U123456789', log_store=mock_log_store, llm=mock_llm)

    # Verify timezone function was called
    mock_get_tz.assert_called_once_with('U123456789')

    # Verify log store was called to fetch logs
    mock_log_store.fetch_logs.assert_called_once()

    # Verify LLM was called with appropriate prompt
    mock_llm.complete.assert_called_once()

    # Verify return value
    assert summary == 'Yesterday you focused on timezone handling and date calculations.'


def test_get_user_timezone_success() -> None:
    """Test that _get_user_timezone returns correct timezone for valid user."""
    from unittest.mock import MagicMock, patch

    # Mock Slack client
    mock_slack_client = MagicMock()
    mock_slack_client.users_info.return_value = {'ok': True, 'user': {'tz': 'America/New_York'}}

    # Import the helper function
    from companion_memory.summarizer import _get_user_timezone

    with patch('companion_memory.summarizer.get_slack_client', return_value=mock_slack_client):
        timezone_result = _get_user_timezone('U123456789')

    # Verify timezone is correct
    import zoneinfo

    assert isinstance(timezone_result, zoneinfo.ZoneInfo)
    assert str(timezone_result) == 'America/New_York'

    # Verify Slack client was called
    mock_slack_client.users_info.assert_called_once_with(user='U123456789')


def test_get_user_timezone_fallback_to_utc() -> None:
    """Test that _get_user_timezone falls back to UTC when Slack API fails."""
    from unittest.mock import MagicMock, patch

    # Mock Slack client that fails
    mock_slack_client = MagicMock()
    mock_slack_client.users_info.return_value = {'ok': False}

    # Import the helper function
    from companion_memory.summarizer import _get_user_timezone

    with patch('companion_memory.summarizer.get_slack_client', return_value=mock_slack_client):
        timezone_result = _get_user_timezone('U123456789')

    # Verify falls back to UTC
    from datetime import UTC

    assert timezone_result is UTC


def test_get_user_timezone_invalid_timezone_fallback() -> None:
    """Test that _get_user_timezone falls back to UTC for invalid timezone."""
    from unittest.mock import MagicMock, patch

    # Mock Slack client with invalid timezone
    mock_slack_client = MagicMock()
    mock_slack_client.users_info.return_value = {'ok': True, 'user': {'tz': 'Invalid/Timezone'}}

    # Import the helper function
    from companion_memory.summarizer import _get_user_timezone

    with patch('companion_memory.summarizer.get_slack_client', return_value=mock_slack_client):
        timezone_result = _get_user_timezone('U123456789')

    # Verify falls back to UTC
    from datetime import UTC

    assert timezone_result is UTC


def test_get_user_timezone_utc_string_returns_utc() -> None:
    """Test that _get_user_timezone returns UTC for 'UTC' string."""
    from unittest.mock import MagicMock, patch

    # Mock Slack client with UTC timezone
    mock_slack_client = MagicMock()
    mock_slack_client.users_info.return_value = {'ok': True, 'user': {'tz': 'UTC'}}

    # Import the helper function
    from companion_memory.summarizer import _get_user_timezone

    with patch('companion_memory.summarizer.get_slack_client', return_value=mock_slack_client):
        timezone_result = _get_user_timezone('U123456789')

    # Verify returns UTC
    from datetime import UTC

    assert timezone_result is UTC


def test_get_user_timezone_exception_fallback() -> None:
    """Test that _get_user_timezone falls back to UTC when exception occurs."""
    from unittest.mock import MagicMock, patch

    # Mock Slack client that raises exception
    mock_slack_client = MagicMock()
    mock_slack_client.users_info.side_effect = Exception('API Error')

    # Import the helper function
    from companion_memory.summarizer import _get_user_timezone

    with patch('companion_memory.summarizer.get_slack_client', return_value=mock_slack_client):
        timezone_result = _get_user_timezone('U123456789')

    # Verify falls back to UTC
    from datetime import UTC

    assert timezone_result is UTC


def test_summarize_today_with_timezone() -> None:
    """Test that summarize_today() fetches logs for today in user's timezone."""
    from unittest.mock import patch

    # Mock log store
    mock_log_store = MagicMock()

    # Mock logs for today
    mock_logs = [
        {
            'user_id': 'U123456789',
            'timestamp': '2024-01-15T10:00:00+00:00',
            'text': 'Working on implementing new features',
            'log_id': 'log-1',
        },
        {
            'user_id': 'U123456789',
            'timestamp': '2024-01-15T14:00:00+00:00',
            'text': 'Testing timezone functionality',
            'log_id': 'log-2',
        },
    ]
    mock_log_store.fetch_logs.return_value = mock_logs

    # Mock LLM client
    mock_llm = MagicMock()
    mock_llm.complete.return_value = 'Today you are working on implementing new features and testing.'

    # Import the function we're testing
    from companion_memory.summarizer import summarize_today

    # Test summarize_today with timezone
    with patch('companion_memory.summarizer._get_user_timezone') as mock_get_tz:
        import zoneinfo

        mock_get_tz.return_value = zoneinfo.ZoneInfo('America/New_York')
        summary = summarize_today(user_id='U123456789', log_store=mock_log_store, llm=mock_llm)

    # Verify timezone function was called
    mock_get_tz.assert_called_once_with('U123456789')

    # Verify log store was called to fetch logs
    mock_log_store.fetch_logs.assert_called_once()

    # Verify LLM was called with appropriate prompt
    mock_llm.complete.assert_called_once()
    llm_call_args = mock_llm.complete.call_args[0][0]
    assert 'Working on implementing new features' in llm_call_args
    assert 'Testing timezone functionality' in llm_call_args
    assert 'today' in llm_call_args  # Should use "today" in prompt

    # Verify return value
    assert summary == 'Today you are working on implementing new features and testing.'
