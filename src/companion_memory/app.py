"""Flask web application for webhook handling."""

import uuid
from datetime import UTC, datetime
from urllib.parse import parse_qs

from flask import Flask, request

from companion_memory.slack_auth import validate_slack_signature
from companion_memory.storage import LogStore, MemoryLogStore
from companion_memory.summarizer import LLMClient, summarize_week, summarize_yesterday


def get_log_store() -> LogStore:
    """Get the log store instance.

    Returns:
        LogStore instance (currently returns MemoryLogStore for testing)

    """
    return MemoryLogStore()


def create_app(log_store: LogStore | None = None, llm: LLMClient | None = None) -> Flask:  # noqa: C901
    """Create and configure the Flask application.

    Args:
        log_store: Optional log store instance to inject. If None, uses default.
        llm: Optional LLM client instance to inject. If None, uses default.

    Returns:
        Configured Flask application instance

    """
    app = Flask(__name__)

    # Use injected log store or fall back to default
    if log_store is None:
        log_store = get_log_store()

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

        # Parse the request data
        request_data = request.get_json()

        # Handle URL verification
        if request_data and request_data.get('type') == 'url_verification':
            challenge = request_data.get('challenge', '')
            return challenge, 200

        # No-op: do nothing with other event data
        return '', 200

    @app.route('/slack/lastweek', methods=['POST'])
    def lastweek_summary() -> tuple[str, int]:
        """Handle Slack /lastweek command.

        Returns:
            Response tuple with summary message and status code

        """
        # Get signature validation headers
        timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
        signature = request.headers.get('X-Slack-Signature', '')

        # Validate signature
        if not validate_slack_signature(request.get_data(), timestamp, signature):
            return 'Invalid signature', 403

        # Parse the request data
        request_data = parse_qs(request.get_data(as_text=True))

        # Extract user ID
        user_id = request_data.get('user_id', [''])[0]

        # Generate weekly summary
        if llm is None:
            return 'LLM not configured', 500

        summary = summarize_week(user_id=user_id, log_store=log_store, llm=llm)

        return summary, 200

    @app.route('/slack/yesterday', methods=['POST'])
    def yesterday_summary() -> tuple[str, int]:
        """Handle Slack /yesterday command.

        Returns:
            Response tuple with summary message and status code

        """
        # Get signature validation headers
        timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
        signature = request.headers.get('X-Slack-Signature', '')

        # Validate signature
        if not validate_slack_signature(request.get_data(), timestamp, signature):
            return 'Invalid signature', 403

        # Parse the request data
        request_data = parse_qs(request.get_data(as_text=True))

        # Extract user ID
        user_id = request_data.get('user_id', [''])[0]

        # Generate yesterday summary
        if llm is None:
            return 'LLM not configured', 500

        summary = summarize_yesterday(user_id=user_id, log_store=log_store, llm=llm)

        return summary, 200

    return app
