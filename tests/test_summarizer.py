"""Tests for log summarization functionality."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from companion_memory.summarizer import send_summary_message, summarize_day, summarize_week

pytestmark = pytest.mark.block_network


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
        'Yesterday summary: Attended meetings and completed code reviews.',
    ]

    # Mock Slack client
    mock_slack_client = MagicMock()

    # Test send_summary_message
    with patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client):
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
    assert 'Yesterday summary: Attended meetings and completed code reviews.' in message_text


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

    # Mock DynamoDB user settings store
    mock_settings_store = MagicMock()
    mock_settings_store.get_user_settings.return_value = {'timezone': 'America/New_York'}

    # Import the helper function
    from companion_memory.summarizer import _get_user_timezone

    with patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_settings_store):
        timezone_result = _get_user_timezone('U123456789')

    # Verify timezone is correct
    import zoneinfo

    assert isinstance(timezone_result, zoneinfo.ZoneInfo)
    assert str(timezone_result) == 'America/New_York'

    # Verify settings store was called
    mock_settings_store.get_user_settings.assert_called_once_with('U123456789')


def test_get_user_timezone_fallback_to_utc() -> None:
    """Test that _get_user_timezone falls back to UTC when no timezone is set."""
    from unittest.mock import MagicMock, patch

    # Mock user settings store with no timezone
    mock_settings_store = MagicMock()
    mock_settings_store.get_user_settings.return_value = {}

    # Import the helper function
    from companion_memory.summarizer import _get_user_timezone

    with patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_settings_store):
        timezone_result = _get_user_timezone('U123456789')

    # Verify falls back to UTC
    from datetime import UTC

    assert timezone_result is UTC


def test_get_user_timezone_invalid_timezone_fallback() -> None:
    """Test that _get_user_timezone falls back to UTC for invalid timezone."""
    from unittest.mock import MagicMock, patch

    # Mock user settings store with invalid timezone
    mock_settings_store = MagicMock()
    mock_settings_store.get_user_settings.return_value = {'timezone': 'Invalid/Timezone'}

    # Import the helper function
    from companion_memory.summarizer import _get_user_timezone

    with patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_settings_store):
        timezone_result = _get_user_timezone('U123456789')

    # Verify falls back to UTC
    from datetime import UTC

    assert timezone_result is UTC


def test_get_user_timezone_utc_string_returns_utc() -> None:
    """Test that _get_user_timezone returns UTC for 'UTC' string."""
    from unittest.mock import MagicMock, patch

    # Mock user settings store with UTC timezone
    mock_settings_store = MagicMock()
    mock_settings_store.get_user_settings.return_value = {'timezone': 'UTC'}

    # Import the helper function
    from companion_memory.summarizer import _get_user_timezone

    with patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_settings_store):
        timezone_result = _get_user_timezone('U123456789')

    # Verify returns UTC
    from datetime import UTC

    assert timezone_result is UTC


def test_get_user_timezone_exception_fallback() -> None:
    """Test that _get_user_timezone falls back to UTC when exception occurs."""
    from unittest.mock import MagicMock, patch

    # Mock user settings store that raises exception
    mock_settings_store = MagicMock()
    mock_settings_store.get_user_settings.side_effect = Exception('DynamoDB Error')

    # Import the helper function
    from companion_memory.summarizer import _get_user_timezone

    with patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_settings_store):
        timezone_result = _get_user_timezone('U123456789')

    # Verify falls back to UTC
    from datetime import UTC

    assert timezone_result is UTC


def test_get_user_timezone_syncs_from_slack_when_no_record() -> None:
    """Test that _get_user_timezone syncs from Slack when no user record exists."""
    from unittest.mock import MagicMock, patch

    # Mock user settings store with no timezone
    mock_settings_store = MagicMock()
    mock_settings_store.get_user_settings.return_value = {}

    # Mock successful Slack sync
    mock_sync_function = MagicMock(return_value='America/New_York')

    # Import the helper function
    from companion_memory.summarizer import _get_user_timezone

    with (
        patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_settings_store),
        patch('companion_memory.user_sync.sync_user_timezone_from_slack', mock_sync_function),
    ):
        timezone_result = _get_user_timezone('U123456789')

    # Verify timezone is correct
    import zoneinfo

    assert isinstance(timezone_result, zoneinfo.ZoneInfo)
    assert str(timezone_result) == 'America/New_York'

    # Verify sync function was called
    mock_sync_function.assert_called_once_with('U123456789')


def test_get_user_timezone_fallback_when_slack_sync_fails() -> None:
    """Test that _get_user_timezone falls back to UTC when Slack sync fails."""
    from unittest.mock import MagicMock, patch

    # Mock user settings store with no timezone
    mock_settings_store = MagicMock()
    mock_settings_store.get_user_settings.return_value = {}

    # Mock failed Slack sync
    mock_sync_function = MagicMock(return_value=None)

    # Import the helper function
    from companion_memory.summarizer import _get_user_timezone

    with (
        patch('companion_memory.user_settings.DynamoUserSettingsStore', return_value=mock_settings_store),
        patch('companion_memory.user_sync.sync_user_timezone_from_slack', mock_sync_function),
    ):
        timezone_result = _get_user_timezone('U123456789')

    # Verify falls back to UTC
    from datetime import UTC

    assert timezone_result is UTC

    # Verify sync function was called
    mock_sync_function.assert_called_once_with('U123456789')


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


def test_format_log_entries_with_no_timezone_defaults_to_utc() -> None:
    """Test that _format_log_entries defaults to UTC when no timezone is provided."""
    from companion_memory.summarizer import _format_log_entries

    # Mock logs with UTC timestamps
    mock_logs = [
        {
            'timestamp': '2024-01-15T10:00:00+00:00',
            'text': 'Working on tests',
        },
        {
            'timestamp': '2024-01-15T14:00:00+00:00',
            'text': 'Debugging code',
        },
    ]

    # Call _format_log_entries without timezone (should default to UTC)
    result = _format_log_entries(mock_logs)

    # Verify timestamps are formatted in UTC
    assert '2024-01-15 10:00:00: Working on tests' in result
    assert '2024-01-15 14:00:00: Debugging code' in result


def test_send_daily_summary_to_users_no_users_configured() -> None:
    """Test send_daily_summary_to_users when no users are configured."""
    from unittest.mock import MagicMock, patch

    from companion_memory.summarizer import send_daily_summary_to_users

    mock_log_store = MagicMock()
    mock_llm = MagicMock()

    with patch.dict('os.environ', {}, clear=True):
        send_daily_summary_to_users(mock_log_store, mock_llm)

    # Should not call any functions
    mock_llm.complete.assert_not_called()


def test_send_daily_summary_to_users_with_users() -> None:
    """Test send_daily_summary_to_users with configured users."""
    from unittest.mock import MagicMock, patch

    from companion_memory.summarizer import send_daily_summary_to_users

    mock_log_store = MagicMock()
    mock_llm = MagicMock()
    mock_slack_client = MagicMock()

    with (
        patch.dict('os.environ', {'DAILY_SUMMARY_USERS': 'U123,U456,U789'}),
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client),
        patch('companion_memory.summarizer._get_user_timezone', return_value=UTC),
    ):
        send_daily_summary_to_users(mock_log_store, mock_llm)

    # Should send messages to all 3 users
    assert mock_slack_client.chat_postMessage.call_count == 3


def test_check_and_send_daily_summaries_no_users() -> None:
    """Test check_and_send_daily_summaries when no users are configured."""
    from unittest.mock import MagicMock, patch

    from companion_memory.summarizer import check_and_send_daily_summaries

    mock_log_store = MagicMock()
    mock_llm = MagicMock()

    with patch.dict('os.environ', {}, clear=True):
        check_and_send_daily_summaries(mock_log_store, mock_llm)

    # Should not call any functions
    mock_llm.complete.assert_not_called()


def test_check_and_send_daily_summaries_not_7am() -> None:
    """Test check_and_send_daily_summaries when it's not 7am for any user."""
    from datetime import UTC, datetime
    from unittest.mock import MagicMock, patch

    from companion_memory.summarizer import check_and_send_daily_summaries

    mock_log_store = MagicMock()
    mock_llm = MagicMock()
    mock_slack_client = MagicMock()

    # Mock current time as 3am UTC
    mock_utc_time = datetime(2024, 1, 15, 3, 0, 0, tzinfo=UTC)

    with (
        patch.dict('os.environ', {'DAILY_SUMMARY_USERS': 'U123'}),
        patch('companion_memory.summarizer.datetime') as mock_datetime,
        patch('companion_memory.summarizer._get_user_timezone', return_value=UTC),
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client),
    ):
        mock_datetime.now.return_value = mock_utc_time
        check_and_send_daily_summaries(mock_log_store, mock_llm)

    # Should not send any messages since it's 3am, not 7am
    mock_slack_client.chat_postMessage.assert_not_called()


def test_check_and_send_daily_summaries_is_7am() -> None:
    """Test check_and_send_daily_summaries when it's 7am for a user."""
    from datetime import UTC, datetime
    from unittest.mock import MagicMock, patch

    from companion_memory.summarizer import check_and_send_daily_summaries

    mock_log_store = MagicMock()
    mock_llm = MagicMock()
    mock_slack_client = MagicMock()

    # Mock current time as 7am UTC
    mock_utc_time = datetime(2024, 1, 15, 7, 0, 0, tzinfo=UTC)

    with (
        patch.dict('os.environ', {'DAILY_SUMMARY_USERS': 'U123'}),
        patch('companion_memory.summarizer.datetime') as mock_datetime,
        patch('companion_memory.summarizer._get_user_timezone', return_value=UTC),
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client),
    ):
        mock_datetime.now.return_value = mock_utc_time
        check_and_send_daily_summaries(mock_log_store, mock_llm)

    # Should send message since it's 7am
    mock_slack_client.chat_postMessage.assert_called_once()


def test_send_daily_summary_to_users_empty_users_list() -> None:
    """Test send_daily_summary_to_users with empty users list after parsing."""
    from unittest.mock import MagicMock, patch

    from companion_memory.summarizer import send_daily_summary_to_users

    mock_log_store = MagicMock()
    mock_llm = MagicMock()

    # Set environment with only commas and whitespace (no valid user IDs)
    with patch.dict('os.environ', {'DAILY_SUMMARY_USERS': ' , , '}):
        send_daily_summary_to_users(mock_log_store, mock_llm)

    # Should not call any functions since no valid user IDs
    mock_llm.complete.assert_not_called()


def test_send_daily_summary_to_users_exception_during_send() -> None:
    """Test send_daily_summary_to_users when send_summary_message raises exception."""
    from unittest.mock import MagicMock, patch

    from companion_memory.summarizer import send_daily_summary_to_users

    mock_log_store = MagicMock()
    mock_llm = MagicMock()
    mock_slack_client = MagicMock()

    with (
        patch.dict('os.environ', {'DAILY_SUMMARY_USERS': 'U123'}),
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client),
        patch('companion_memory.summarizer._get_user_timezone', return_value=UTC),
        patch('companion_memory.summarizer.send_summary_message', side_effect=Exception('Send failed')),
    ):
        # Should not raise exception - errors are caught and logged
        send_daily_summary_to_users(mock_log_store, mock_llm)


def test_check_and_send_daily_summaries_empty_users_list() -> None:
    """Test check_and_send_daily_summaries with empty users list after parsing."""
    from unittest.mock import MagicMock, patch

    from companion_memory.summarizer import check_and_send_daily_summaries

    mock_log_store = MagicMock()
    mock_llm = MagicMock()

    # Set environment with only commas and whitespace (no valid user IDs)
    with patch.dict('os.environ', {'DAILY_SUMMARY_USERS': ' , , '}):
        check_and_send_daily_summaries(mock_log_store, mock_llm)

    # Should not call any functions since no valid user IDs
    mock_llm.complete.assert_not_called()


def test_check_and_send_daily_summaries_timezone_exception() -> None:
    """Test check_and_send_daily_summaries when timezone check raises exception."""
    from datetime import UTC, datetime
    from unittest.mock import MagicMock, patch

    from companion_memory.summarizer import check_and_send_daily_summaries

    mock_log_store = MagicMock()
    mock_llm = MagicMock()
    mock_slack_client = MagicMock()
    mock_utc_time = datetime(2024, 1, 15, 7, 0, 0, tzinfo=UTC)

    with (
        patch.dict('os.environ', {'DAILY_SUMMARY_USERS': 'U123'}),
        patch('companion_memory.summarizer.datetime') as mock_datetime,
        patch('companion_memory.summarizer._get_user_timezone', side_effect=Exception('Timezone error')),
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client),
    ):
        mock_datetime.now.return_value = mock_utc_time
        # Should not raise exception - errors are caught and logged
        check_and_send_daily_summaries(mock_log_store, mock_llm)

    # Should not send any messages due to timezone exception
    mock_slack_client.chat_postMessage.assert_not_called()


def test_check_and_send_daily_summaries_send_exception() -> None:
    """Test check_and_send_daily_summaries when sending summary raises exception."""
    from datetime import UTC, datetime
    from unittest.mock import MagicMock, patch

    from companion_memory.summarizer import check_and_send_daily_summaries

    mock_log_store = MagicMock()
    mock_llm = MagicMock()
    mock_slack_client = MagicMock()
    mock_utc_time = datetime(2024, 1, 15, 7, 0, 0, tzinfo=UTC)

    with (
        patch.dict('os.environ', {'DAILY_SUMMARY_USERS': 'U123'}),
        patch('companion_memory.summarizer.datetime') as mock_datetime,
        patch('companion_memory.summarizer._get_user_timezone', return_value=UTC),
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_slack_client),
        patch('companion_memory.summarizer.send_summary_message', side_effect=Exception('Send failed')),
    ):
        mock_datetime.now.return_value = mock_utc_time
        # Should not raise exception - errors are caught and logged
        check_and_send_daily_summaries(mock_log_store, mock_llm)
