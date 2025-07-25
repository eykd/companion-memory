"""CLI interface for companion-scheduler."""

import click

from companion_memory.commands import run_job_worker, run_scheduler, run_web_server, test_slack_connection


@click.group()
def cli() -> None:
    """Comem - Work activity tracking and summarization."""


@cli.command()
def scheduler() -> None:
    """Run the companion scheduler."""
    run_scheduler()


@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind the server to')
@click.option('--port', default=5000, help='Port to bind the server to')
@click.option('--debug/--no-debug', default=True, help='Enable debug mode')
def web(host: str, port: int, debug: bool) -> None:  # noqa: FBT001
    """Run the web server."""
    run_web_server(host=host, port=port, debug=debug)


@cli.command('slack-test')
@click.option('--user-id', help='Slack user ID to send test message to')
def slack_test(user_id: str | None) -> None:
    """Test Slack connection using the same mechanisms as the scheduler.

    This command tests the complete Slack integration pipeline:
    - Validates environment variables (SLACK_BOT_TOKEN, SLACK_USER_ID)
    - Tests authentication with Slack API
    - Sends a test message to verify message delivery

    The test uses the same client creation and messaging methods as the scheduler.
    """
    click.echo('Testing Slack connection...')

    if test_slack_connection(user_id):
        click.echo('✅ Slack connection successful!')
        click.echo('Test message sent to Slack user.')
    else:
        click.echo('❌ Slack connection failed!')
        click.echo('Check the logs for detailed error information.')
        click.echo('Common issues:')
        click.echo('  • SLACK_BOT_TOKEN environment variable not set')
        click.echo('  • SLACK_USER_ID environment variable not set (if --user-id not provided)')
        click.echo('  • Invalid bot token or insufficient permissions')
        click.echo('  • Invalid user ID or bot cannot send DMs to user')
        raise click.ClickException('Slack connection test failed')


@cli.command('job-worker')
@click.option('--polling-limit', default=25, help='Maximum number of jobs to fetch per poll')
@click.option('--lock-timeout', default=10, help='How long to hold job locks (minutes)')
@click.option('--max-attempts', default=5, help='Maximum retry attempts before dead letter')
@click.option('--poll-interval', default=30, help='Seconds to wait between polling cycles')
def job_worker(polling_limit: int, lock_timeout: int, max_attempts: int, poll_interval: int) -> None:
    """Run the job worker to process scheduled jobs.

    The job worker polls the DynamoDB table for due jobs and processes them
    using registered handlers. Failed jobs are retried with exponential backoff.
    """
    run_job_worker(  # pragma: no cover
        polling_limit=polling_limit,
        lock_timeout_minutes=lock_timeout,
        max_attempts=max_attempts,
        poll_interval_seconds=poll_interval,
    )
