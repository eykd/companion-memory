"""Deduplication index for preventing duplicate job scheduling."""

from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError

from companion_memory.job_models import ScheduledJob, make_job_sk

if TYPE_CHECKING:  # pragma: no cover
    from companion_memory.job_table import JobTable


class DeduplicationIndex:
    """DynamoDB-based deduplication index for job scheduling."""

    def __init__(self, table_name: str = 'CompanionMemory') -> None:
        """Initialize the deduplication index.

        Args:
            table_name: Name of the DynamoDB table to use

        """
        self._table_name = table_name
        self._dynamodb = boto3.resource('dynamodb')
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

    def try_reserve(self, logical_id: str, date: str, job_pk: str, job_sk: str) -> bool:
        """Try to reserve a deduplication slot for a logical job.

        Args:
            logical_id: Logical identifier for the job (e.g., 'summary#U123456')
            date: Date string for the reservation (e.g., '2025-07-11')
            job_pk: Job partition key to reference
            job_sk: Job sort key to reference

        Returns:
            True if reservation succeeded, False if already reserved

        """
        item = {
            'PK': f'scheduled-job#{logical_id}',
            'SK': date,
            'job_pk': job_pk,
            'job_sk': job_sk,
        }

        try:
            # Use conditional write to prevent duplicates
            self._table.put_item(Item=item, ConditionExpression='attribute_not_exists(PK)')
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # Item already exists - deduplication prevented scheduling
                return False
            raise  # Re-raise other errors
        else:
            return True

    def schedule_if_needed(self, job: ScheduledJob, job_table: 'JobTable', logical_id: str, date: str) -> bool:
        """Schedule a job only if not already scheduled for the given logical ID and date.

        Args:
            job: The job to schedule
            job_table: Job table instance for storing the job
            logical_id: Logical identifier for deduplication
            date: Date string for deduplication

        Returns:
            True if job was scheduled, False if skipped due to deduplication

        """
        job_sk = make_job_sk(job.scheduled_for, job.job_id)

        # Try to reserve the deduplication slot
        if self.try_reserve(logical_id, date, 'job', job_sk):
            # Reservation succeeded, store the actual job
            job_table.put_job(job)
            return True
        # Already reserved - skip scheduling
        return False
