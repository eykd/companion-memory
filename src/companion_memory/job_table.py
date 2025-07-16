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

        # Debug logging for heartbeat jobs
        import logging

        logger = logging.getLogger(__name__)
        if job.job_type == 'heartbeat_event':
            logger.info(
                'DEBUG: Storing heartbeat job - SK=%s, status=%s, scheduled_for=%s',
                item['SK'],
                item['status'],
                item['scheduled_for'],
            )

        # Enhanced error handling and logging for DynamoDB write operations
        try:
            logger.info('DEBUG: About to call put_item for job %s', item['SK'])
            response = self._table.put_item(Item=item)
            logger.info(
                'DEBUG: put_item returned successfully, response metadata: %s', response.get('ResponseMetadata', {})
            )

            # Verify the write by immediately reading it back for heartbeat jobs
            if job.job_type == 'heartbeat_event':
                try:
                    verify_response = self._table.get_item(Key={'PK': 'job', 'SK': item['SK']}, ConsistentRead=True)
                    if 'Item' in verify_response:
                        logger.info('DEBUG: Verification read SUCCESS - job exists in DynamoDB')
                    else:  # pragma: no cover
                        logger.error('DEBUG: Verification read FAILED - job NOT found in DynamoDB after put_item')
                except Exception:  # pragma: no cover
                    logger.exception('DEBUG: Verification read ERROR')

        except Exception:  # pragma: no cover
            logger.exception('DEBUG: put_item FAILED')
            raise

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

    def get_due_jobs(self, now: datetime, limit: int = 25) -> list[ScheduledJob]:  # noqa: C901
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

        # Try query without filter first to debug
        response_no_filter = self._table.query(
            KeyConditionExpression=Key('PK').eq('job') & Key('SK').lte(query_sk),
            Limit=limit,
            ConsistentRead=True,
        )

        response = self._table.query(
            KeyConditionExpression=Key('PK').eq('job') & Key('SK').lte(query_sk),
            FilterExpression=Attr('status').eq('pending'),
            Limit=limit,
            ConsistentRead=True,  # Use strongly consistent reads to avoid eventual consistency issues
        )

        # Debug logging to understand what's being retrieved
        import logging

        logger = logging.getLogger(__name__)

        # Debug: log table configuration for get_due_jobs
        import os

        table_name = 'CompanionMemory'  # Default table name
        region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        logger.info('DEBUG GET_DUE_JOBS: Using table_name=%s, region=%s', table_name, region)

        logger.info('DEBUG: Query without filter returned %d items', len(response_no_filter.get('Items', [])))
        logger.info('DEBUG: Query with filter returned %d items', len(response.get('Items', [])))

        # Debug: examine the first few items to see their actual status values and SK
        for i, item in enumerate(response_no_filter.get('Items', [])[:3]):
            status_value = item.get('status')
            sk_value = item.get('SK')
            logger.info(
                'DEBUG: Time-bounded query item %d: SK=%s, status=%s (type: %s, repr: %s)',
                i,
                sk_value,
                status_value,
                type(status_value).__name__,
                repr(status_value),
            )

        # Test different filter approaches
        pending_count_manual = len([
            item for item in response_no_filter.get('Items', []) if item.get('status') == 'pending'
        ])
        logger.info('DEBUG: Manual filter count for status==pending: %d', pending_count_manual)
        logger.info('DEBUG: Querying with now=%s, query_sk=%s', now.isoformat(), repr(query_sk))
        logger.info('DynamoDB query for jobs <= %s returned %d items', query_sk, len(response.get('Items', [])))

        # Additional debug logging for heartbeat jobs
        if len(response.get('Items', [])) == 0:
            # Query all jobs to see what's actually in the table
            all_jobs_response = self._table.query(
                KeyConditionExpression=Key('PK').eq('job'), Limit=50, ConsistentRead=True
            )
            logger.info('DEBUG: Found %d total job items in table', len(all_jobs_response.get('Items', [])))

            # Look specifically for recent pending jobs
            recent_pending_jobs = []
            all_pending_jobs = []
            very_recent_jobs = []  # Jobs from the last few minutes
            for item in all_jobs_response.get('Items', []):
                if item.get('status') == 'pending':  # pragma: no cover
                    all_pending_jobs.append(item.get('SK', 'unknown'))  # pragma: no cover
                    if '2025-07-16T00:' in item.get('SK', ''):  # Today's recent jobs  # pragma: no cover
                        recent_pending_jobs.append(item.get('SK', 'unknown'))  # pragma: no cover
                    # Check for jobs in the last 5 minutes
                    sk = item.get('SK', '')  # pragma: no cover
                    if sk.startswith(('scheduled#2025-07-16T00:2', 'scheduled#2025-07-16T00:3')):  # pragma: no cover
                        very_recent_jobs.append(f'SK={sk}, status={item.get("status")}')  # pragma: no cover

            if all_pending_jobs:  # pragma: no cover
                logger.info('DEBUG: Found pending jobs: %s', all_pending_jobs)  # pragma: no cover
            if recent_pending_jobs:  # pragma: no cover
                logger.info('DEBUG: Found recent pending jobs: %s', recent_pending_jobs)  # pragma: no cover
            if very_recent_jobs:  # pragma: no cover
                logger.info('DEBUG: Found very recent jobs (last 5 min): %s', very_recent_jobs)  # pragma: no cover
            else:  # pragma: no cover
                logger.info('DEBUG: No very recent jobs found in full scan')  # pragma: no cover

            # Show first 5 jobs for debugging with more details
            for item in all_jobs_response.get('Items', [])[:5]:
                logger.info(  # pragma: no cover
                    'DEBUG: Full scan job SK=%s, status=%s, job_type=%s',
                    item.get('SK', 'unknown'),
                    item.get('status', 'unknown'),
                    item.get('job_type', 'unknown'),
                )

            # Compare: show what jobs would be returned by time-bounded query without filter
            logger.info('DEBUG: Comparing time-bounded vs full scan results')  # pragma: no cover
            logger.info(
                'DEBUG: Time-bounded query found %d items vs full scan found %d items',  # pragma: no cover
                len(response_no_filter.get('Items', [])),
                len(all_jobs_response.get('Items', [])),
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
