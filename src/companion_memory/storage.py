"""Storage interfaces and implementations for log data."""

from datetime import datetime
from typing import Any, Protocol

import boto3  # type: ignore[import-untyped]


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


class DynamoLogStore:
    """DynamoDB implementation of LogStore."""

    def __init__(self, table_name: str = 'companion-memory-logs') -> None:
        """Initialize the DynamoDB log store.

        Args:
            table_name: Name of the DynamoDB table to use

        """
        self._table_name = table_name
        self._dynamodb = boto3.resource('dynamodb')
        self._table = self._dynamodb.Table(table_name)

    def _generate_partition_key(self, user_id: str) -> str:
        """Generate partition key for DynamoDB.

        Args:
            user_id: The user identifier

        Returns:
            Partition key string

        """
        return f'user#{user_id}'

    def _generate_sort_key(self, timestamp: str) -> str:
        """Generate sort key for DynamoDB.

        Args:
            timestamp: ISO 8601 timestamp string

        Returns:
            Sort key string

        """
        return f'log#{timestamp}'

    def write_log(self, user_id: str, timestamp: str, text: str, log_id: str) -> None:
        """Write a log entry to DynamoDB.

        Args:
            user_id: The user identifier
            timestamp: ISO 8601 timestamp string
            text: The log content
            log_id: Unique identifier for the log entry

        """
        item = {
            'pk': self._generate_partition_key(user_id),
            'sk': self._generate_sort_key(timestamp),
            'user_id': user_id,
            'timestamp': timestamp,
            'text': text,
            'log_id': log_id,
        }
        self._table.put_item(Item=item)

    def fetch_logs(self, _user_id: str, _since: datetime) -> list[dict[str, Any]]:
        """Fetch log entries for a user since a given date.

        Args:
            _user_id: The user identifier
            _since: Fetch logs from this date onwards

        Returns:
            List of log entries as dictionaries

        """
        # TODO: Implement in Step 11
        return []
