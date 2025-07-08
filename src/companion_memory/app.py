"""Flask web application for webhook handling."""

from flask import Flask


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

    return app
