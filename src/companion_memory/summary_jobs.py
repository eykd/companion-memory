"""Job handlers for summary generation and delivery."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from companion_memory.job_dispatcher import BaseJobHandler, register_handler
from companion_memory.job_models import ScheduledJob
from companion_memory.job_table import JobTable
from companion_memory.llm_client import LLMLClient
from companion_memory.scheduler import get_slack_client
from companion_memory.storage import LogStore
from companion_memory.summarizer import summarize_today, summarize_week, summarize_yesterday

logger = logging.getLogger(__name__)


def get_summary(user_id: str, summary_range: str, log_store: LogStore, llm: LLMLClient) -> str:
    """Get summary for user and time range.

    Args:
        user_id: User ID to generate summary for
        summary_range: Summary range ('today', 'yesterday', 'lastweek')
        log_store: Log store for retrieving user data
        llm: LLM client for generating summaries

    Returns:
        Generated summary text

    Raises:
        ValueError: If summary_range is not supported

    """
    # Validate range early
    if summary_range not in ('today', 'yesterday', 'lastweek'):
        error_msg = f'Unknown range: {summary_range}'
        raise ValueError(error_msg)

    # Generate summary based on range
    if summary_range == 'today':
        return summarize_today(user_id=user_id, log_store=log_store, llm=llm)
    if summary_range == 'yesterday':
        return summarize_yesterday(user_id=user_id, log_store=log_store, llm=llm)
    # lastweek
    return summarize_week(user_id=user_id, log_store=log_store, llm=llm)


def generate_summary_job(
    user_id: str,
    summary_range: str,
    job_table: JobTable,
    log_store: LogStore,
    llm: LLMLClient,
) -> None:
    """Generate a summary and enqueue a Slack message job.

    Args:
        user_id: User ID to generate summary for
        summary_range: Summary range ('today', 'yesterday', 'lastweek')
        job_table: Job table for scheduling follow-up job
        log_store: Log store for retrieving user data
        llm: LLM client for generating summaries

    """
    # Generate summary using helper
    summary = get_summary(user_id, summary_range, log_store, llm)

    # Generate UUID for tracing
    job_uuid = str(uuid.uuid1())

    # Create follow-up job to send message to Slack
    send_job = ScheduledJob(
        job_id=uuid.uuid4(),
        job_type='send_slack_message',
        payload={
            'slack_user_id': user_id,
            'message': summary,
            'job_uuid': job_uuid,
        },
        scheduled_for=datetime.now(UTC),
        status='pending',
        created_at=datetime.now(UTC),
    )

    # Enqueue the send job
    job_table.put_job(send_job)


def send_slack_message_job(payload: dict[str, Any]) -> None:
    """Send a message to Slack using ephemeral payload.

    Args:
        payload: Dictionary containing slack_user_id, message, and job_uuid

    """
    # Extract payload data
    slack_user_id = payload['slack_user_id']
    message = payload['message']
    job_uuid = payload.get('job_uuid', 'unknown')

    logger.info('Starting send_slack_message job %s for user %s', job_uuid, slack_user_id)

    # Get Slack client
    client = get_slack_client()

    # Send message to Slack
    response = client.chat_postMessage(channel=slack_user_id, text=message)

    logger.debug('Slack API response: %s', response)
    logger.info('Successfully sent message via Slack for job %s', job_uuid)


class GenerateSummaryPayload(BaseModel):
    """Payload model for generate_summary jobs."""

    user_id: str = Field(description='User ID to generate summary for')
    summary_range: str = Field(description='Summary range (today, yesterday, lastweek)')


class SendSlackMessagePayload(BaseModel):
    """Payload model for send_slack_message jobs."""

    slack_user_id: str = Field(description='Slack user ID to send message to')
    message: str = Field(description='Message content to send')
    job_uuid: str = Field(description='UUID for tracking this job')


@register_handler('generate_summary')
class GenerateSummaryHandler(BaseJobHandler):
    """Handler for generate_summary jobs."""

    @classmethod
    def payload_model(cls) -> type[BaseModel]:
        """Return the payload model for this handler."""
        return GenerateSummaryPayload

    def handle(self, payload: BaseModel) -> None:
        """Process a generate_summary job.

        Args:
            payload: Validated payload containing user_id and summary_range

        """
        if not isinstance(payload, GenerateSummaryPayload):
            msg = f'Expected GenerateSummaryPayload, got {type(payload)}'
            raise TypeError(msg)

        # Get required dependencies
        from companion_memory.app import get_log_store
        from companion_memory.job_table import JobTable
        from companion_memory.llm_client import LLMLClient

        job_table = JobTable()
        log_store = get_log_store()
        llm = LLMLClient()

        # Call the existing business logic
        generate_summary_job(
            user_id=payload.user_id,
            summary_range=payload.summary_range,
            job_table=job_table,
            log_store=log_store,
            llm=llm,
        )


@register_handler('send_slack_message')
class SendSlackMessageHandler(BaseJobHandler):
    """Handler for send_slack_message jobs."""

    @classmethod
    def payload_model(cls) -> type[BaseModel]:
        """Return the payload model for this handler."""
        return SendSlackMessagePayload

    def handle(self, payload: BaseModel) -> None:
        """Process a send_slack_message job.

        Args:
            payload: Validated payload containing slack_user_id, message, and job_uuid

        """
        if not isinstance(payload, SendSlackMessagePayload):
            msg = f'Expected SendSlackMessagePayload, got {type(payload)}'
            raise TypeError(msg)

        # Call the existing business logic
        send_slack_message_job({
            'slack_user_id': payload.slack_user_id,
            'message': payload.message,
            'job_uuid': payload.job_uuid,
        })
