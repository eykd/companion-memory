"""Log summarization functionality using LLM."""

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

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
