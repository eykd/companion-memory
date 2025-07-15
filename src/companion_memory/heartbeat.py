"""Heartbeat diagnostic functionality."""

import logging
import os
import uuid

logger = logging.getLogger(__name__)


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
    run_heartbeat_timed_job()


def run_heartbeat_timed_job() -> None:
    """Execute the timed heartbeat job logic.

    Generates UUIDv1, logs heartbeat message, and schedules event-based follow-up.
    """
    # Generate UUIDv1 (includes timestamp)
    heartbeat_uuid = uuid.uuid1()

    # Log the timed heartbeat
    logger.info('Heartbeat (timed): UUID=%s', str(heartbeat_uuid))

    # Schedule event-based heartbeat job with 10-second delay
    schedule_event_heartbeat_job(str(heartbeat_uuid))


def run_heartbeat_event_job(heartbeat_uuid: str) -> None:
    """Execute the event-based heartbeat job logic.

    Args:
        heartbeat_uuid: The UUID to log in the heartbeat message.

    """
    # Log the event heartbeat with the provided UUID
    logger.info('Heartbeat (event): UUID=%s', heartbeat_uuid)


def schedule_event_heartbeat_job(heartbeat_uuid: str) -> None:
    """Schedule an event-based heartbeat job with 10-second delay.

    Args:
        heartbeat_uuid: The UUID to pass to the event job for logging.

    """
    # TODO: Implement in later steps
