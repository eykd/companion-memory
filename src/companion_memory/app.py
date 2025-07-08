"""Flask web application for webhook handling."""

import uuid
from datetime import UTC, datetime
from urllib.parse import parse_qs

from flask import Flask, request

from companion_memory.slack_auth import validate_slack_signature
from companion_memory.storage import LogStore, MemoryLogStore


def get_log_store() -> LogStore:
    """Get the log store instance.

    Returns:
        LogStore instance (currently returns MemoryLogStore for testing)

    """
    return MemoryLogStore()


def create_app() -> Flask:
    """Create and configure the Flask application.

    Returns:
        Configured Flask application instance

    """
    app = Flask(__name__)

    @app.route('/')
    def healthcheck() -> str:
        """Health check endpoint.

        Returns:
            Simple success message

        """
        return 'OK'

    @app.route('/fail')
    def fail() -> str:
        """Fail endpoint.

        Returns:
            Always raises an exception

        """
        raise RuntimeError('Test exception')

    @app.route('/slack/log', methods=['POST'])
    def log_entry() -> tuple[str, int]:
        """Handle Slack /log command.

        Returns:
            Response tuple with message and status code

        """
        # Get signature validation headers
        timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
        signature = request.headers.get('X-Slack-Signature', '')

        # Validate signature
        if not validate_slack_signature(request.get_data(), timestamp, signature):
            return 'Invalid signature', 403

        # Parse the request data
        request_data = parse_qs(request.get_data(as_text=True))

        # Extract log entry data
        text = request_data.get('text', [''])[0]
        user_id = request_data.get('user_id', [''])[0]

        # Create log entry
        log_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        # Store the log entry
        log_store = get_log_store()
        log_store.write_log(user_id=user_id, timestamp=timestamp, text=text, log_id=log_id)

        return 'Logged', 200

    @app.route('/slack/events', methods=['POST'])
    def slack_events() -> tuple[str, int]:
        """Handle Slack events webhook.

        Returns:
            Response tuple with empty message and status code

        """
        # Get signature validation headers
        timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
        signature = request.headers.get('X-Slack-Signature', '')

        # Validate signature
        if not validate_slack_signature(request.get_data(), timestamp, signature):
            return 'Invalid signature', 403

        # No-op: do nothing with the event data
        return '', 200

    return app
