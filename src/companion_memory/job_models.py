"""Job data models and utilities for the scheduled job queue."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

JobStatus = Literal['pending', 'in_progress', 'completed', 'failed', 'dead_letter', 'cancelled']


class ScheduledJob(BaseModel):
    """Data model for a scheduled job in DynamoDB."""

    job_id: UUID = Field(description='Unique identifier for the job')
    job_type: str = Field(description='Type of job for handler dispatch')
    payload: dict[str, Any] = Field(description='Job-specific data for handler')
    scheduled_for: datetime = Field(description='When the job should run (UTC)')
    status: JobStatus = Field(description='Current status of the job')
    locked_by: str | None = Field(default=None, description='Worker ID currently processing')
    lock_expires_at: datetime | None = Field(default=None, description='When lock expires')
    attempts: int = Field(default=0, description='Number of retry attempts')
    last_error: str | None = Field(default=None, description='Last error message or traceback')
    created_at: datetime = Field(description='Job creation time')
    completed_at: datetime | None = Field(default=None, description='Job completion time')


def make_job_sk(scheduled_for: datetime, job_id: UUID) -> str:
    """Generate DynamoDB sort key for a scheduled job.

    Args:
        scheduled_for: When the job should run (UTC)
        job_id: Unique identifier for the job

    Returns:
        Sort key in format: scheduled#<ISO8601 timestamp>#<UUID>

    """
    return f'scheduled#{scheduled_for.isoformat()}#{job_id}'


def parse_job_sk(sk: str) -> tuple[datetime, UUID]:
    """Parse DynamoDB sort key to extract timestamp and job ID.

    Args:
        sk: Sort key string

    Returns:
        Tuple of (timestamp, job_id)

    Raises:
        ValueError: If sort key format is invalid

    """
    error_message = f'Invalid sort key format: {sk}'

    parts = sk.split('#')
    if len(parts) != 3 or parts[0] != 'scheduled':
        raise ValueError(error_message)

    try:
        timestamp = datetime.fromisoformat(parts[1])
        job_id = UUID(parts[2])
    except (ValueError, TypeError) as exc:
        raise ValueError(error_message) from exc
    else:
        return timestamp, job_id
