"""Scheduler functionality for work sampling and summaries."""

import os

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]
from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import-untyped]
from slack_sdk import WebClient


def create_scheduler(*, blocking: bool = True) -> BlockingScheduler | BackgroundScheduler:
    """Create and configure the APScheduler instance.

    Args:
        blocking: If True, return BlockingScheduler; if False, return BackgroundScheduler

    Returns:
        Configured scheduler instance

    """
    if blocking:
        return BlockingScheduler()
    return BackgroundScheduler()


def get_slack_client() -> WebClient:
    """Get the Slack WebClient instance.

    Returns:
        Configured Slack WebClient

    """
    bot_token = os.environ.get('SLACK_BOT_TOKEN')
    if not bot_token:
        raise ValueError('SLACK_BOT_TOKEN environment variable is required')

    return WebClient(token=bot_token)


def send_sampling_prompt(user_id: str) -> None:
    """Send a work sampling prompt to a user via Slack DM.

    Args:
        user_id: The Slack user ID to send the message to

    """
    client = get_slack_client()

    message = 'What are you doing right now?'

    client.chat_postMessage(channel=user_id, text=message)
