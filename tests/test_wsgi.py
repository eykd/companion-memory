"""Tests for WSGI entry point."""

from unittest.mock import MagicMock, patch


def test_wsgi_creates_dynamo_log_store_for_production() -> None:
    """Test that WSGI creates DynamoDB log store for production deployment."""
    import sys

    # Remove module from cache to force re-import
    if 'companion_memory.wsgi' in sys.modules:
        del sys.modules['companion_memory.wsgi']

    # Patch at the storage module level where DynamoLogStore is defined
    with patch('companion_memory.storage.DynamoLogStore') as mock_dynamo_store:
        # Mock DynamoDB store instance
        mock_store_instance = MagicMock()
        mock_dynamo_store.return_value = mock_store_instance

        # Import wsgi module to trigger application creation
        from companion_memory import wsgi  # noqa: F401

        # Verify DynamoLogStore was instantiated
        mock_dynamo_store.assert_called_once()
