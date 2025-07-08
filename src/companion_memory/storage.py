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

    def fetch_logs(self, user_id: str, since: datetime) -> list[dict[str, Any]]:  # noqa: ARG002
        """Fetch log entries for a user since a given date.

        Args:
            user_id: The user identifier
            since: Fetch logs from this date onwards

        Returns:
            List of log entries as dictionaries

        """
        return []
