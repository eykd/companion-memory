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
