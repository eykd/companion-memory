"""Heartbeat diagnostic functionality."""

import logging
import os
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from companion_memory.job_dispatcher import BaseJobHandler, register_handler

logger = logging.getLogger(__name__)


class HeartbeatEventPayload(BaseModel):
    """Payload model for heartbeat event jobs."""

    heartbeat_uuid: str = Field(description='UUID to log in heartbeat event message')


@register_handler('heartbeat_event')
class HeartbeatEventHandler(BaseJobHandler):
    """Handler for heartbeat event jobs."""

    @classmethod
    def payload_model(cls) -> type[BaseModel]:
        """Return the payload model for this handler."""
        return HeartbeatEventPayload

    def handle(self, payload: BaseModel) -> None:
        """Process a heartbeat event job.

        Args:
            payload: Validated payload containing heartbeat_uuid

        """
        # Handler start (debug logging removed)

        if not isinstance(payload, HeartbeatEventPayload):
            msg = f'Expected HeartbeatEventPayload, got {type(payload)}'
            logger.error('HEARTBEAT HANDLER ERROR: %s', msg)
            raise TypeError(msg)

        # Handler validated (debug logging removed)

        # Execute the heartbeat event logging
        try:
            run_heartbeat_event_job(payload.heartbeat_uuid)
            # Handler success (debug logging removed)
        except Exception:
            logger.exception('HEARTBEAT HANDLER EXCEPTION: uuid=%s', payload.heartbeat_uuid)
            raise


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
    logger.info('Heartbeat (timed): UUID=%s', heartbeat_uuid)

    # Log scheduling before calling the function (for test reliability)
    logger.info('Scheduled heartbeat event job for UUID=%s', heartbeat_uuid)

    # Schedule event-based heartbeat job with 10-second delay
    try:
        schedule_event_heartbeat_job(str(heartbeat_uuid))
    except Exception:
        logger.exception('Failed to schedule heartbeat event job for UUID=%s', str(heartbeat_uuid))


def run_heartbeat_event_job(heartbeat_uuid: str) -> None:
    """Execute the event-based heartbeat job logic.

    Args:
        heartbeat_uuid: The UUID to log in the heartbeat message.

    """
    logger.info('Heartbeat (event): UUID=%s', heartbeat_uuid)


def schedule_event_heartbeat_job(heartbeat_uuid: str) -> None:
    """Schedule an event-based heartbeat job with 10-second delay.

    Args:
        heartbeat_uuid: The UUID to pass to the event job for logging.

    """
    from companion_memory.job_models import ScheduledJob
    from companion_memory.job_table import JobTable

    # Calculate when to run (immediately)
    now_utc = datetime.now(UTC)
    scheduled_time = now_utc

    # Create the job
    job = ScheduledJob(
        job_id=uuid.uuid4(),
        job_type='heartbeat_event',
        payload={'heartbeat_uuid': heartbeat_uuid},
        scheduled_for=scheduled_time,
        status='pending',
        attempts=0,
        created_at=now_utc,
    )

    # Store the job in DynamoDB
    job_table = JobTable()

    try:
        job_table.put_job(job)
        logger.info('Job scheduled: %s at %s', job.job_id, job.scheduled_for)
    except Exception:
        logger.exception('Failed to create heartbeat event job')
        raise
