"""Tests for LogStore interface and implementations."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from companion_memory.storage import LogStore


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
