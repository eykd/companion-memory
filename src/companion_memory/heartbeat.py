"""Heartbeat diagnostic functionality."""

import os


def is_heartbeat_enabled() -> bool:
    """Check if heartbeat feature is enabled via ENABLE_HEARTBEAT environment variable.

    Returns:
        True if ENABLE_HEARTBEAT is set to a truthy value, False otherwise.

    """
    value = os.environ.get('ENABLE_HEARTBEAT', '').strip()
    return value not in ('', '0', 'false', 'False', 'FALSE')


def schedule_heartbeat_job() -> None:
    """Timed heartbeat job that generates UUID and schedules follow-up event.

    This function will be scheduled to run every minute via cron.
    """
    # TODO: Implement in later steps
