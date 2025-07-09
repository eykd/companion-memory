"""Tests for command implementations."""

import os
from unittest.mock import MagicMock, patch


def test_test_slack_connection_success_with_default_user() -> None:
    """Test that test_slack_connection succeeds with default user from environment."""
    from companion_memory.commands import test_slack_connection

    mock_client = MagicMock()
    mock_client.auth_test.return_value = {'ok': True}
    mock_client.chat_postMessage.return_value = {'ok': True}

    with (
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_client),
        patch.dict(os.environ, {'SLACK_USER_ID': 'U123456', 'SLACK_BOT_TOKEN': 'test-token'}),
    ):
        result = test_slack_connection()

    assert result is True
    mock_client.auth_test.assert_called_once()
    mock_client.chat_postMessage.assert_called_once_with(
        channel='U123456', text='✅ Test message from companion-memory CLI - Slack connection working!'
    )


def test_test_slack_connection_success_with_specified_user() -> None:
    """Test that test_slack_connection succeeds with specified user ID."""
    from companion_memory.commands import test_slack_connection

    mock_client = MagicMock()
    mock_client.auth_test.return_value = {'ok': True}
    mock_client.chat_postMessage.return_value = {'ok': True}

    with (
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_client),
        patch.dict(os.environ, {'SLACK_BOT_TOKEN': 'test-token'}),
    ):
        result = test_slack_connection('U789012')

    assert result is True
    mock_client.auth_test.assert_called_once()
    mock_client.chat_postMessage.assert_called_once_with(
        channel='U789012', text='✅ Test message from companion-memory CLI - Slack connection working!'
    )


def test_test_slack_connection_fails_auth_test() -> None:
    """Test that test_slack_connection fails when auth test fails."""
    from companion_memory.commands import test_slack_connection

    mock_client = MagicMock()
    mock_client.auth_test.return_value = {'ok': False}

    with (
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_client),
        patch.dict(os.environ, {'SLACK_USER_ID': 'U123456', 'SLACK_BOT_TOKEN': 'test-token'}),
    ):
        result = test_slack_connection()

    assert result is False
    mock_client.auth_test.assert_called_once()
    mock_client.chat_postMessage.assert_not_called()


def test_test_slack_connection_fails_message_send() -> None:
    """Test that test_slack_connection fails when message sending fails."""
    from companion_memory.commands import test_slack_connection

    mock_client = MagicMock()
    mock_client.auth_test.return_value = {'ok': True}
    mock_client.chat_postMessage.return_value = {'ok': False}

    with (
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_client),
        patch.dict(os.environ, {'SLACK_USER_ID': 'U123456', 'SLACK_BOT_TOKEN': 'test-token'}),
    ):
        result = test_slack_connection()

    assert result is False
    mock_client.auth_test.assert_called_once()
    mock_client.chat_postMessage.assert_called_once()


def test_test_slack_connection_handles_auth_exception() -> None:
    """Test that test_slack_connection handles exceptions during auth test."""
    from companion_memory.commands import test_slack_connection

    mock_client = MagicMock()
    mock_client.auth_test.side_effect = Exception('Auth failed')

    with (
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_client),
        patch.dict(os.environ, {'SLACK_USER_ID': 'U123456', 'SLACK_BOT_TOKEN': 'test-token'}),
    ):
        result = test_slack_connection()

    assert result is False
    mock_client.auth_test.assert_called_once()
    mock_client.chat_postMessage.assert_not_called()


def test_test_slack_connection_handles_message_exception() -> None:
    """Test that test_slack_connection handles exceptions during message sending."""
    from companion_memory.commands import test_slack_connection

    mock_client = MagicMock()
    mock_client.auth_test.return_value = {'ok': True}
    mock_client.chat_postMessage.side_effect = Exception('Message failed')

    with (
        patch('companion_memory.scheduler.get_slack_client', return_value=mock_client),
        patch.dict(os.environ, {'SLACK_USER_ID': 'U123456', 'SLACK_BOT_TOKEN': 'test-token'}),
    ):
        result = test_slack_connection()

    assert result is False
    mock_client.auth_test.assert_called_once()
    mock_client.chat_postMessage.assert_called_once()


def test_test_slack_connection_fails_without_user_id() -> None:
    """Test that test_slack_connection fails when no user ID is provided."""
    from companion_memory.commands import test_slack_connection

    with patch.dict(os.environ, {}, clear=True):
        result = test_slack_connection()

    assert result is False


def test_test_slack_connection_fails_without_bot_token() -> None:
    """Test that test_slack_connection fails when SLACK_BOT_TOKEN is not set."""
    from companion_memory.commands import test_slack_connection

    with patch.dict(os.environ, {'SLACK_USER_ID': 'U123456'}, clear=True):
        result = test_slack_connection()

    assert result is False


def test_test_slack_connection_handles_slack_client_creation_error() -> None:
    """Test that test_slack_connection handles errors during Slack client creation."""
    from companion_memory.commands import test_slack_connection

    with (
        patch('companion_memory.scheduler.get_slack_client', side_effect=Exception('Client creation failed')),
        patch.dict(os.environ, {'SLACK_USER_ID': 'U123456', 'SLACK_BOT_TOKEN': 'test-token'}),
    ):
        result = test_slack_connection()

    assert result is False
