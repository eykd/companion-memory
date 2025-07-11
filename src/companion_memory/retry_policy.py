"""Retry policy and exponential backoff implementation."""

from datetime import datetime, timedelta


class RetryPolicy:
    """Policy for retrying failed jobs with exponential backoff."""

    def __init__(self, base_delay_seconds: int = 60, max_attempts: int = 5) -> None:
        """Initialize retry policy.

        Args:
            base_delay_seconds: Base delay for exponential backoff
            max_attempts: Maximum number of retry attempts

        """
        self._base_delay_seconds = base_delay_seconds
        self._max_attempts = max_attempts

    def calculate_delay(self, attempts: int) -> timedelta:
        """Calculate exponential backoff delay.

        Args:
            attempts: Number of attempts (1-based)

        Returns:
            Delay timedelta for the given attempt

        """
        # delay = base_delay * (2 ** (attempts - 1))
        delay_seconds = self._base_delay_seconds * (2 ** (attempts - 1))
        return timedelta(seconds=delay_seconds)

    def calculate_next_run(self, now: datetime, attempts: int) -> datetime:
        """Calculate when a failed job should run next.

        Args:
            now: Current time
            attempts: Number of attempts (1-based)

        Returns:
            When the job should be retried

        """
        delay = self.calculate_delay(attempts)
        return now + delay

    def should_retry(self, attempts: int) -> bool:
        """Determine if a job should be retried.

        Args:
            attempts: Number of attempts (1-based)

        Returns:
            True if job should be retried, False if it should go to dead letter

        """
        return attempts < self._max_attempts
