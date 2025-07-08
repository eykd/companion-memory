"""Scheduler functionality for work sampling and summaries."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler


def create_scheduler(*, blocking: bool = True) -> BlockingScheduler | BackgroundScheduler:
    """Create and configure the APScheduler instance.

    Args:
        blocking: If True, return BlockingScheduler; if False, return BackgroundScheduler

    Returns:
        Configured scheduler instance

    """
    if blocking:
        return BlockingScheduler()
    return BackgroundScheduler()
