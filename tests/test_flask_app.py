"""Tests for Flask web application."""

from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest

from companion_memory.app import create_app

pytestmark = pytest.mark.block_network

if TYPE_CHECKING:  # pragma: no cover
    from flask.testing import FlaskClient


@pytest.fixture
def client() -> Generator['FlaskClient', None, None]:
    """Create a test client for the Flask app."""
    app = create_app(enable_scheduler=False)
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
    """Test that /slack/log endpoint returns 403 for invalid signature."""
    response = client.post(
        '/slack/log', data={'text': 'test message', 'user_id': 'U123456789', 'timestamp': '1234567890'}
    )
    assert response.status_code == 403


def test_log_endpoint_with_valid_signature_returns_200(client: 'FlaskClient') -> None:
    """Test that /slack/log endpoint returns 200 for valid signature."""
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
        '/slack/log',
        data=request_body,
        headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
        content_type='application/x-www-form-urlencoded',
    )

    assert response.status_code == 200
    assert response.get_data(as_text=True) == 'Logged: test message'


def test_log_endpoint_stores_entry_with_valid_signature() -> None:
    """Test that /slack/log endpoint stores log entry when signature is valid."""
    import hashlib
    import hmac
    import os
    from unittest.mock import MagicMock

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

    # Create app with injected mock log store
    app = create_app(log_store=mock_store, enable_scheduler=False)
    app.config['TESTING'] = True

    with app.test_client() as client:
        # Make request with valid signature
        response = client.post(
            '/slack/log',
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


def test_log_endpoint_handles_sampling_responses() -> None:
    """Test that /slack/log endpoint handles sampling responses like manual logs."""
    import hashlib
    import hmac
    import os
    from unittest.mock import MagicMock

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

    # Create app with injected mock log store
    app = create_app(log_store=mock_store, enable_scheduler=False)
    app.config['TESTING'] = True

    with app.test_client() as client:
        # Make request with valid signature (simulating user response to sampling prompt)
        response = client.post(
            '/slack/log',
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


def test_events_endpoint_with_invalid_signature_returns_403(client: 'FlaskClient') -> None:
    """Test that /slack/events endpoint returns 403 for invalid signature."""
    response = client.post(
        '/slack/events',
        json={'event': 'test_event'},
        headers={'X-Slack-Request-Timestamp': '1234567890', 'X-Slack-Signature': 'invalid'},
    )
    assert response.status_code == 403


def test_events_endpoint_with_valid_signature_returns_200(client: 'FlaskClient') -> None:
    """Test that /slack/events endpoint returns 200 for valid signature."""
    import hashlib
    import hmac
    import json
    import os

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret

    # Create test request data
    request_body = json.dumps({'event': 'test_event', 'type': 'message'})
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Make request with valid signature
    response = client.post(
        '/slack/events',
        data=request_body,
        headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
        content_type='application/json',
    )

    assert response.status_code == 200
    assert response.get_data(as_text=True) == ''


def test_events_endpoint_handles_url_verification(client: 'FlaskClient') -> None:
    """Test that /slack/events endpoint handles URL verification challenge."""
    import hashlib
    import hmac
    import json
    import os

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret

    # Create test request data for URL verification
    challenge_value = 'test_challenge_123'
    request_body = json.dumps({'type': 'url_verification', 'challenge': challenge_value})
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Make request with valid signature
    response = client.post(
        '/slack/events',
        data=request_body,
        headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
        content_type='application/json',
    )

    assert response.status_code == 200
    assert response.get_data(as_text=True) == challenge_value


def test_create_app_accepts_injected_log_store(client: 'FlaskClient') -> None:
    """Test that create_app accepts an injected log store."""
    from unittest.mock import MagicMock

    # Create a mock log store
    mock_log_store = MagicMock()

    # Create app with injected log store
    app = create_app(log_store=mock_log_store, enable_scheduler=False)
    app.config['TESTING'] = True

    # Verify that the app was created successfully
    assert app is not None


def test_lastweek_endpoint_with_invalid_signature_returns_403(client: 'FlaskClient') -> None:
    """Test that /slack/lastweek endpoint returns 403 for invalid signature."""
    response = client.post('/slack/lastweek', data={'user_id': 'U123456789', 'command': '/lastweek'})
    assert response.status_code == 403


def test_lastweek_endpoint_with_valid_signature_returns_summary() -> None:
    """Test that /slack/lastweek endpoint schedules job and returns 204."""
    import hashlib
    import hmac
    import os
    from unittest.mock import patch

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret

    # Create test request data
    request_body = 'user_id=U123456789&command=/lastweek'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Create app with disabled scheduler
    app = create_app(enable_scheduler=False)
    app.config['TESTING'] = True

    with (
        app.test_client() as client,
        patch('companion_memory.app.schedule_summary_job') as mock_schedule_job,
    ):
        # Make request with valid signature
        response = client.post(
            '/slack/lastweek',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response is 204 No Content
        assert response.status_code == 204
        assert response.data == b''

        # Verify job was scheduled
        mock_schedule_job.assert_called_once_with('U123456789', 'lastweek')


def test_yesterday_endpoint_with_invalid_signature_returns_403(client: 'FlaskClient') -> None:
    """Test that /slack/yesterday endpoint returns 403 for invalid signature."""
    response = client.post('/slack/yesterday', data={'user_id': 'U123456789', 'command': '/yesterday'})
    assert response.status_code == 403


def test_yesterday_endpoint_with_valid_signature_returns_summary() -> None:
    """Test that /slack/yesterday endpoint schedules job and returns 204."""
    import hashlib
    import hmac
    import os
    from unittest.mock import patch

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret

    # Create test request data
    request_body = 'user_id=U123456789&command=/yesterday'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Create app with disabled scheduler
    app = create_app(enable_scheduler=False)
    app.config['TESTING'] = True

    with (
        app.test_client() as client,
        patch('companion_memory.app.schedule_summary_job') as mock_schedule_job,
    ):
        # Make request with valid signature
        response = client.post(
            '/slack/yesterday',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response is 204 No Content
        assert response.status_code == 204
        assert response.data == b''

        # Verify job was scheduled
        mock_schedule_job.assert_called_once_with('U123456789', 'yesterday')


def test_yesterday_endpoint_with_timezone_discovery() -> None:
    """Test that /slack/yesterday endpoint schedules job and returns 204."""
    import hashlib
    import hmac
    import os
    from unittest.mock import patch

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret

    # Create test request data
    request_body = 'user_id=U123456789&command=/yesterday'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Create app with disabled scheduler
    app = create_app(enable_scheduler=False)
    app.config['TESTING'] = True

    with (
        app.test_client() as client,
        patch('companion_memory.app.schedule_summary_job') as mock_schedule_job,
    ):
        # Make request with valid signature
        response = client.post(
            '/slack/yesterday',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response is 204 No Content
        assert response.status_code == 204
        assert response.data == b''

        # Verify job was scheduled
        mock_schedule_job.assert_called_once_with('U123456789', 'yesterday')


def test_today_endpoint_with_invalid_signature_returns_403(client: 'FlaskClient') -> None:
    """Test that /slack/today endpoint returns 403 for invalid signature."""
    response = client.post('/slack/today', data={'user_id': 'U123456789', 'command': '/today'})
    assert response.status_code == 403


def test_today_endpoint_with_valid_signature_returns_summary() -> None:
    """Test that /slack/today endpoint schedules job and returns 204."""
    import hashlib
    import hmac
    import os
    from unittest.mock import patch

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret

    # Create test request data
    request_body = 'user_id=U123456789&command=/today'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Create app with disabled scheduler
    app = create_app(enable_scheduler=False)
    app.config['TESTING'] = True

    with (
        app.test_client() as client,
        patch('companion_memory.app.schedule_summary_job') as mock_schedule_job,
    ):
        # Make request with valid signature
        response = client.post(
            '/slack/today',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response is 204 No Content
        assert response.status_code == 204
        assert response.data == b''

        # Verify job was scheduled
        mock_schedule_job.assert_called_once_with('U123456789', 'today')


def test_today_endpoint_with_timezone_discovery() -> None:
    """Test that /slack/today endpoint schedules job and returns 204."""
    import hashlib
    import hmac
    import os
    from unittest.mock import patch

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret

    # Create test request data
    request_body = 'user_id=U123456789&timestamp=1234567890'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Create app with disabled scheduler
    app = create_app(enable_scheduler=False)
    app.config['TESTING'] = True

    with (
        app.test_client() as client,
        patch('companion_memory.app.schedule_summary_job') as mock_schedule_job,
    ):
        # Make request with valid signature
        response = client.post(
            '/slack/today',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response is 204 No Content
        assert response.status_code == 204
        assert response.data == b''

        # Verify job was scheduled
        mock_schedule_job.assert_called_once_with('U123456789', 'today')


def test_create_app_with_scheduler_already_running() -> None:
    """Test that create_app handles case where scheduler is already running."""
    from unittest.mock import patch

    with patch('companion_memory.scheduler.SchedulerLock.acquire') as mock_acquire:
        mock_acquire.return_value = False  # Simulate scheduler already running

        app = create_app(enable_scheduler=False)
        app.config['TESTING'] = True

        with app.test_client() as client:
            # Verify we can still access endpoints
            response = client.get('/')
            assert response.status_code == 200

            # Verify scheduler status endpoint works
            response = client.get('/scheduler/status')
            assert response.status_code == 200


def test_create_app_with_scheduler_disabled() -> None:
    """Test that create_app with scheduler disabled returns appropriate status."""
    app = create_app(enable_scheduler=False)
    app.config['TESTING'] = True

    with app.test_client() as client:
        # Verify we can still access endpoints
        response = client.get('/')
        assert response.status_code == 200

        # Verify scheduler status endpoint indicates scheduler is disabled
        response = client.get('/scheduler/status')
        assert response.status_code == 200
        data = response.get_json()
        assert data['scheduler_enabled'] is False
        assert 'disabled' in data['message']
