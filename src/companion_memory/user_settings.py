"""User settings storage interfaces and DynamoDB implementation."""

from typing import Any, Protocol

import boto3


class UserSettingsStore(Protocol):
    """Protocol for user settings storage implementations."""

    def get_user_settings(self, user_id: str) -> dict[str, Any]:
        """Get user settings for a user.

        Args:
            user_id: The user identifier
        Returns:
            Dictionary of user settings (empty if not set)

        """
        ...  # pragma: no cover

    def update_user_settings(self, user_id: str, settings: dict[str, Any]) -> None:
        """Update user settings for a user.

        Args:
            user_id: The user identifier
            settings: Dictionary of settings to store

        """
        ...  # pragma: no cover


class DynamoUserSettingsStore:
    """DynamoDB implementation of UserSettingsStore."""

    def __init__(self, table_name: str = 'CompanionMemory') -> None:
        """Initialize the DynamoDB user settings store.

        Args:
            table_name: Name of the DynamoDB table to use

        """
        import os

        self._table_name = table_name
        # Use specified region or default to us-east-1 for testing
        region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        self._dynamodb = boto3.resource('dynamodb', region_name=region)
        self._table = self._dynamodb.Table(table_name)

    def _generate_partition_key(self, user_id: str) -> str:
        """Generate partition key for DynamoDB."""
        return f'user#{user_id}'

    def _generate_sort_key(self) -> str:
        """Generate sort key for user settings."""
        return 'settings'

    def get_user_settings(self, user_id: str) -> dict[str, Any]:
        """Get user settings for a user."""
        pk = self._generate_partition_key(user_id)
        sk = self._generate_sort_key()
        response = self._table.get_item(Key={'PK': pk, 'SK': sk})
        item = response.get('Item')
        if not item:
            return {}
        # Remove PK and SK from returned settings
        return {k: v for k, v in item.items() if k not in ('PK', 'SK')}

    def update_user_settings(self, user_id: str, settings: dict[str, Any]) -> None:
        """Update user settings for a user."""
        pk = self._generate_partition_key(user_id)
        sk = self._generate_sort_key()
        item = {'PK': pk, 'SK': sk}
        item.update(settings)
        self._table.put_item(Item=item)
