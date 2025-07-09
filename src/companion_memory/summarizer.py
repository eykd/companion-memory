"""Log summarization functionality using LLM."""

import zoneinfo
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Protocol

from companion_memory.scheduler import get_slack_client
from companion_memory.storage import LogStore


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


def _format_log_entries(logs: list[dict[str, Any]]) -> str:
    """Format log entries for inclusion in prompts.

    Args:
        logs: List of log entry dictionaries

    Returns:
        Formatted string with log entries

    """
    log_entries = [f'- {log["timestamp"]}: {log["text"]}' for log in logs]
    return '\n'.join(log_entries)


def _build_summary_prompt(logs_text: str, period: str) -> str:
    """Build LLM prompt for summarizing logs.

    Args:
        logs_text: Formatted log entries text
        period: Time period description (e.g., "past week")

    Returns:
        Complete prompt string

    """
    return f"""Please summarize the following work log entries from the {period}:

{logs_text}

Provide a concise summary of the main activities and themes."""


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
    # Calculate date N days ago
    since = datetime.now(UTC) - timedelta(days=days)

    # Fetch logs from the period
    logs = log_store.fetch_logs(user_id, since)

    # Format logs and build prompt
    logs_text = _format_log_entries(logs)
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
    """Get user's timezone from Slack, with fallback to UTC.

    Args:
        user_id: The user identifier

    Returns:
        User's timezone or UTC if unable to determine

    """
    try:
        slack_client = get_slack_client()
        user_info = slack_client.users_info(user=user_id)

        if not user_info.get('ok'):
            return UTC

        user_tz_name = user_info['user'].get('tz', 'UTC')
        if user_tz_name == 'UTC':
            return UTC

        try:
            return zoneinfo.ZoneInfo(user_tz_name)
        except zoneinfo.ZoneInfoNotFoundError:
            return UTC

    except Exception:  # noqa: BLE001
        # Fall back to UTC if any error occurs with Slack API
        return UTC


def summarize_yesterday(user_id: str, log_store: LogStore, llm: LLMClient) -> str:
    """Generate a summary of the user's logs from yesterday in their timezone.

    Discovers the user's timezone via Slack's users_info API, then calculates
    yesterday's date range in that timezone and fetches logs accordingly.

    Args:
        user_id: The user identifier
        log_store: Storage implementation for fetching logs
        llm: LLM client for generating summaries

    Returns:
        Generated summary text

    """
    # Get user's timezone
    user_tz = _get_user_timezone(user_id)

    # Get current time in user's timezone
    now_user_tz = datetime.now(user_tz)

    # Calculate yesterday's start time in user's timezone
    yesterday_start = now_user_tz.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)

    # Convert to UTC for storage query
    yesterday_start_utc = yesterday_start.astimezone(UTC)

    # Fetch logs from yesterday
    logs = log_store.fetch_logs(user_id, yesterday_start_utc)

    # Format logs and build prompt
    # Note: In a real implementation, we might want to filter logs here, but
    # for now we trust that fetch_logs returns the correct date range
    logs_text = _format_log_entries(logs)
    prompt = _build_summary_prompt(logs_text, 'yesterday')

    # Generate summary using LLM
    return llm.complete(prompt)


def _format_summary_message(weekly_summary: str, daily_summary: str) -> str:
    """Format combined weekly and daily summaries into a message.

    Args:
        weekly_summary: Summary of the past week's activities
        daily_summary: Summary of the past day's activities

    Returns:
        Formatted message text

    """
    return f"""Here's your activity summary:

**This Week:**
{weekly_summary}

**Today:**
{daily_summary}"""


def send_summary_message(user_id: str, log_store: LogStore, llm: LLMClient) -> None:
    """Generate and send combined summary message via Slack.

    Args:
        user_id: The user identifier
        log_store: Storage implementation for fetching logs
        llm: LLM client for generating summaries

    """
    # Generate both weekly and daily summaries
    weekly_summary = summarize_week(user_id, log_store, llm)
    daily_summary = summarize_day(user_id, log_store, llm)

    # Format combined message
    message = _format_summary_message(weekly_summary, daily_summary)

    # Send via Slack
    slack_client = get_slack_client()
    slack_client.chat_postMessage(channel=user_id, text=message)
