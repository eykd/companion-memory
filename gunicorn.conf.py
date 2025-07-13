"""Gunicorn configuration file."""

import logging


class HealthCheckFilter(logging.Filter):
    """Filter to exclude health check requests (/) from access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log records to exclude health check requests.

        Args:
            record: Log record to filter

        Returns:
            True if record should be logged, False to filter it out

        """
        # Filter out requests to the root path "/"
        return not (
            hasattr(record, 'args')
            and record.args is not None
            and isinstance(record.args, tuple)
            and len(record.args) >= 1
            and isinstance(record.args[0], str)
            and '"GET / HTTP' in record.args[0]
        )


def when_ready(server: object) -> None:  # noqa: ARG001
    """Configure logging when server is ready.

    Args:
        server: Gunicorn server instance (unused but required by gunicorn)

    """
    # Get the gunicorn access logger
    access_logger = logging.getLogger('gunicorn.access')

    # Add our health check filter
    access_logger.addFilter(HealthCheckFilter())


# Gunicorn configuration
bind = ':8000'
workers = 2
access_logfile = '-'
error_logfile = '-'
