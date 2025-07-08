"""Tests for CLI functionality."""

from click.testing import CliRunner

from companion_memory.cli import cli


def test_cli_help_text() -> None:
    """Test that CLI prints help text when invoked with --help."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])

    assert result.exit_code == 0
    assert 'companion-scheduler' in result.output
    assert 'run' in result.output
    assert 'web' in result.output


def test_cli_run_command_exists() -> None:
    """Test that CLI has a run command."""
    runner = CliRunner()
    result = runner.invoke(cli, ['run', '--help'])

    assert result.exit_code == 0
    assert 'run' in result.output


def test_cli_run_command_execution() -> None:
    """Test that CLI run command executes successfully."""
    runner = CliRunner()
    result = runner.invoke(cli, ['run'])

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
