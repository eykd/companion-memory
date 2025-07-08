"""Tests for Flask web application."""

from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest

from companion_memory.app import create_app

if TYPE_CHECKING:  # pragma: no cover
    from flask.testing import FlaskClient


@pytest.fixture
def client() -> Generator['FlaskClient', None, None]:
    """Create a test client for the Flask app."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_root_url_returns_200(client: 'FlaskClient') -> None:
    """Test that root URL returns 200 status code."""
    response = client.get('/')
    assert response.status_code == 200


def test_fail_endpoint_returns_500(client: 'FlaskClient') -> None:
    """Test that /fail endpoint returns 500 status code."""
    with pytest.raises(RuntimeError):
        client.get('/fail')


def test_log_endpoint_with_invalid_signature_returns_403(client: 'FlaskClient') -> None:
    """Test that /log endpoint returns 403 for invalid signature."""
    response = client.post('/log', data={'text': 'test message', 'user_id': 'U123456789', 'timestamp': '1234567890'})
    assert response.status_code == 403


def test_log_endpoint_with_valid_signature_returns_200(client: 'FlaskClient') -> None:
    """Test that /log endpoint returns 200 for valid signature."""
    import hashlib
    import hmac
    import os

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret

    # Create test request data
    request_body = 'text=test+message&user_id=U123456789&timestamp=1234567890'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Make request with valid signature
    response = client.post(
        '/log',
        data=request_body,
        headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
        content_type='application/x-www-form-urlencoded',
    )

    assert response.status_code == 200
    assert response.get_data(as_text=True) == 'Logged'


def test_log_endpoint_stores_entry_with_valid_signature(client: 'FlaskClient') -> None:
    """Test that /log endpoint stores log entry when signature is valid."""
    import hashlib
    import hmac
    import os
    from unittest.mock import MagicMock, patch

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret

    # Create test request data
    request_body = 'text=Debugged+deploy+script&user_id=U123456789&timestamp=1234567890'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Mock the log store
    mock_store = MagicMock()

    with patch('companion_memory.app.get_log_store', return_value=mock_store):
        # Make request with valid signature
        response = client.post(
            '/log',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response
        assert response.status_code == 200
        assert 'Logged' in response.get_data(as_text=True)

        # Verify log store was called
        mock_store.write_log.assert_called_once()
        call_args = mock_store.write_log.call_args
        assert call_args[1]['user_id'] == 'U123456789'
        assert call_args[1]['text'] == 'Debugged deploy script'
        assert call_args[1]['timestamp'] is not None
        assert call_args[1]['log_id'] is not None


def test_log_endpoint_handles_sampling_responses(client: 'FlaskClient') -> None:
    """Test that /log endpoint handles sampling responses like manual logs."""
    import hashlib
    import hmac
    import os
    from unittest.mock import MagicMock, patch

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret

    # Create test request data for a sampling response
    request_body = 'text=Working+on+debugging+the+API&user_id=U123456789&timestamp=1234567890'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Mock the log store
    mock_store = MagicMock()

    with patch('companion_memory.app.get_log_store', return_value=mock_store):
        # Make request with valid signature (simulating user response to sampling prompt)
        response = client.post(
            '/log',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response
        assert response.status_code == 200
        assert 'Logged' in response.get_data(as_text=True)

        # Verify log store was called with sampling response
        mock_store.write_log.assert_called_once()
        call_args = mock_store.write_log.call_args
        assert call_args[1]['user_id'] == 'U123456789'
        assert call_args[1]['text'] == 'Working on debugging the API'
        assert call_args[1]['timestamp'] is not None
        assert call_args[1]['log_id'] is not None
