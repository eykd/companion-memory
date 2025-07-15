"""Tests for job worker CLI command."""

import pytest
from click.testing import CliRunner

from companion_memory.cli import cli

pytestmark = pytest.mark.block_network


def test_cli_job_worker_command_exists() -> None:
    """Test that job-worker command exists in CLI."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'job-worker' in result.output


def test_cli_job_worker_help_text() -> None:
    """Test that job-worker command has proper help text."""
    runner = CliRunner()
    result = runner.invoke(cli, ['job-worker', '--help'])
    assert result.exit_code == 0
    assert 'Run the job worker to process scheduled jobs' in result.output
    assert 'polling-limit' in result.output
    assert 'lock-timeout' in result.output
    assert 'max-attempts' in result.output
