"""Command handlers for CLI operations."""

import logging
import os

import click


def run_scheduler() -> None:
    """Run the companion scheduler."""
    click.echo('Starting companion scheduler...')


def run_web_server(host: str = '127.0.0.1', port: int = 5000, debug: bool = True) -> None:  # noqa: FBT001, FBT002
    """Run the web server.

    Args:
        host: Host to bind the server to
        port: Port to bind the server to
        debug: Enable debug mode

    """
    from companion_memory.app import create_app

    app = create_app()
    click.echo(f'Starting web server on {host}:{port} (debug={debug})...')
    app.run(host=host, port=port, debug=debug)


def test_slack_connection(user_id: str | None = None) -> bool:  # noqa: PT028
    """Test Slack connection using the same mechanisms as the scheduler.

    This function tests the complete Slack integration pipeline:
    1. Validates that required environment variables are set
    2. Creates a Slack client using the same method as the scheduler
    3. Tests authentication with the Slack API
    4. Sends a test message to verify message delivery capability

    Args:
        user_id: Slack user ID to send test message to. If None, uses SLACK_USER_ID environment variable.

    Returns:
        True if connection test succeeds, False otherwise.

    """
    from companion_memory.scheduler import get_slack_client

    logger = logging.getLogger(__name__)

    # Get user ID from parameter or environment
    target_user_id = user_id or os.environ.get('SLACK_USER_ID')
    if not target_user_id:
        logger.error('No user ID provided and SLACK_USER_ID environment variable not set')
        return False

    # Validate required environment variables
    if not os.environ.get('SLACK_BOT_TOKEN'):
        logger.error('SLACK_BOT_TOKEN environment variable not set')
        return False

    try:
        # Get Slack client using same method as scheduler
        logger.debug('Creating Slack client...')
        client = get_slack_client()

        # Test authentication
        logger.debug('Testing Slack authentication...')
        auth_response = client.auth_test()
        if not auth_response.get('ok'):
            error_msg = auth_response.get('error', 'Unknown error')
            logger.error('Slack authentication failed: %s', error_msg)
            return False

        bot_info = auth_response.get('user', 'Unknown bot')
        logger.debug('Authenticated as bot: %s', bot_info)

        # Test message sending
        logger.debug('Testing message sending to user %s...', target_user_id)
        message_response = client.chat_postMessage(
            channel=target_user_id, text='✅ Test message from companion-memory CLI - Slack connection working!'
        )
        if not message_response.get('ok'):
            error_msg = message_response.get('error', 'Unknown error')
            logger.error('Message sending failed: %s', error_msg)
            return False

        logger.info('Slack connection test successful - message sent to %s', target_user_id)
    except Exception:
        logger.exception('Slack connection test failed')
        return False
    else:
        return True
