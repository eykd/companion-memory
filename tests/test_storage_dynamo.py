"""Tests for DynamoDB storage implementation."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from companion_memory.storage import DynamoLogStore


def test_dynamo_log_store_write_log() -> None:
    """Test that DynamoLogStore.write_log() calls DynamoDB put_item."""
    # Mock boto3 client
    mock_dynamodb = MagicMock()

    with patch('companion_memory.storage.boto3.resource', return_value=mock_dynamodb):
        store = DynamoLogStore()

        # Test write_log
        timestamp = datetime.now(UTC).isoformat()
        store.write_log(user_id='U123456789', timestamp=timestamp, text='Working on unit tests', log_id='test-log-id')

        # Verify DynamoDB was called
        mock_table = mock_dynamodb.Table.return_value
        mock_table.put_item.assert_called_once()

        # Check the item structure
        call_args = mock_table.put_item.call_args
        item = call_args[1]['Item']
        assert item['pk'] == 'user#U123456789'
        assert item['sk'] == f'log#{timestamp}'
        assert item['user_id'] == 'U123456789'
        assert item['timestamp'] == timestamp
        assert item['text'] == 'Working on unit tests'
        assert item['log_id'] == 'test-log-id'
