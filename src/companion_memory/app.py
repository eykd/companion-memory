"""Flask web application for webhook handling."""

import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs

from flask import Flask, request

from companion_memory.scheduler import get_scheduler
from companion_memory.slack_auth import validate_slack_signature
from companion_memory.storage import LogStore, MemoryLogStore
from companion_memory.summarizer import LLMClient, summarize_today, summarize_week, summarize_yesterday


def get_log_store() -> LogStore:
    """Get the log store instance.

    Returns:
        LogStore instance (currently returns MemoryLogStore for testing)

    """
    return MemoryLogStore()


def create_app(
    log_store: LogStore | None = None, llm: LLMClient | None = None, *, enable_scheduler: bool = True
) -> Flask:
    """Create and configure the Flask application.

    Args:
        log_store: Optional log store instance to inject. If None, uses default.
        llm: Optional LLM client instance to inject. If None, uses default.
        enable_scheduler: Whether to start the distributed scheduler. Defaults to True.

    Returns:
        Configured Flask application instance

    """
    app = Flask(__name__)

    # Use injected log store or fall back to default
    if log_store is None:
        log_store = get_log_store()

    # Initialize distributed scheduler (coordinates across workers/containers via DynamoDB)
    if enable_scheduler:
        scheduler = get_scheduler()
        # Configure dependencies for scheduled jobs (if available)
        if llm is not None:
            scheduler.configure_dependencies(log_store, llm)
        scheduler.start()  # Always starts successfully - workers compete for DynamoDB lock
        app.logger.info('Distributed scheduler infrastructure started - competing for lock')

        # Add scheduled jobs here

        # Register cleanup on app teardown
        @app.teardown_appcontext  # type: ignore[type-var]
        def cleanup_scheduler(exc: Exception | None) -> None:  # noqa: ARG001
            scheduler.shutdown()

    else:
        app.logger.info('Scheduler disabled by configuration')

    @app.route('/')
    def healthcheck() -> str:
        """Health check endpoint.

        Returns:
            Simple success message

        """
        return 'OK'

    @app.route('/scheduler/status')
    def scheduler_status() -> dict[str, Any]:
        """Get scheduler status for monitoring.

        Returns:
            JSON with scheduler status information

        """
        if enable_scheduler:
            scheduler = get_scheduler()
            return scheduler.get_status()
        return {'scheduler_enabled': False, 'message': 'Scheduler disabled by configuration'}

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

    @app.route('/slack/today', methods=['POST'])
    def today_summary() -> tuple[str, int]:
        """Handle Slack /today command.

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

        # Generate today summary
        if llm is None:
            return 'LLM not configured', 500

        summary = summarize_today(user_id=user_id, log_store=log_store, llm=llm)

        return summary, 200

    return app
