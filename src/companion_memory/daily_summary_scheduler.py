"""Daily summary scheduling functionality."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


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
