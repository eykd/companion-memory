"""DynamoDB client for job queue operations."""

from datetime import datetime
from typing import Any
from uuid import UUID

import boto3
from boto3.dynamodb.conditions import Attr, Key

from companion_memory.job_models import ScheduledJob, make_job_sk


class JobTable:
    """DynamoDB client for scheduled job operations."""

    def __init__(self, table_name: str = 'CompanionMemory') -> None:
        """Initialize the job table client.

        Args:
            table_name: Name of the DynamoDB table to use

        """
        import os

        self._table_name = table_name
        # Use specified region or default to us-east-1 for testing
        region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        self._dynamodb = boto3.resource('dynamodb', region_name=region)
        self._table = self._dynamodb.Table(table_name)

    def create_table_for_testing(self) -> None:
        """Create DynamoDB table for testing purposes only."""
        try:
            self._dynamodb.create_table(
                TableName=self._table_name,
                KeySchema=[{'AttributeName': 'PK', 'KeyType': 'HASH'}, {'AttributeName': 'SK', 'KeyType': 'RANGE'}],
                AttributeDefinitions=[
                    {'AttributeName': 'PK', 'AttributeType': 'S'},
                    {'AttributeName': 'SK', 'AttributeType': 'S'},
                ],
                BillingMode='PAY_PER_REQUEST',
            )
            # Wait for table to be created
            self._table.wait_until_exists()
        except Exception:  # noqa: BLE001, S110
            # Table might already exist in tests - this is expected behavior in test environment
            pass

    def put_job(self, job: ScheduledJob) -> None:
        """Store a job in DynamoDB.

        Args:
            job: The scheduled job to store

        """
        item = {
            'PK': 'job',
            'SK': make_job_sk(job.scheduled_for, job.job_id),
            'job_id': str(job.job_id),
            'job_type': job.job_type,
            'payload': job.payload,
            'scheduled_for': job.scheduled_for.isoformat(),
            'status': job.status,
            'attempts': job.attempts,
            'created_at': job.created_at.isoformat(),
        }

        # Add optional fields if present
        if job.locked_by is not None:
            item['locked_by'] = job.locked_by
        if job.lock_expires_at is not None:
            item['lock_expires_at'] = job.lock_expires_at.isoformat()
        if job.last_error is not None:
            item['last_error'] = job.last_error
        if job.completed_at is not None:
            item['completed_at'] = job.completed_at.isoformat()

        self._table.put_item(Item=item)

    def get_job_by_id(self, job_id: UUID, scheduled_for: datetime) -> ScheduledJob | None:
        """Get a job by its ID and scheduled_for time.

        Args:
            job_id: The job's unique identifier
            scheduled_for: When the job was scheduled for (needed for SK)

        Returns:
            The job if found, None otherwise

        """
        sk = make_job_sk(scheduled_for, job_id)

        try:
            response = self._table.get_item(Key={'PK': 'job', 'SK': sk})

            if 'Item' not in response:  # pragma: no cover
                return None

            return self._item_to_job(response['Item'])
        except Exception:  # noqa: BLE001  # pragma: no cover
            return None

    def get_due_jobs(self, now: datetime, limit: int = 25) -> list[ScheduledJob]:
        """Fetch jobs that are due to run before the given time.

        Args:
            now: Current time to compare against
            limit: Maximum number of jobs to return

        Returns:
            List of scheduled jobs that are due

        """
        # Query for jobs with SK up to the current time
        # Use 'z' to ensure we capture all UUIDs for timestamps <= now (UUIDs use hex digits 0-9,a-f)
        query_sk = f'scheduled#{now.isoformat()}#z'

        response = self._table.query(
            KeyConditionExpression=Key('PK').eq('job') & Key('SK').lte(query_sk),
            FilterExpression=Attr('status').eq('pending'),
            Limit=limit,
            ConsistentRead=True,
        )

        jobs = []
        for item in response.get('Items', []):
            job = self._item_to_job(item)
            jobs.append(job)

        return jobs

    def update_job_status(self, job_id: UUID, scheduled_for: datetime, status: str, **kwargs: str | int | None) -> None:
        """Update the status of a job.

        Args:
            job_id: The job's unique identifier
            scheduled_for: When the job was scheduled for (needed for SK)
            status: New status value
            **kwargs: Additional attributes to update

        """
        sk = make_job_sk(scheduled_for, job_id)
        updates = {'status': status, **kwargs}

        expression_parts = self._build_update_expression(updates)

        self._table.update_item(
            Key={'PK': 'job', 'SK': sk},
            UpdateExpression=expression_parts['expression'],
            ExpressionAttributeNames=expression_parts['names'],
            ExpressionAttributeValues=expression_parts['values'],
        )

    def _build_update_expression(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Build DynamoDB update expression from key-value pairs.

        Args:
            updates: Dictionary of attribute names to values

        Returns:
            Dictionary containing expression, names, and values

        """
        set_clauses = []
        expression_attribute_names = {}
        expression_attribute_values = {}

        for key, value in updates.items():
            set_clauses.append(f'#{key} = :{key}')
            expression_attribute_names[f'#{key}'] = key
            expression_attribute_values[f':{key}'] = value

        return {
            'expression': f'SET {", ".join(set_clauses)}',
            'names': expression_attribute_names,
            'values': expression_attribute_values,
        }

    def _item_to_job(self, item: dict[str, Any]) -> ScheduledJob:
        """Convert DynamoDB item to ScheduledJob model.

        Args:
            item: DynamoDB item dictionary

        Returns:
            ScheduledJob instance

        """
        return ScheduledJob(
            job_id=UUID(item['job_id']),
            job_type=item['job_type'],
            payload=item['payload'],
            scheduled_for=datetime.fromisoformat(item['scheduled_for']),
            status=item['status'],
            locked_by=item.get('locked_by'),
            lock_expires_at=datetime.fromisoformat(item['lock_expires_at']) if item.get('lock_expires_at') else None,
            attempts=item['attempts'],
            last_error=item.get('last_error'),
            created_at=datetime.fromisoformat(item['created_at']),
            completed_at=datetime.fromisoformat(item['completed_at']) if item.get('completed_at') else None,
        )

    def get_all_jobs_by_id(self, job_id: UUID) -> list[ScheduledJob]:
        """Fetch all jobs with the given job_id (across all scheduled_for times).

        Args:
            job_id: The job's unique identifier

        Returns:
            List of ScheduledJob instances with the given job_id

        """
        response = self._table.query(
            KeyConditionExpression=Key('PK').eq('job'),
        )
        return [self._item_to_job(item) for item in response.get('Items', []) if item.get('job_id') == str(job_id)]

    def cleanup_old_jobs(self, older_than_days: int = 7) -> int:
        """Clean up old completed, failed, and dead_letter jobs.

        Args:
            older_than_days: Remove jobs older than this many days (default: 7)

        Returns:
            Number of jobs deleted

        """
        import logging
        from datetime import UTC, datetime, timedelta

        logger = logging.getLogger(__name__)
        cutoff_date = datetime.now(UTC) - timedelta(days=older_than_days)
        cutoff_sk = f'scheduled#{cutoff_date.isoformat()}#'

        # Starting cleanup of old jobs

        # Query for jobs older than the cutoff date
        response = self._table.query(
            KeyConditionExpression=Key('PK').eq('job') & Key('SK').lt(cutoff_sk),
            FilterExpression=Attr('status').is_in(['completed', 'failed', 'dead_letter', 'cancelled']),
            ConsistentRead=True,
        )

        items_to_delete = response.get('Items', [])
        deleted_count = 0

        # Found old jobs to clean up

        # Delete jobs in batches to avoid throttling
        for item in items_to_delete:
            try:
                self._table.delete_item(
                    Key={'PK': item['PK'], 'SK': item['SK']},
                )
                deleted_count += 1

                # Progress tracking removed

            except Exception:  # pragma: no cover
                logger.exception('Failed to delete job SK=%s', item.get('SK', 'unknown'))

        # Cleanup completed
        return deleted_count
