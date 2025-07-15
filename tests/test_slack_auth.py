"""Tests for Slack authentication functionality."""

import hashlib
import hmac
import os

import pytest

from companion_memory.slack_auth import validate_slack_signature

pytestmark = pytest.mark.block_network


def test_validate_slack_signature_with_valid_signature() -> None:
    """Test that validate_slack_signature returns True for valid signature."""
    request_body = b'token=test&text=hello'
    request_timestamp = '1234567890'
    signing_secret = 'test_secret'  # noqa: S105

    # Create valid signature
    sig_basestring = f'v0:{request_timestamp}:{request_body.decode("utf-8")}'
    expected_signature = (
        'v0=' + hmac.new(signing_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    result = validate_slack_signature(request_body, request_timestamp, expected_signature, signing_secret)
    assert result is True


def test_validate_slack_signature_with_invalid_signature() -> None:
    """Test that validate_slack_signature returns False for invalid signature."""
    request_body = b'token=test&text=hello'
    request_timestamp = '1234567890'
    signing_secret = 'test_secret'  # noqa: S105
    invalid_signature = 'v0=invalid_signature'

    result = validate_slack_signature(request_body, request_timestamp, invalid_signature, signing_secret)
    assert result is False


def test_validate_slack_signature_missing_signing_secret_env() -> None:
    """Test that validate_slack_signature returns False when signing secret is missing from env."""
    request_body = b'token=test&text=hello'
    request_timestamp = '1234567890'
    invalid_signature = 'v0=some_signature'

    # Make sure SLACK_SIGNING_SECRET is not set
    original_secret = os.environ.get('SLACK_SIGNING_SECRET')
    if 'SLACK_SIGNING_SECRET' in os.environ:
        del os.environ['SLACK_SIGNING_SECRET']

    try:
        result = validate_slack_signature(request_body, request_timestamp, invalid_signature)
        assert result is False
    finally:
        # Restore original secret
        if original_secret is not None:
            os.environ['SLACK_SIGNING_SECRET'] = original_secret


def test_validate_slack_signature_from_env_var() -> None:
    """Test that validate_slack_signature uses env var when signing_secret is None."""
    request_body = b'token=test&text=hello'
    request_timestamp = '1234567890'
    signing_secret = 'test_secret_from_env'  # noqa: S105

    # Set env var
    os.environ['SLACK_SIGNING_SECRET'] = signing_secret

    try:
        # Create valid signature
        sig_basestring = f'v0:{request_timestamp}:{request_body.decode("utf-8")}'
        expected_signature = (
            'v0=' + hmac.new(signing_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
        )

        # Test with signing_secret=None (should use env var)
        result = validate_slack_signature(request_body, request_timestamp, expected_signature, None)
        assert result is True
    finally:
        # Clean up
        if 'SLACK_SIGNING_SECRET' in os.environ:
            del os.environ['SLACK_SIGNING_SECRET']
