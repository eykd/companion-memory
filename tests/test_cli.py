"""Tests for CLI functionality."""

from click.testing import CliRunner

from companion_memory.cli import cli


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
