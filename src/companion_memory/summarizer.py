"""Log summarization functionality using LLM."""

from datetime import UTC, datetime, timedelta
from typing import Protocol

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


def summarize_week(user_id: str, log_store: LogStore, llm: LLMClient) -> str:
    """Generate a summary of the user's logs from the past week.

    Args:
        user_id: The user identifier
        log_store: Storage implementation for fetching logs
        llm: LLM client for generating summaries

    Returns:
        Generated summary text

    """
    # Calculate date 7 days ago
    since = datetime.now(UTC) - timedelta(days=7)

    # Fetch logs from the past week
    logs = log_store.fetch_logs(user_id, since)

    # Build prompt with logs
    log_entries = [f'- {log["timestamp"]}: {log["text"]}' for log in logs]

    logs_text = '\n'.join(log_entries)
    prompt = f"""Please summarize the following work log entries from the past week:

{logs_text}

Provide a concise summary of the main activities and themes."""

    # Generate summary using LLM
    return llm.complete(prompt)
