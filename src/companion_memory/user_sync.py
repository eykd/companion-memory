"""User profile sync jobs (e.g., time zone) from Slack to DynamoDB user settings."""

import logging
import os

from companion_memory.user_settings import DynamoUserSettingsStore

logger = logging.getLogger(__name__)


def sync_user_timezone_from_slack(user_id: str) -> str | None:
    """Sync a specific user's timezone from Slack to DynamoDB user settings.

    Args:
        user_id: The Slack user ID to sync timezone for

    Returns:
        The timezone string if successfully synced, None otherwise

    """
    # Import here to avoid circular import
    from companion_memory.scheduler import get_slack_client

    try:
        slack_client = get_slack_client()
        response = slack_client.users_info(user=user_id)
        if not response.get('ok'):
            logger.warning('Failed to fetch user info from Slack for user %s: %s', user_id, response)
            return None

        user = response['user']
        timezone = user.get('tz')
        if not timezone:
            logger.info('No time zone found in Slack profile for user %s', user_id)
            return None

        settings_store = DynamoUserSettingsStore()
        settings_store.update_user_settings(user_id, {'timezone': timezone})
        logger.info('Synced user %s timezone to %s from Slack to DynamoDB', user_id, timezone)

    except Exception:
        logger.exception('Error syncing user timezone from Slack for user %s', user_id)
        return None
    else:
        return str(timezone)


def sync_user_timezone() -> None:
    """Sync the user's time zone from Slack to DynamoDB user settings.

    Fetches the user's profile from Slack, extracts the time zone,
    and updates the user settings record in DynamoDB.
    """
    slack_user_id = os.environ.get('SLACK_USER_ID')
    if not slack_user_id:
        logger.warning('SLACK_USER_ID environment variable not set; cannot sync time zone')
        return

    sync_user_timezone_from_slack(slack_user_id)
