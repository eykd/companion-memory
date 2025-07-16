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
        logger.info('HEARTBEAT HANDLER START: payload=%s, type=%s', payload, type(payload))

        if not isinstance(payload, HeartbeatEventPayload):
            msg = f'Expected HeartbeatEventPayload, got {type(payload)}'
            logger.error('HEARTBEAT HANDLER ERROR: %s', msg)
            raise TypeError(msg)

        logger.info('HEARTBEAT HANDLER VALIDATED: uuid=%s', payload.heartbeat_uuid)

        # Execute the heartbeat event logging
        try:
            run_heartbeat_event_job(payload.heartbeat_uuid)
            logger.info('HEARTBEAT HANDLER SUCCESS: uuid=%s', payload.heartbeat_uuid)
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
    logger.info('Heartbeat (timed): UUID=%s', str(heartbeat_uuid))

    # Schedule event-based heartbeat job with 10-second delay
    try:
        schedule_event_heartbeat_job(str(heartbeat_uuid))
        logger.info('Scheduled heartbeat event job for UUID=%s', str(heartbeat_uuid))
    except Exception:
        logger.exception('Failed to schedule heartbeat event job for UUID=%s', str(heartbeat_uuid))


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

    # Debug: log table configuration
    import os

    table_name = 'CompanionMemory'  # Default table name
    region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
    logger.info('DEBUG HEARTBEAT: Creating job_table with table_name=%s, region=%s', table_name, region)

    try:
        job_table.put_job(job)
        logger.info('Created heartbeat event job: job_id=%s, scheduled_for=%s', job.job_id, job.scheduled_for)
    except Exception:
        logger.exception('Failed to create heartbeat event job')
        raise
