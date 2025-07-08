"""Slack authentication and signature validation."""

import hashlib
import hmac
import os


def validate_slack_signature(
    request_body: bytes,
    request_timestamp: str,
    request_signature: str,
    signing_secret: str | None = None,
) -> bool:
    """Validate Slack request signature.

    Args:
        request_body: Raw request body bytes
        request_timestamp: X-Slack-Request-Timestamp header value
        request_signature: X-Slack-Signature header value
        signing_secret: Slack signing secret (defaults to env var)

    Returns:
        True if signature is valid, False otherwise

    """
    if signing_secret is None:
        signing_secret = os.environ.get('SLACK_SIGNING_SECRET')

    if not signing_secret:
        return False

    # Create the signature base string
    sig_basestring = f'v0:{request_timestamp}:{request_body.decode("utf-8")}'

    # Create the signature
    expected_signature = (
        'v0=' + hmac.new(signing_secret.encode('utf-8'), sig_basestring.encode('utf-8'), hashlib.sha256).hexdigest()
    )

    # Compare signatures securely
    return hmac.compare_digest(expected_signature, request_signature)
