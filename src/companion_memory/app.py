"""Flask web application for webhook handling."""

from flask import Flask, request

from companion_memory.slack_auth import validate_slack_signature


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

    @app.route('/log', methods=['POST'])
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

        # For now, just return success
        return 'OK', 200

    return app
