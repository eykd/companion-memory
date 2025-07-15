"""Job handlers for summary generation and delivery."""

import uuid
from datetime import UTC, datetime

from companion_memory.job_models import ScheduledJob
from companion_memory.job_table import JobTable
from companion_memory.llm_client import LLMLClient
from companion_memory.storage import LogStore
from companion_memory.summarizer import summarize_today, summarize_week, summarize_yesterday


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
    # Generate summary based on range
    if summary_range == 'today':
        summary = summarize_today(user_id=user_id, log_store=log_store, llm=llm)
    elif summary_range == 'yesterday':
        summary = summarize_yesterday(user_id=user_id, log_store=log_store, llm=llm)
    elif summary_range == 'lastweek':
        summary = summarize_week(user_id=user_id, log_store=log_store, llm=llm)
    else:
        error_msg = f'Unknown range: {summary_range}'
        raise ValueError(error_msg)

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
