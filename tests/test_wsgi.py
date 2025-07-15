"""Tests for WSGI entry point."""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.block_network


def test_wsgi_creates_dynamo_log_store_and_llm_client_for_production() -> None:
    """Test that WSGI creates DynamoDB log store and LLM client for production deployment."""
    import sys

    # Remove module from cache to force re-import
    if 'companion_memory.wsgi' in sys.modules:
        del sys.modules['companion_memory.wsgi']

    # Patch at the module level where classes are defined
    with (
        patch('companion_memory.storage.DynamoLogStore') as mock_dynamo_store,
        patch('companion_memory.llm_client.LLMLClient') as mock_llm_client,
        patch('boto3.resource') as mock_boto3,
    ):
        # Mock instances
        mock_store_instance = MagicMock()
        mock_llm_instance = MagicMock()
        mock_table = MagicMock()
        mock_dynamo_store.return_value = mock_store_instance
        mock_llm_client.return_value = mock_llm_instance
        mock_boto3.return_value.Table.return_value = mock_table

        # Import wsgi module to trigger application creation
        from companion_memory import wsgi  # noqa: F401

        # Verify both DynamoLogStore and LLMLClient were instantiated
        mock_dynamo_store.assert_called_once()
        mock_llm_client.assert_called_once()
