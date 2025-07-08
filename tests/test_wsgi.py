"""Tests for WSGI entry point."""

import os
from unittest.mock import MagicMock, patch


def test_wsgi_creates_dynamo_log_store_when_env_var_set() -> None:
    """Test that WSGI creates DynamoDB log store when environment variable is set."""
    # Set environment variable to use DynamoDB
    original_env = os.environ.get('USE_DYNAMODB')
    os.environ['USE_DYNAMODB'] = 'true'

    try:
        with patch('companion_memory.storage.DynamoLogStore') as mock_dynamo_store:
            # Mock DynamoDB store instance
            mock_store_instance = MagicMock()
            mock_dynamo_store.return_value = mock_store_instance

            # Import wsgi module to trigger application creation
            import importlib
            import sys

            if 'companion_memory.wsgi' in sys.modules:
                importlib.reload(sys.modules['companion_memory.wsgi'])
            else:
                from companion_memory import wsgi  # noqa: F401

            # Verify DynamoLogStore was instantiated
            mock_dynamo_store.assert_called_once()

    finally:
        # Clean up environment variable
        if original_env is None:
            if 'USE_DYNAMODB' in os.environ:
                del os.environ['USE_DYNAMODB']
        else:
            os.environ['USE_DYNAMODB'] = original_env


def test_wsgi_uses_default_log_store_when_env_var_not_set() -> None:
    """Test that WSGI uses default log store when environment variable is not set."""
    # Ensure environment variable is not set
    original_env = os.environ.get('USE_DYNAMODB')
    if 'USE_DYNAMODB' in os.environ:
        del os.environ['USE_DYNAMODB']

    try:
        with patch('companion_memory.storage.DynamoLogStore') as mock_dynamo_store:
            # Import wsgi module to trigger application creation
            import importlib
            import sys

            if 'companion_memory.wsgi' in sys.modules:
                importlib.reload(sys.modules['companion_memory.wsgi'])
            else:
                from companion_memory import wsgi  # noqa: F401

            # Verify DynamoLogStore was NOT instantiated
            mock_dynamo_store.assert_not_called()

    finally:
        # Restore environment variable
        if original_env is not None:
            os.environ['USE_DYNAMODB'] = original_env
