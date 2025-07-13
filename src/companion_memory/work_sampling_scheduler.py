"""Work sampling prompt scheduler.

Schedules random work sampling prompts throughout the workday for each user.
"""

import hashlib
import random
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4
from zoneinfo import ZoneInfo

if TYPE_CHECKING:  # pragma: no cover
    from datetime import tzinfo

from companion_memory.deduplication import DeduplicationIndex
from companion_memory.job_models import ScheduledJob, make_job_sk
from companion_memory.job_table import JobTable
from companion_memory.user_settings import DynamoUserSettingsStore
from companion_memory.work_sampling_handler import WORK_SAMPLING_PROMPTS_PER_DAY


def schedule_work_sampling_jobs(
    now_utc: datetime | None = None,
    user_settings_store: DynamoUserSettingsStore | None = None,
    job_table: JobTable | None = None,
    deduplication_index: DeduplicationIndex | None = None,
) -> None:
    """Schedule work sampling prompt jobs for all users.

    Args:
        now_utc: Current UTC time (for testing), defaults to None for current time
        user_settings_store: User settings store instance (for testing)
        job_table: Job table instance (for testing)
        deduplication_index: Deduplication index instance (for testing)

    """
    if now_utc is None:
        now_utc = datetime.now(UTC)

    # Initialize components (with dependency injection for testing)
    if user_settings_store is None:
        user_settings_store = DynamoUserSettingsStore()
    if job_table is None:
        job_table = JobTable()
    if deduplication_index is None:
        deduplication_index = DeduplicationIndex()

    # Get all users (this method doesn't exist yet - we'll need to add it)
    # For now, we'll create a mock implementation
    all_users = _get_all_users(user_settings_store)

    for user_id in all_users:
        _schedule_user_work_sampling_jobs(
            user_id=user_id,
            now_utc=now_utc,
            user_settings_store=user_settings_store,
            job_table=job_table,
            deduplication_index=deduplication_index,
        )


def _get_all_users(user_settings_store: DynamoUserSettingsStore) -> list[str]:
    """Get all user IDs from user settings store.

    Note: This is a simplified implementation. In practice, we would need to
    scan the DynamoDB table or maintain a separate index of users.
    """
    # For now, use the mock method if it exists (for testing)
    if hasattr(user_settings_store, 'get_all_users'):
        users = user_settings_store.get_all_users()
        return users if isinstance(users, list) else []

    # In a real implementation, this would scan the user settings table
    # For now, return empty list (no users to schedule)
    return []


def _schedule_user_work_sampling_jobs(
    user_id: str,
    now_utc: datetime,
    user_settings_store: DynamoUserSettingsStore,
    job_table: JobTable,
    deduplication_index: DeduplicationIndex,
) -> None:
    """Schedule work sampling jobs for a single user."""
    # Get user's timezone settings
    user_settings = user_settings_store.get_user_settings(user_id)
    timezone_name = user_settings.get('timezone', 'UTC')

    try:
        user_tz: tzinfo = ZoneInfo(timezone_name)
    except Exception:  # noqa: BLE001
        # Fall back to UTC if timezone is invalid
        user_tz = UTC

    # Determine local date corresponding to midnight UTC
    local_date = now_utc.astimezone(user_tz).date()

    # Define workday range: 8:00-17:00 in user's local timezone
    workday_start = datetime.combine(local_date, datetime.min.time().replace(hour=8), tzinfo=user_tz)
    workday_end = datetime.combine(local_date, datetime.min.time().replace(hour=17), tzinfo=user_tz)

    # Calculate slot duration (9 hours / N slots)
    workday_duration = workday_end - workday_start
    slot_duration = workday_duration / WORK_SAMPLING_PROMPTS_PER_DAY

    # Schedule jobs for each slot
    for slot_index in range(WORK_SAMPLING_PROMPTS_PER_DAY):
        slot_start = workday_start + (slot_duration * slot_index)
        slot_end = slot_start + slot_duration

        # Generate deterministic random time within the slot
        random_time_utc = _generate_random_time_in_slot(
            user_id=user_id,
            local_date=datetime.combine(local_date, datetime.min.time()),
            slot_index=slot_index,
            slot_start=slot_start,
            slot_end=slot_end,
        )

        # Create logical job ID for deduplication
        logical_job_id = f'work_sampling_prompt:{user_id}:{local_date.isoformat()}:{slot_index}'

        # Create job
        job_id = uuid4()
        job = ScheduledJob(
            job_id=job_id,
            job_type='work_sampling_prompt',
            payload={'user_id': user_id, 'slot_index': slot_index},
            scheduled_for=random_time_utc,
            status='pending',
            attempts=0,
            created_at=now_utc,
        )

        # Try to reserve deduplication slot
        job_sk = make_job_sk(random_time_utc, job_id)
        if deduplication_index.try_reserve(logical_job_id, str(local_date), 'job', job_sk):
            job_table.put_job(job)


def _generate_random_time_in_slot(
    user_id: str,
    local_date: datetime,
    slot_index: int,
    slot_start: datetime,
    slot_end: datetime,
) -> datetime:
    """Generate a deterministic random time within a slot using seeded PRNG."""
    # Create deterministic seed as specified
    seed_string = f'{user_id}-{local_date.date().isoformat()}-{slot_index}'
    seed_bytes = hashlib.sha256(seed_string.encode()).digest()

    # Use first 4 bytes as integer seed
    seed = int.from_bytes(seed_bytes[:4], byteorder='big')

    # Seed random generator
    rng = random.Random(seed)  # noqa: S311

    # Generate random time within the slot
    slot_duration_seconds = (slot_end - slot_start).total_seconds()
    random_offset_seconds = rng.uniform(0, slot_duration_seconds)

    return slot_start + timedelta(seconds=random_offset_seconds)
