"""Storage interfaces and implementations for log data."""

from datetime import datetime
from typing import Any, Protocol


class LogStore(Protocol):
    """Protocol for log storage implementations."""

    def write_log(self, user_id: str, timestamp: str, text: str, log_id: str) -> None:
        """Write a log entry to storage.

        Args:
            user_id: The user identifier
            timestamp: ISO 8601 timestamp string
            text: The log content
            log_id: Unique identifier for the log entry

        """
        ...

    def fetch_logs(self, user_id: str, since: datetime) -> list[dict[str, Any]]:
        """Fetch log entries for a user since a given date.

        Args:
            user_id: The user identifier
            since: Fetch logs from this date onwards

        Returns:
            List of log entries as dictionaries

        """
        ...


class MemoryLogStore:
    """In-memory implementation of LogStore for testing."""

    def __init__(self) -> None:
        """Initialize the memory log store."""
        self._storage: dict[str, list[dict[str, Any]]] = {}

    def write_log(self, user_id: str, timestamp: str, text: str, log_id: str) -> None:
        """Write a log entry to memory storage.

        Args:
            user_id: The user identifier
            timestamp: ISO 8601 timestamp string
            text: The log content
            log_id: Unique identifier for the log entry

        """
        if user_id not in self._storage:
            self._storage[user_id] = []

        log_entry = {
            'user_id': user_id,
            'timestamp': timestamp,
            'text': text,
            'log_id': log_id,
        }
        self._storage[user_id].append(log_entry)

    def fetch_logs(self, user_id: str, since: datetime) -> list[dict[str, Any]]:
        """Fetch log entries for a user since a given date.

        Args:
            user_id: The user identifier
            since: Fetch logs from this date onwards

        Returns:
            List of log entries as dictionaries

        """
        if user_id not in self._storage:
            return []

        user_logs = self._storage[user_id]
        filtered_logs = []

        for log_entry in user_logs:
            # Parse the ISO timestamp string
            log_timestamp = datetime.fromisoformat(log_entry['timestamp'].replace('Z', '+00:00'))  # noqa: FURB162

            # Filter logs that are at or after the 'since' datetime
            if log_timestamp >= since:
                filtered_logs.append(log_entry)

        return filtered_logs
