"""Work sampling prompt scheduler.

Schedules random work sampling prompts throughout the workday for each user.
"""

from datetime import datetime


def schedule_work_sampling_jobs(now_utc: datetime | None = None) -> None:
    """Schedule work sampling prompt jobs for all users.

    Args:
        now_utc: Current UTC time (for testing), defaults to None for current time

    """
    # TODO: Implement work sampling scheduling logic
    # This stub will be implemented in GREEN phase
