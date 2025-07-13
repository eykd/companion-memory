"""Log summarization functionality using LLM."""

import logging
import zoneinfo
from datetime import UTC, datetime, timedelta, timezone
from textwrap import dedent
from typing import Any, Protocol

# Import moved to function level to avoid circular import
from companion_memory.storage import LogStore

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Protocol for LLM client implementations."""

    def complete(self, prompt: str) -> str:
        """Generate completion for given prompt.

        Args:
            prompt: The input prompt for the LLM

        Returns:
            Generated completion text

        """
        ...  # pragma: no cover


def _format_log_entries(logs: list[dict[str, Any]], user_tz: timezone | zoneinfo.ZoneInfo | None = None) -> str:
    """Format log entries for inclusion in prompts.

    Args:
        logs: List of log entry dictionaries
        user_tz: User's timezone for timestamp conversion (defaults to UTC)

    Returns:
        Formatted string with log entries

    """
    if user_tz is None:
        user_tz = UTC

    log_entries = []
    for log in logs:
        # Parse UTC timestamp and convert to user timezone
        utc_timestamp = datetime.fromisoformat(log['timestamp'])
        user_timestamp = utc_timestamp.astimezone(user_tz)
        # Format timestamp in user's timezone (show date and time)
        formatted_timestamp = user_timestamp.strftime('%Y-%m-%d %H:%M:%S')
        log_entries.append(f'- {formatted_timestamp}: {log["text"]}')

    return '\n'.join(log_entries)


def _build_summary_prompt(logs_text: str, period: str) -> str:
    """Build LLM prompt for summarizing logs.

    Args:
        logs_text: Formatted log entries text
        period: Time period description (e.g., "past week")

    Returns:
        Complete prompt string

    """
    return dedent(
        f"""
        You will be acting in the role of an executive assistant for an important executive with limited time.

        Your executive has tasked you with summarizing the executive's work log entries from the {period}.

        Here are the log entries:

        <log-entries>
        {logs_text}
        </log-entries>

        Using these log entries, provide a concise summary of the main activities and themes.
        - Instead of specific times, refer to general times of the day.
        - Include both the name of the day and the date.
        - Include any relevant metrics or insights that are relevant to the executive's work.
        - Use the second person (you), as if you were addressing the executive directly in conversation.
        - Do not include a preamble, address, or salutation.
        - Do not invite the executive to respond or follow up.
        - Do not include any other text than the summary.
        - Format your summary as a bulleted list.
        - At the end of the summary, make note of any items that are not yet complete or left unaddressed.
"""
    )


def _summarize_period(user_id: str, log_store: LogStore, llm: LLMClient, days: int, period_name: str) -> str:
    """Generate a summary of the user's logs from a specified time period.

    Args:
        user_id: The user identifier
        log_store: Storage implementation for fetching logs
        llm: LLM client for generating summaries
        days: Number of days to look back
        period_name: Human-readable period description for the prompt

    Returns:
        Generated summary text

    """
    # Get user's timezone for timestamp formatting
    user_tz = _get_user_timezone(user_id)

    # Calculate date N days ago
    since = datetime.now(UTC) - timedelta(days=days)

    # Fetch logs from the period
    logs = log_store.fetch_logs(user_id, since)

    # Format logs and build prompt
    logs_text = _format_log_entries(logs, user_tz)
    prompt = _build_summary_prompt(logs_text, period_name)

    # Generate summary using LLM
    return llm.complete(prompt)


def summarize_week(user_id: str, log_store: LogStore, llm: LLMClient) -> str:
    """Generate a summary of the user's logs from the past week.

    Args:
        user_id: The user identifier
        log_store: Storage implementation for fetching logs
        llm: LLM client for generating summaries

    Returns:
        Generated summary text

    """
    return _summarize_period(user_id, log_store, llm, days=7, period_name='past week')


def summarize_day(user_id: str, log_store: LogStore, llm: LLMClient) -> str:
    """Generate a summary of the user's logs from the past day.

    Args:
        user_id: The user identifier
        log_store: Storage implementation for fetching logs
        llm: LLM client for generating summaries

    Returns:
        Generated summary text

    """
    return _summarize_period(user_id, log_store, llm, days=1, period_name='past day')


def _get_user_timezone(user_id: str) -> timezone | zoneinfo.ZoneInfo:
    """Get user's timezone from DynamoDB user settings, with fallback to Slack sync and UTC.

    If no user record exists in DynamoDB, attempts to sync timezone from Slack API
    and create the user record before returning the timezone.

    Args:
        user_id: The user identifier

    Returns:
        User's timezone or UTC if unable to determine

    """
    try:
        from companion_memory.user_settings import DynamoUserSettingsStore

        settings_store = DynamoUserSettingsStore()
        user_settings = settings_store.get_user_settings(user_id)

        # Check if user has timezone setting
        user_tz_name = user_settings.get('timezone')

        # If no timezone found, try to sync from Slack
        if not user_tz_name:
            from companion_memory.user_sync import sync_user_timezone_from_slack

            user_tz_name = sync_user_timezone_from_slack(user_id)
            if not user_tz_name:
                # Could not sync from Slack, fall back to UTC
                return UTC

        if user_tz_name == 'UTC':
            return UTC

        try:
            return zoneinfo.ZoneInfo(user_tz_name)
        except zoneinfo.ZoneInfoNotFoundError:
            return UTC

    except Exception:  # noqa: BLE001
        # Fall back to UTC if any error occurs with DynamoDB or Slack sync
        return UTC


def _summarize_timezone_aware_day(
    user_id: str, log_store: LogStore, llm: LLMClient, days_offset: int, period_name: str
) -> str:
    """Generate a summary of the user's logs from a specific day in their timezone.

    Gets the user's timezone from DynamoDB user settings, then calculates
    the target day's date range in that timezone and fetches logs accordingly.

    Args:
        user_id: The user identifier
        log_store: Storage implementation for fetching logs
        llm: LLM client for generating summaries
        days_offset: Number of days to offset from today (0=today, 1=yesterday, etc.)
        period_name: Human-readable period description for the prompt

    Returns:
        Generated summary text

    """
    # Get user's timezone
    user_tz = _get_user_timezone(user_id)

    # Get current time in user's timezone
    now_user_tz = datetime.now(user_tz)

    # Calculate target day's start time in user's timezone
    target_day_start = now_user_tz.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_offset)

    # Convert to UTC for storage query
    target_day_start_utc = target_day_start.astimezone(UTC)

    # Fetch logs from target day
    logs = log_store.fetch_logs(user_id, target_day_start_utc)

    # Format logs and build prompt
    logs_text = _format_log_entries(logs, user_tz)
    prompt = _build_summary_prompt(logs_text, period_name)

    # Generate summary using LLM
    return llm.complete(prompt)


def summarize_yesterday(user_id: str, log_store: LogStore, llm: LLMClient) -> str:
    """Generate a summary of the user's logs from yesterday in their timezone.

    Gets the user's timezone from DynamoDB user settings, then calculates
    yesterday's date range in that timezone and fetches logs accordingly.

    Args:
        user_id: The user identifier
        log_store: Storage implementation for fetching logs
        llm: LLM client for generating summaries

    Returns:
        Generated summary text

    """
    return _summarize_timezone_aware_day(user_id, log_store, llm, days_offset=1, period_name='day before')


def summarize_today(user_id: str, log_store: LogStore, llm: LLMClient) -> str:
    """Generate a summary of the user's logs from today in their timezone.

    Gets the user's timezone from DynamoDB user settings, then calculates
    today's date range in that timezone and fetches logs accordingly.

    Args:
        user_id: The user identifier
        log_store: Storage implementation for fetching logs
        llm: LLM client for generating summaries

    Returns:
        Generated summary text

    """
    return _summarize_timezone_aware_day(user_id, log_store, llm, days_offset=0, period_name='today')


def _format_summary_message(weekly_summary: str, daily_summary: str) -> str:
    """Format combined weekly and daily summaries into a message.

    Args:
        weekly_summary: Summary of the past week's activities
        daily_summary: Summary of the past day's activities

    Returns:
        Formatted message text

    """
    return dedent(
        f"""
        Here's your activity summary:

        **This Week:**
        {weekly_summary}

        **Yesterday:**
        {daily_summary}
        """
    )


def send_summary_message(user_id: str, log_store: LogStore, llm: LLMClient) -> None:
    """Generate and send combined summary message via Slack.

    Args:
        user_id: The user identifier
        log_store: Storage implementation for fetching logs
        llm: LLM client for generating summaries

    """
    # Generate both weekly and yesterday summaries for morning delivery
    weekly_summary = summarize_week(user_id, log_store, llm)
    daily_summary = summarize_yesterday(user_id, log_store, llm)

    # Format combined message
    message = _format_summary_message(weekly_summary, daily_summary)

    # Send via Slack
    from companion_memory.scheduler import get_slack_client

    slack_client = get_slack_client()
    slack_client.chat_postMessage(channel=user_id, text=message)


def send_daily_summary_to_users(log_store: LogStore, llm: LLMClient) -> None:
    """Send daily summaries to all configured users.

    Gets the list of users from DAILY_SUMMARY_USERS environment variable
    and sends daily summaries to each user.

    Args:
        log_store: Storage implementation for fetching logs
        llm: LLM client for generating summaries

    """
    import os

    users_env = os.environ.get('DAILY_SUMMARY_USERS', '')
    if not users_env:
        logger.info('No users configured for daily summaries (DAILY_SUMMARY_USERS not set)')
        return

    # Parse comma-separated user IDs
    user_ids = [user_id.strip() for user_id in users_env.split(',') if user_id.strip()]

    if not user_ids:
        logger.info('No valid user IDs found in DAILY_SUMMARY_USERS')
        return

    logger.info('Sending daily summaries to %d users: %s', len(user_ids), ', '.join(user_ids))

    for user_id in user_ids:
        try:
            send_summary_message(user_id, log_store, llm)
            logger.info('Successfully sent daily summary to user %s', user_id)
        except Exception:
            logger.exception('Failed to send daily summary to user %s', user_id)


def check_and_send_daily_summaries(log_store: LogStore, llm: LLMClient) -> None:
    """Check if it's 7am in any user's timezone and send daily summaries.

    This function should be called hourly. It checks each configured user's
    timezone and sends daily summaries to users for whom it's currently 7am.

    Args:
        log_store: Storage implementation for fetching logs
        llm: LLM client for generating summaries

    """
    import os

    users_env = os.environ.get('DAILY_SUMMARY_USERS', '')
    if not users_env:
        return

    # Parse comma-separated user IDs
    user_ids = [user_id.strip() for user_id in users_env.split(',') if user_id.strip()]

    if not user_ids:
        return

    current_utc = datetime.now(UTC)
    users_to_notify = []

    for user_id in user_ids:
        try:
            # Get user's timezone
            user_tz = _get_user_timezone(user_id)

            # Convert current UTC time to user's timezone
            user_local_time = current_utc.astimezone(user_tz)

            # Check if it's 7am in the user's timezone (within the current hour)
            if user_local_time.hour == 7:
                users_to_notify.append(user_id)

        except Exception:
            logger.exception('Failed to check timezone for user %s', user_id)

    if users_to_notify:
        logger.info(
            'Sending daily summaries to %d users at 7am local time: %s',
            len(users_to_notify),
            ', '.join(users_to_notify),
        )

        for user_id in users_to_notify:
            try:
                send_summary_message(user_id, log_store, llm)
                logger.info('Successfully sent daily summary to user %s', user_id)
            except Exception:
                logger.exception('Failed to send daily summary to user %s', user_id)
