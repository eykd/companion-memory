"""Heartbeat diagnostic functionality."""

import os


def is_heartbeat_enabled() -> bool:
    """Check if heartbeat feature is enabled via ENABLE_HEARTBEAT environment variable.

    Returns:
        True if ENABLE_HEARTBEAT is set to a truthy value, False otherwise.

    """
    value = os.environ.get('ENABLE_HEARTBEAT', '').strip()
    return value not in ('', '0', 'false', 'False', 'FALSE')
