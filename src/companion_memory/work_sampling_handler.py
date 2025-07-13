"""Handler for work sampling prompt jobs."""

import random

from pydantic import BaseModel

from companion_memory.job_dispatcher import BaseJobHandler, register_handler
from companion_memory.job_models import WorkSamplingPayload

# Prompt variations for work sampling
PROMPT_VARIATIONS = [
    'What are you working on right now?',
    "Got a minute? Log what you're doing with `/log`.",
    "Quick check-in: what's your focus at the moment?",
    'Still on track? Drop a note with `/log`.',
    'Pause and reflect: what are you doing right now?',
]


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

        # Load Slack client
        from companion_memory.scheduler import get_slack_client

        slack_client = get_slack_client()

        # Select a random prompt variation
        prompt = random.choice(PROMPT_VARIATIONS)  # noqa: S311

        # Send direct message to user
        slack_client.chat_postMessage(channel=payload.user_id, text=prompt)
