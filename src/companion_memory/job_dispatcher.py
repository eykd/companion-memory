"""Job handler base classes and dispatcher system."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from pydantic import BaseModel, ValidationError

from companion_memory.job_models import ScheduledJob


class BaseJobHandler(ABC):
    """Base class for all job handlers."""

    @classmethod
    @abstractmethod
    def payload_model(cls) -> type[BaseModel]:
        """Return the Pydantic model for validating this job's payload.

        Returns:
            Pydantic model class for payload validation

        """
        ...  # pragma: no cover

    @abstractmethod
    def handle(self, payload: BaseModel) -> None:
        """Handle the job with validated payload.

        Args:
            payload: Validated payload instance

        """
        ...  # pragma: no cover


class JobDispatcher:
    """Dispatcher for routing jobs to appropriate handlers."""

    def __init__(self) -> None:
        """Initialize the job dispatcher."""
        self._handlers: dict[str, type[BaseJobHandler]] = {}

    def register(self, job_type: str, handler_class: type[BaseJobHandler]) -> None:
        """Register a handler for a specific job type.

        Args:
            job_type: The job type string
            handler_class: The handler class

        """
        self._handlers[job_type] = handler_class

    def dispatch(self, job: ScheduledJob) -> BaseJobHandler:
        """Dispatch a job to its appropriate handler.

        Args:
            job: The scheduled job to dispatch

        Returns:
            Handler instance that processed the job

        Raises:
            ValueError: If no handler is registered for the job type or payload validation fails

        """
        # Check if handler is registered
        if job.job_type not in self._handlers:
            error_message = f'No handler registered for job type: {job.job_type}'
            raise ValueError(error_message)

        handler_class = self._handlers[job.job_type]

        # Validate payload using handler's model
        try:
            payload_model = handler_class.payload_model()
            validated_payload = payload_model.model_validate(job.payload)
        except ValidationError as e:
            error_message = f'Payload validation failed for job type {job.job_type}: {e}'
            raise ValueError(error_message) from e

        # Create handler instance and process job
        handler_instance = handler_class()
        handler_instance.handle(validated_payload)

        return handler_instance


# Global dispatcher instance for use with decorator
global_dispatcher = JobDispatcher()


def register_handler(job_type: str) -> Callable[[type[BaseJobHandler]], type[BaseJobHandler]]:
    """Decorator to register a handler with the global dispatcher.

    Args:
        job_type: The job type string to register

    Returns:
        Decorator function

    """

    def decorator(handler_class: type[BaseJobHandler]) -> type[BaseJobHandler]:
        global_dispatcher.register(job_type, handler_class)
        return handler_class

    return decorator
