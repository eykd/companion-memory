"""Handler for work sampling prompt jobs."""

from pydantic import BaseModel

from companion_memory.job_dispatcher import BaseJobHandler, register_handler
from companion_memory.job_models import WorkSamplingPayload


@register_handler('work_sampling_prompt')
class WorkSamplingHandler(BaseJobHandler):
    """Handler for work sampling prompt jobs."""

    @classmethod
    def payload_model(cls) -> type[BaseModel]:
        """Return the payload model for this handler."""
        return WorkSamplingPayload

    def handle(self, payload: BaseModel) -> None:
        """Process a work sampling prompt job.

        Args:
            payload: Validated payload containing user_id and slot_index

        """
        # The payload is already validated as WorkSamplingPayload by the job dispatcher
        if not isinstance(payload, WorkSamplingPayload):
            msg = f'Expected WorkSamplingPayload, got {type(payload)}'
            raise TypeError(msg)

        # TODO: Implement Slack messaging logic
        # For now, this is just a stub that will be implemented in GREEN phase
