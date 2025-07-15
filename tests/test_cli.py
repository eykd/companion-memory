"""Tests for CLI functionality."""

import pytest
from click.testing import CliRunner

from companion_memory.cli import cli

pytestmark = pytest.mark.block_network


def test_cli_help_text() -> None:
    """Test that CLI prints help text when invoked with --help."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])

    assert result.exit_code == 0
    assert 'Comem' in result.output
    assert 'scheduler' in result.output
    assert 'web' in result.output


def test_cli_scheduler_command_exists() -> None:
    """Test that CLI has a scheduler command."""
    runner = CliRunner()
    result = runner.invoke(cli, ['scheduler', '--help'])

    assert result.exit_code == 0
    assert 'scheduler' in result.output


def test_cli_scheduler_command_execution() -> None:
    """Test that CLI scheduler command executes successfully."""
    runner = CliRunner()
    result = runner.invoke(cli, ['scheduler'])

    assert result.exit_code == 0
    assert 'Starting companion scheduler...' in result.output


def test_cli_web_command_exists() -> None:
    """Test that CLI has a web command."""
    runner = CliRunner()
    result = runner.invoke(cli, ['web', '--help'])

    assert result.exit_code == 0
    assert 'web' in result.output


def test_cli_web_command_execution() -> None:
    """Test that CLI web command executes successfully."""
    from unittest.mock import patch

    runner = CliRunner()
    with patch('companion_memory.app.create_app') as mock_create_app:
        mock_app = mock_create_app.return_value
        result = runner.invoke(cli, ['web'])

    assert result.exit_code == 0
    mock_create_app.assert_called_once()
    mock_app.run.assert_called_once_with(host='127.0.0.1', port=5000, debug=True)


def test_cli_web_command_with_options() -> None:
    """Test that CLI web command accepts custom options."""
    from unittest.mock import patch

    runner = CliRunner()
    with patch('companion_memory.app.create_app') as mock_create_app:
        mock_app = mock_create_app.return_value
        result = runner.invoke(cli, ['web', '--host', '0.0.0.0', '--port', '8080', '--no-debug'])  # noqa: S104

    assert result.exit_code == 0
    mock_create_app.assert_called_once()
    mock_app.run.assert_called_once_with(host='0.0.0.0', port=8080, debug=False)  # noqa: S104


def test_cli_slack_test_command_exists() -> None:
    """Test that CLI has a slack-test command."""
    runner = CliRunner()
    result = runner.invoke(cli, ['slack-test', '--help'])

    assert result.exit_code == 0
    assert 'slack-test' in result.output
    assert 'Test Slack connection' in result.output


def test_cli_slack_test_command_success() -> None:
    """Test that CLI slack-test command succeeds with valid connection."""
    from unittest.mock import patch

    runner = CliRunner()
    with patch('companion_memory.cli.test_slack_connection') as mock_test:
        mock_test.return_value = True
        result = runner.invoke(cli, ['slack-test'])

    assert result.exit_code == 0
    assert 'Testing Slack connection...' in result.output
    assert '✅ Slack connection successful!' in result.output
    assert 'Test message sent to Slack user.' in result.output
    mock_test.assert_called_once()


def test_cli_slack_test_command_failure() -> None:
    """Test that CLI slack-test command fails with invalid connection."""
    from unittest.mock import patch

    runner = CliRunner()
    with patch('companion_memory.cli.test_slack_connection') as mock_test:
        mock_test.return_value = False
        result = runner.invoke(cli, ['slack-test'])

    assert result.exit_code == 1
    assert 'Testing Slack connection...' in result.output
    assert '❌ Slack connection failed!' in result.output
    assert 'Check the logs for detailed error information.' in result.output
    mock_test.assert_called_once()


def test_cli_slack_test_command_with_user_id() -> None:
    """Test that CLI slack-test command accepts user ID option."""
    from unittest.mock import patch

    runner = CliRunner()
    with patch('companion_memory.cli.test_slack_connection') as mock_test:
        mock_test.return_value = True
        result = runner.invoke(cli, ['slack-test', '--user-id', 'U123456'])

    assert result.exit_code == 0
    assert 'Testing Slack connection...' in result.output
    assert '✅ Slack connection successful!' in result.output
    mock_test.assert_called_once_with('U123456')
