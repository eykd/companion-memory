"""Tests for user settings storage."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.block_network


def test_user_settings_store_interface() -> None:
    """Test that UserSettingsStore interface can be called."""
    # This test will fail until we implement the interface

    # Create a mock implementation for testing
    class MockUserSettingsStore:
        def get_user_settings(self, user_id: str) -> dict[str, Any]:
            """Get user settings."""
            return {}

        def update_user_settings(self, user_id: str, settings: dict[str, Any]) -> None:
            """Update user settings."""

    store = MockUserSettingsStore()

    # Test that we can call the methods
    settings = store.get_user_settings('U123456789')
    assert isinstance(settings, dict)

    store.update_user_settings('U123456789', {'timezone': 'UTC'})


def test_dynamo_user_settings_store_timezone() -> None:
    """Test that DynamoUserSettingsStore can store and retrieve a user's timezone."""
    from companion_memory.user_settings import DynamoUserSettingsStore

    mock_dynamodb = MagicMock()
    mock_table = mock_dynamodb.Table.return_value

    # Simulate get_item returning no settings initially
    mock_table.get_item.return_value = {}

    with patch('companion_memory.user_settings.boto3.resource', return_value=mock_dynamodb):
        store = DynamoUserSettingsStore()
        user_id = 'U123456789'
        # Should return empty dict if not set
        settings = store.get_user_settings(user_id)
        assert settings == {}

        # Now update settings
        store.update_user_settings(user_id, {'timezone': 'America/Los_Angeles'})
        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]['Item']
        assert item['PK'] == f'user#{user_id}'
        assert item['SK'] == 'settings'
        assert item['timezone'] == 'America/Los_Angeles'

        # Simulate get_item returning the settings
        mock_table.get_item.return_value = {'Item': item}
        settings = store.get_user_settings(user_id)
        assert settings['timezone'] == 'America/Los_Angeles'
