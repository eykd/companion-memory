"""Tests for LogStore interface and implementations."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:  # pragma: no cover
    from companion_memory.storage import LogStore

from companion_memory.storage import MemoryLogStore

pytestmark = pytest.mark.block_network


class TestLogStore:
    """Test implementation of LogStore protocol."""

    def write_log(self, user_id: str, timestamp: str, text: str, log_id: str) -> None:
        """Test implementation of write_log."""

    def fetch_logs(self, user_id: str, since: datetime) -> list[dict[str, Any]]:
        """Test implementation of fetch_logs."""
        return []


def test_log_store_has_write_log_method() -> None:
    """Test that LogStore has a write_log method."""
    store: LogStore = TestLogStore()
    store.write_log(user_id='user123', timestamp='2023-01-01T12:00:00Z', text='Test log entry', log_id='log123')


def test_log_store_has_fetch_logs_method() -> None:
    """Test that LogStore has a fetch_logs method."""
    store: LogStore = TestLogStore()
    since = datetime(2023, 1, 1, tzinfo=UTC)
    logs = store.fetch_logs(user_id='user123', since=since)
    assert isinstance(logs, list)


def test_memory_log_store_write_log_stores_record() -> None:
    """Test that MemoryLogStore write_log() stores a record."""
    store = MemoryLogStore()
    store.write_log(user_id='user123', timestamp='2023-01-01T12:00:00Z', text='Test log entry', log_id='log123')

    # Verify the record was stored
    assert 'user123' in store._storage  # noqa: SLF001
    assert len(store._storage['user123']) == 1  # noqa: SLF001

    log_entry = store._storage['user123'][0]  # noqa: SLF001
    assert log_entry['user_id'] == 'user123'
    assert log_entry['timestamp'] == '2023-01-01T12:00:00Z'
    assert log_entry['text'] == 'Test log entry'
    assert log_entry['log_id'] == 'log123'


def test_memory_log_store_fetch_logs_filters_by_date() -> None:
    """Test that MemoryLogStore fetch_logs() filters logs by date."""
    store = MemoryLogStore()

    # Add some log entries with different timestamps
    store.write_log(user_id='user123', timestamp='2023-01-01T10:00:00Z', text='Old log', log_id='log1')
    store.write_log(user_id='user123', timestamp='2023-01-01T12:00:00Z', text='Recent log', log_id='log2')
    store.write_log(user_id='user123', timestamp='2023-01-01T14:00:00Z', text='Newer log', log_id='log3')

    # Fetch logs since 11:00 AM - should return 2 entries
    since = datetime(2023, 1, 1, 11, 0, 0, tzinfo=UTC)
    logs = store.fetch_logs(user_id='user123', since=since)

    assert len(logs) == 2
    assert logs[0]['text'] == 'Recent log'
    assert logs[1]['text'] == 'Newer log'


def test_memory_log_store_fetch_logs_filters_by_user() -> None:
    """Test that MemoryLogStore fetch_logs() filters logs by user."""
    store = MemoryLogStore()

    # Add logs for different users
    store.write_log(user_id='user123', timestamp='2023-01-01T12:00:00Z', text='User 123 log', log_id='log1')
    store.write_log(user_id='user456', timestamp='2023-01-01T12:00:00Z', text='User 456 log', log_id='log2')

    # Fetch logs for user123 only
    since = datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC)
    logs = store.fetch_logs(user_id='user123', since=since)

    assert len(logs) == 1
    assert logs[0]['text'] == 'User 123 log'


def test_memory_log_store_fetch_logs_returns_empty_for_nonexistent_user() -> None:
    """Test that MemoryLogStore fetch_logs() returns empty list for nonexistent user."""
    store = MemoryLogStore()

    since = datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC)
    logs = store.fetch_logs(user_id='nonexistent', since=since)

    assert logs == []
