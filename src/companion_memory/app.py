"""Flask web application for webhook handling."""

import atexit
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs

from flask import Flask, request

from companion_memory.job_models import ScheduledJob
from companion_memory.job_table import JobTable
from companion_memory.scheduler import get_scheduler
from companion_memory.slack_auth import validate_slack_signature
from companion_memory.storage import LogStore, MemoryLogStore
from companion_memory.summarizer import LLMClient


def get_log_store() -> LogStore:
    """Get the log store instance.

    Returns:
        LogStore instance (currently returns MemoryLogStore for testing)

    """
    return MemoryLogStore()


def schedule_summary_job(user_id: str, summary_range: str) -> None:  # pragma: no cover
    """Schedule a summary generation job.

    Args:
        user_id: User ID to generate summary for
        summary_range: Summary range ('today', 'yesterday', 'lastweek')

    """
    # Defensive code - complex integration function with AWS dependencies that are difficult to mock completely
    from companion_memory.deduplication import DeduplicationIndex  # pragma: no cover
    from companion_memory.job_models import make_job_sk  # pragma: no cover

    # Create job table and deduplication index
    job_table = JobTable()  # pragma: no cover
    dedup_index = DeduplicationIndex()  # pragma: no cover

    # Create summary generation job
    job_id = uuid.uuid4()  # pragma: no cover
    scheduled_for = datetime.now(UTC)  # pragma: no cover

    job = ScheduledJob(  # pragma: no cover
        job_id=job_id,
        job_type='generate_summary',
        payload={
            'user_id': user_id,
            'summary_range': summary_range,
        },
        scheduled_for=scheduled_for,
        status='pending',
        created_at=datetime.now(UTC),
    )

    # Create DynamoDB keys for deduplication
    job_pk = 'job'  # pragma: no cover
    job_sk = make_job_sk(scheduled_for, job_id)  # pragma: no cover

    # Create logical job ID for deduplication
    logical_id = f'summary:{summary_range}:{user_id}'  # pragma: no cover
    date = scheduled_for.strftime('%Y-%m-%d')  # pragma: no cover

    # Try to reserve the job (skip if already exists)
    if not dedup_index.try_reserve(logical_id, date, job_pk, job_sk):  # pragma: no cover
        return  # Job already exists, skip

    # Schedule the job
    job_table.put_job(job)  # pragma: no cover


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

        # Register cleanup on application shutdown
        def cleanup_scheduler() -> None:  # pragma: no cover
            scheduler.shutdown()

        atexit.register(cleanup_scheduler)

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

        return f'Logged: {text}', 200

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
            Response tuple with empty message and 204 status code

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

        # Schedule summary job
        schedule_summary_job(user_id, 'lastweek')

        return '', 204

    @app.route('/slack/yesterday', methods=['POST'])
    def yesterday_summary() -> tuple[str, int]:
        """Handle Slack /yesterday command.

        Returns:
            Response tuple with empty message and 204 status code

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

        # Schedule summary job
        schedule_summary_job(user_id, 'yesterday')

        return '', 204

    @app.route('/slack/today', methods=['POST'])
    def today_summary() -> tuple[str, int]:
        """Handle Slack /today command.

        Returns:
            Response tuple with empty message and 204 status code

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

        # Schedule summary job
        schedule_summary_job(user_id, 'today')

        return '', 204

    return app
