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
    assert response.get_data(as_text=True) == 'Logged'


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
    app = create_app(log_store=mock_store)
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
    app = create_app(log_store=mock_store)
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
    app = create_app(log_store=mock_log_store)
    app.config['TESTING'] = True

    # Verify that the app was created successfully
    assert app is not None


def test_lastweek_endpoint_with_invalid_signature_returns_403(client: 'FlaskClient') -> None:
    """Test that /slack/lastweek endpoint returns 403 for invalid signature."""
    response = client.post('/slack/lastweek', data={'user_id': 'U123456789', 'command': '/lastweek'})
    assert response.status_code == 403


def test_lastweek_endpoint_with_valid_signature_returns_summary() -> None:
    """Test that /slack/lastweek endpoint returns weekly summary for valid signature."""
    import hashlib
    import hmac
    import os
    from unittest.mock import MagicMock

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

    # Mock the dependencies
    mock_log_store = MagicMock()
    mock_llm = MagicMock()
    mock_llm.complete.return_value = 'This week you focused on testing, debugging, and code review activities.'

    # Create app with injected dependencies
    app = create_app(log_store=mock_log_store, llm=mock_llm)
    app.config['TESTING'] = True

    with app.test_client() as client:
        # Make request with valid signature
        response = client.post(
            '/slack/lastweek',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response
        assert response.status_code == 200
        assert 'This week you focused on testing, debugging, and code review activities.' in response.get_data(
            as_text=True
        )

        # Verify log store was called to fetch logs
        mock_log_store.fetch_logs.assert_called_once()

        # Verify LLM was called to generate summary
        mock_llm.complete.assert_called_once()


def test_lastweek_endpoint_with_no_llm_returns_500() -> None:
    """Test that /slack/lastweek endpoint returns 500 when LLM is not configured."""
    import hashlib
    import hmac
    import os
    from unittest.mock import MagicMock

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

    # Mock the log store (but no LLM)
    mock_log_store = MagicMock()

    # Create app with log store but no LLM
    app = create_app(log_store=mock_log_store, llm=None)
    app.config['TESTING'] = True

    with app.test_client() as client:
        # Make request with valid signature
        response = client.post(
            '/slack/lastweek',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response
        assert response.status_code == 500
        assert 'LLM not configured' in response.get_data(as_text=True)


def test_yesterday_endpoint_with_invalid_signature_returns_403(client: 'FlaskClient') -> None:
    """Test that /slack/yesterday endpoint returns 403 for invalid signature."""
    response = client.post('/slack/yesterday', data={'user_id': 'U123456789', 'command': '/yesterday'})
    assert response.status_code == 403


def test_yesterday_endpoint_with_valid_signature_returns_summary() -> None:
    """Test that /slack/yesterday endpoint returns yesterday's summary for valid signature."""
    import hashlib
    import hmac
    import os
    from unittest.mock import MagicMock, patch

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret
    os.environ['SLACK_BOT_TOKEN'] = 'test-bot-token'  # noqa: S105

    # Create test request data
    request_body = 'user_id=U123456789&command=/yesterday'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Mock the dependencies
    mock_log_store = MagicMock()
    mock_llm = MagicMock()
    mock_llm.complete.return_value = 'Yesterday you focused on reviewing pull requests and fixing bugs.'

    # Mock Slack client
    mock_slack_client = MagicMock()
    mock_slack_client.users_info.return_value = {'ok': True, 'user': {'tz': 'America/New_York', 'tz_offset': -18000}}

    # Create app with injected dependencies
    app = create_app(log_store=mock_log_store, llm=mock_llm)
    app.config['TESTING'] = True

    with (
        app.test_client() as client,
        patch('companion_memory.summarizer._get_user_timezone') as mock_get_tz,
    ):
        import zoneinfo

        mock_get_tz.return_value = zoneinfo.ZoneInfo('America/New_York')

        # Make request with valid signature
        response = client.post(
            '/slack/yesterday',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response
        assert response.status_code == 200
        assert 'Yesterday you focused on reviewing pull requests and fixing bugs.' in response.get_data(as_text=True)

        # Verify log store was called to fetch logs
        mock_log_store.fetch_logs.assert_called_once()

        # Verify LLM was called to generate summary
        mock_llm.complete.assert_called_once()

        # Verify timezone function was called
        mock_get_tz.assert_called_once_with('U123456789')


def test_yesterday_endpoint_with_no_llm_returns_500() -> None:
    """Test that /slack/yesterday endpoint returns 500 when LLM is not configured."""
    import hashlib
    import hmac
    import os
    from unittest.mock import MagicMock

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret
    os.environ['SLACK_BOT_TOKEN'] = 'test-bot-token'  # noqa: S105

    # Create test request data
    request_body = 'user_id=U123456789&command=/yesterday'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Mock the log store (but no LLM)
    mock_log_store = MagicMock()

    # Create app with log store but no LLM
    app = create_app(log_store=mock_log_store, llm=None)
    app.config['TESTING'] = True

    with app.test_client() as client:
        # Make request with valid signature
        response = client.post(
            '/slack/yesterday',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response
        assert response.status_code == 500
        assert 'LLM not configured' in response.get_data(as_text=True)


def test_yesterday_endpoint_with_timezone_discovery() -> None:
    """Test that /slack/yesterday endpoint discovers user timezone and calculates yesterday properly."""
    import hashlib
    import hmac
    import os
    from unittest.mock import MagicMock, patch

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret
    os.environ['SLACK_BOT_TOKEN'] = 'test-bot-token'  # noqa: S105

    # Create test request data
    request_body = 'user_id=U123456789&command=/yesterday'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Mock Slack client for timezone discovery
    mock_slack_client = MagicMock()
    mock_slack_client.users_info.return_value = {'ok': True, 'user': {'tz': 'America/New_York', 'tz_offset': -18000}}

    # Mock the dependencies
    mock_log_store = MagicMock()
    mock_llm = MagicMock()
    mock_llm.complete.return_value = 'Yesterday you focused on timezone handling and date calculations.'

    # Create app with injected dependencies
    app = create_app(log_store=mock_log_store, llm=mock_llm)
    app.config['TESTING'] = True

    with (
        app.test_client() as client,
        patch('companion_memory.summarizer._get_user_timezone') as mock_get_tz,
    ):
        import zoneinfo

        mock_get_tz.return_value = zoneinfo.ZoneInfo('America/New_York')

        # Make request with valid signature
        response = client.post(
            '/slack/yesterday',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response
        assert response.status_code == 200
        assert 'Yesterday you focused on timezone handling and date calculations.' in response.get_data(as_text=True)

        # Verify timezone function was called
        mock_get_tz.assert_called_once_with('U123456789')

        # Verify log store was called to fetch logs
        mock_log_store.fetch_logs.assert_called_once()

        # Verify LLM was called to generate summary
        mock_llm.complete.assert_called_once()


def test_today_endpoint_with_invalid_signature_returns_403(client: 'FlaskClient') -> None:
    """Test that /slack/today endpoint returns 403 for invalid signature."""
    response = client.post('/slack/today', data={'user_id': 'U123456789', 'command': '/today'})
    assert response.status_code == 403


def test_today_endpoint_with_valid_signature_returns_summary() -> None:
    """Test that /slack/today endpoint returns today's summary for valid signature."""
    import hashlib
    import hmac
    import os
    from unittest.mock import MagicMock, patch

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret
    os.environ['SLACK_BOT_TOKEN'] = 'test-bot-token'  # noqa: S105

    # Create test request data
    request_body = 'user_id=U123456789&command=/today'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Mock the dependencies
    mock_log_store = MagicMock()
    mock_llm = MagicMock()
    mock_llm.complete.return_value = 'Today you are focusing on implementing new features and testing.'

    # Create app with injected dependencies
    app = create_app(log_store=mock_log_store, llm=mock_llm)
    app.config['TESTING'] = True

    with (
        app.test_client() as client,
        patch('companion_memory.summarizer._get_user_timezone') as mock_get_tz,
    ):
        import zoneinfo

        mock_get_tz.return_value = zoneinfo.ZoneInfo('America/New_York')

        # Make request with valid signature
        response = client.post(
            '/slack/today',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response
        assert response.status_code == 200
        assert 'Today you are focusing on implementing new features and testing.' in response.get_data(as_text=True)

        # Verify log store was called to fetch logs
        mock_log_store.fetch_logs.assert_called_once()

        # Verify LLM was called to generate summary
        mock_llm.complete.assert_called_once()

        # Verify timezone function was called
        mock_get_tz.assert_called_once_with('U123456789')


def test_today_endpoint_with_no_llm_returns_500() -> None:
    """Test that /slack/today endpoint returns 500 when LLM is not configured."""
    import hashlib
    import hmac
    import os
    from unittest.mock import MagicMock

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret
    os.environ['SLACK_BOT_TOKEN'] = 'test-bot-token'  # noqa: S105

    # Create test request data
    request_body = 'user_id=U123456789&command=/today'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Mock the log store (but no LLM)
    mock_log_store = MagicMock()

    # Create app with log store but no LLM
    app = create_app(log_store=mock_log_store, llm=None)
    app.config['TESTING'] = True

    with app.test_client() as client:
        # Make request with valid signature
        response = client.post(
            '/slack/today',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response
        assert response.status_code == 500
        assert 'LLM not configured' in response.get_data(as_text=True)


def test_today_endpoint_with_timezone_discovery() -> None:
    """Test that /slack/today endpoint discovers user timezone and calculates today properly."""
    import hashlib
    import hmac
    import os
    from unittest.mock import MagicMock, patch

    # Set up test environment
    test_secret = 'test_secret'  # noqa: S105
    os.environ['SLACK_SIGNING_SECRET'] = test_secret
    os.environ['SLACK_BOT_TOKEN'] = 'test-bot-token'  # noqa: S105

    # Create test request data
    request_body = 'user_id=U123456789&command=/today'
    request_timestamp = '1234567890'

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body}'
    expected_signature = (
        'v0=' + hmac.new(test_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Mock the dependencies
    mock_log_store = MagicMock()
    mock_llm = MagicMock()
    mock_llm.complete.return_value = 'Today you are working on timezone handling and feature implementation.'

    # Create app with injected dependencies
    app = create_app(log_store=mock_log_store, llm=mock_llm)
    app.config['TESTING'] = True

    with (
        app.test_client() as client,
        patch('companion_memory.summarizer._get_user_timezone') as mock_get_tz,
    ):
        import zoneinfo

        mock_get_tz.return_value = zoneinfo.ZoneInfo('America/New_York')

        # Make request with valid signature
        response = client.post(
            '/slack/today',
            data=request_body,
            headers={'X-Slack-Request-Timestamp': request_timestamp, 'X-Slack-Signature': expected_signature},
            content_type='application/x-www-form-urlencoded',
        )

        # Verify response
        assert response.status_code == 200
        assert 'Today you are working on timezone handling and feature implementation.' in response.get_data(
            as_text=True
        )

        # Verify timezone function was called
        mock_get_tz.assert_called_once_with('U123456789')

        # Verify log store was called to fetch logs
        mock_log_store.fetch_logs.assert_called_once()

        # Verify LLM was called to generate summary
        mock_llm.complete.assert_called_once()
