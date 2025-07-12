"""Daily summary scheduling functionality."""

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:  # pragma: no cover
    from companion_memory.deduplication import DeduplicationIndex
    from companion_memory.job_table import JobTable
    from companion_memory.user_settings import UserSettingsStore


def get_next_7am_utc(user_tz: ZoneInfo, now_utc: datetime) -> datetime:
    """Compute the next 7:00 AM local time for a user and return it in UTC.

    Args:
        user_tz: User's timezone as ZoneInfo
        now_utc: Current time in UTC

    Returns:
        Next 7:00 AM in user's timezone, converted to UTC

    """
    # Convert current UTC time to user's local time
    now_local = now_utc.astimezone(user_tz)

    # Create 7:00 AM today in user's timezone
    today_7am_local = now_local.replace(hour=7, minute=0, second=0, microsecond=0)

    # If it's already past 7:00 AM today, schedule for tomorrow
    if now_local >= today_7am_local:
        tomorrow_7am_local = today_7am_local + timedelta(days=1)
        next_7am_local = tomorrow_7am_local
    else:
        next_7am_local = today_7am_local

    # Convert back to UTC
    return next_7am_local.astimezone(UTC)


def make_daily_summary_job_id(user_id: str, user_tz: ZoneInfo, local_7am_utc: datetime) -> str:
    """Generate a logical job ID for daily summary scheduling.

    Args:
        user_id: Slack user ID
        user_tz: User's timezone as ZoneInfo
        local_7am_utc: The UTC datetime representing 7:00 AM in the user's timezone

    Returns:
        Job ID in format: daily_summary#<user_id>#<YYYY-MM-DD>
        where the date is the local date in the user's timezone

    """
    # Convert UTC time back to user's local time to get the local date
    local_7am = local_7am_utc.astimezone(user_tz)
    local_date = local_7am.date().isoformat()

    return f'daily_summary#{user_id}#{local_date}'


def schedule_daily_summaries(
    user_settings_store: 'UserSettingsStore',
    job_table: 'JobTable',
    deduplication_index: 'DeduplicationIndex',
    now_utc: datetime | None = None,
) -> None:
    """Schedule daily summary jobs for all configured users.

    Args:
        user_settings_store: Store for user timezone settings
        job_table: Job table for creating scheduled jobs
        deduplication_index: Index for preventing duplicate jobs
        now_utc: Current time in UTC (for testing), defaults to datetime.now(UTC)

    """
    from companion_memory.job_models import ScheduledJob

    # Get current time
    if now_utc is None:
        now_utc = datetime.now(UTC)

    # Get list of users from environment
    daily_summary_users = os.environ.get('DAILY_SUMMARY_USERS', '')
    if not daily_summary_users:
        return

    user_ids = [user_id.strip() for user_id in daily_summary_users.split(',') if user_id.strip()]

    for user_id in user_ids:
        # Get user's timezone from settings, default to UTC if not found
        user_settings = user_settings_store.get_user_settings(user_id)
        user_tz_name = user_settings.get('timezone')
        if user_tz_name:
            try:
                user_tz = ZoneInfo(user_tz_name)
            except (ValueError, KeyError):  # Invalid timezone name
                user_tz = ZoneInfo('UTC')
        else:
            user_tz = ZoneInfo('UTC')

        # Compute next 7:00 AM local time in UTC
        next_7am_utc = get_next_7am_utc(user_tz, now_utc)

        # Generate logical job ID
        logical_job_id = make_daily_summary_job_id(user_id, user_tz, next_7am_utc)

        # Extract date for deduplication
        local_7am = next_7am_utc.astimezone(user_tz)
        local_date = local_7am.date().isoformat()

        # Try to reserve this job (deduplication)
        if deduplication_index.try_reserve(logical_job_id, local_date, 'job', f'scheduled#{next_7am_utc.isoformat()}'):
            # Create the scheduled job
            job = ScheduledJob(
                job_id=uuid.uuid4(),  # Generate a new UUID for the actual job
                job_type='daily_summary',
                payload={'user_id': user_id},
                scheduled_for=next_7am_utc,
                status='pending',
                attempts=0,
                locked_by=None,
                lock_expires_at=None,
                created_at=now_utc,
            )

            # Store the job
            job_table.put_job(job)
