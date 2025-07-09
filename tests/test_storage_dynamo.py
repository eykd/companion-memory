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
        assert item['PK'] == 'user#U123456789'
        assert item['SK'] == f'log#{timestamp}'
        assert item['user_id'] == 'U123456789'
        assert item['timestamp'] == timestamp
        assert item['text'] == 'Working on unit tests'
        assert item['log_id'] == 'test-log-id'


def test_dynamo_log_store_fetch_logs() -> None:
    """Test that DynamoLogStore.fetch_logs() queries DynamoDB and returns logs."""
    from datetime import UTC, datetime

    # Mock boto3 client
    mock_dynamodb = MagicMock()
    mock_table = mock_dynamodb.Table.return_value

    # Mock query response
    mock_response = {
        'Items': [
            {
                'pk': 'user#U123456789',
                'sk': 'log#2024-01-15T10:00:00+00:00',
                'user_id': 'U123456789',
                'timestamp': '2024-01-15T10:00:00+00:00',
                'text': 'Working on unit tests',
                'log_id': 'test-log-1',
            },
            {
                'pk': 'user#U123456789',
                'sk': 'log#2024-01-15T11:00:00+00:00',
                'user_id': 'U123456789',
                'timestamp': '2024-01-15T11:00:00+00:00',
                'text': 'Debugging API',
                'log_id': 'test-log-2',
            },
        ]
    }
    mock_table.query.return_value = mock_response

    with patch('companion_memory.storage.boto3.resource', return_value=mock_dynamodb):
        store = DynamoLogStore()

        # Test fetch_logs
        since = datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC)
        logs = store.fetch_logs('U123456789', since)

        # Verify DynamoDB query was called
        mock_table.query.assert_called_once()
        call_args = mock_table.query.call_args[1]
        assert call_args['KeyConditionExpression'] is not None

        # Verify results
        assert len(logs) == 2
        assert logs[0]['text'] == 'Working on unit tests'
        assert logs[1]['text'] == 'Debugging API'


def test_dynamo_log_store_fetch_logs_with_pagination() -> None:
    """Test that DynamoLogStore.fetch_logs() handles pagination correctly."""
    from datetime import UTC, datetime

    # Mock boto3 client
    mock_dynamodb = MagicMock()
    mock_table = mock_dynamodb.Table.return_value

    # Mock pagination: first response has LastEvaluatedKey, second doesn't
    first_response = {
        'Items': [
            {
                'pk': 'user#U123456789',
                'sk': 'log#2024-01-15T10:00:00+00:00',
                'user_id': 'U123456789',
                'timestamp': '2024-01-15T10:00:00+00:00',
                'text': 'First batch',
                'log_id': 'test-log-1',
            }
        ],
        'LastEvaluatedKey': {'pk': 'user#U123456789', 'sk': 'log#2024-01-15T10:00:00+00:00'},
    }

    second_response = {
        'Items': [
            {
                'pk': 'user#U123456789',
                'sk': 'log#2024-01-15T11:00:00+00:00',
                'user_id': 'U123456789',
                'timestamp': '2024-01-15T11:00:00+00:00',
                'text': 'Second batch',
                'log_id': 'test-log-2',
            }
        ]
        # No LastEvaluatedKey in second response
    }

    mock_table.query.side_effect = [first_response, second_response]

    with patch('companion_memory.storage.boto3.resource', return_value=mock_dynamodb):
        store = DynamoLogStore()

        # Test fetch_logs with pagination
        since = datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC)
        logs = store.fetch_logs('U123456789', since)

        # Verify DynamoDB query was called twice (pagination)
        assert mock_table.query.call_count == 2

        # Verify results from both pages
        assert len(logs) == 2
        assert logs[0]['text'] == 'First batch'
        assert logs[1]['text'] == 'Second batch'

        # Verify second call included ExclusiveStartKey
        second_call_args = mock_table.query.call_args_list[1][1]
        assert 'ExclusiveStartKey' in second_call_args


def test_dynamo_log_store_fetch_logs_with_exception() -> None:
    """Test that DynamoLogStore.fetch_logs() handles exceptions gracefully."""
    from datetime import UTC, datetime

    # Mock boto3 client that raises exception
    mock_dynamodb = MagicMock()
    mock_table = mock_dynamodb.Table.return_value
    mock_table.query.side_effect = Exception('DynamoDB error')

    with patch('companion_memory.storage.boto3.resource', return_value=mock_dynamodb):
        store = DynamoLogStore()

        # Test fetch_logs with exception
        since = datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC)
        logs = store.fetch_logs('U123456789', since)

        # Should return empty list as fallback
        assert logs == []


def test_dynamo_log_store_fetch_logs_with_mixed_timestamps() -> None:
    """Test that DynamoLogStore.fetch_logs() filters by timestamp correctly."""
    from datetime import UTC, datetime

    # Mock boto3 client
    mock_dynamodb = MagicMock()
    mock_table = mock_dynamodb.Table.return_value

    # Mock response with logs before and after the 'since' date
    mock_response = {
        'Items': [
            {
                'pk': 'user#U123456789',
                'sk': 'log#2024-01-15T08:00:00+00:00',  # Before 'since'
                'user_id': 'U123456789',
                'timestamp': '2024-01-15T08:00:00+00:00',
                'text': 'Too early',
                'log_id': 'test-log-early',
            },
            {
                'pk': 'user#U123456789',
                'sk': 'log#2024-01-15T10:00:00+00:00',  # After 'since'
                'user_id': 'U123456789',
                'timestamp': '2024-01-15T10:00:00+00:00',
                'text': 'Just right',
                'log_id': 'test-log-good',
            },
        ]
    }
    mock_table.query.return_value = mock_response

    with patch('companion_memory.storage.boto3.resource', return_value=mock_dynamodb):
        store = DynamoLogStore()

        # Test fetch_logs with filtering
        since = datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC)  # 9 AM
        logs = store.fetch_logs('U123456789', since)

        # Should only return the log after 9 AM
        assert len(logs) == 1
        assert logs[0]['text'] == 'Just right'
