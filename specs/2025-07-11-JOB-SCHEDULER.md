# Scheduled Job Queue Specification

This document defines the architecture and behavior of the normalized scheduled job queue system for Companion Memory.

## Overview

The system centralizes all background job scheduling and execution into a robust, extensible job queue built on DynamoDB. It guarantees exactly-once delivery via lease-based locks and idempotent job handlers. Jobs are typed, support arbitrary payloads (via Pydantic), and can be retried with exponential backoff. Failures are reported to Sentry with full context.

---

## 1. Data Model

The job ID refers to the UUID component of the job’s sort key. Workers may extract and log this value explicitly for tracing and monitoring.

The `scheduled_for` field must match the timestamp portion of the SK. SK is used for sorting and query; `scheduled_for` is used in lifecycle logic.

Jobs are stored in DynamoDB using the existing single-table design:

### Table Schema

All timestamps used in the sort key must be in **UTC** and match the format used in the `scheduled_for` field to ensure consistent time-based queries.

| Field             | Type                                   | Description                                                                 |
| ----------------- | -------------------------------------- | --------------------------------------------------------------------------- |
| `PK`              | `job`                                  | Partition key shared by all jobs                                            |
| `SK`              | `scheduled#<ISO8601 timestamp>#<UUID>` | Sort key for querying due jobs by time                                      |
| `job_type`        | string                                 | e.g. `daily_summary`, `user_sync`                                           |
| `payload`         | JSON blob                              | Parsed by a `Pydantic` model per type                                       |
| `scheduled_for`   | UTC ISO timestamp                      | When the job should run                                                     |
| `status`          | string                                 | `pending`, `in_progress`, `completed`, `failed`, `dead_letter`, `cancelled` |
| `locked_by`       | string                                 | Worker ID currently processing                                              |
| `lock_expires_at` | timestamp                              | Time when lock expires                                                      |
| `attempts`        | int                                    | Retry attempt counter                                                       |
| `last_error`      | string                                 | Last error message or traceback                                             |
| `created_at`      | timestamp                              | Job creation time                                                           |
| `completed_at`    | timestamp                              | Optional, when marked completed                                             |

To fetch all jobs scheduled before a given time:

```python
response = table.query(
    KeyConditionExpression=Key('PK').eq('job') & Key('SK').lte(f'scheduled#{now.isoformat()}')
)
```

### Scheduled Job Deduplication Index

To prevent redundant scheduling of identical logical jobs (e.g., daily summaries per user), additional records may be created:

| Field    | Value Example                          |
| -------- | -------------------------------------- |
| `PK`     | `scheduled-job#summary#<user-id>`      |
| `SK`     | `<YYYY-MM-DD>`                         |
| `job_pk` | `job`                                  |
| `job_sk` | `scheduled#<ISO8601 timestamp>#<UUID>` |

Job scheduling logic performs a conditional write on this record:

* If it already exists, the job is not rescheduled.
* If it is newly written, it points to a unique scheduled job record.
* If it exists, the system should verify the target job is still present before assuming the job was scheduled successfully.

---

## 2. Job Lifecycle

### States

* `pending`: Job is ready to run (or scheduled in future)
* `in_progress`: Claimed by a worker with an active lock
* `completed`: Executed successfully
* `failed`: Temporary failure; will be retried with backoff
* `dead_letter`: Failed permanently after max retries
* `cancelled`: Job was intentionally disabled and will not run

### State Transitions

Before scheduling a job, clients may write to the deduplication index and conditionally proceed with job creation if the index key is not already present.

1. Scheduler polls for jobs by querying SKs due before now and filters by:

   * `status == pending`
   * `lock_expires_at < now` or unset
2. Worker claims job via conditional update to set `locked_by` and `lock_expires_at`
3. If success:

   * Status set to `in_progress`
   * Payload parsed, dispatched to handler
4. If success:

   * Status set to `completed`
   * `completed_at` recorded
5. If failure:

   * `attempts += 1`
   * If attempts > max: `status = dead_letter`
   * Else: `status = failed`, `scheduled_for` is updated to a future time based on exponential backoff

---

## 3. Locking & Concurrency

* Locks are implemented via `locked_by` and `lock_expires_at`.
* Workers use conditional writes to claim jobs only if:

  * Not locked, or
  * Lock has expired
* Workers may extend the lease while running
* After crash, another worker can reclaim expired jobs
* All time comparisons use UTC; workers must maintain NTP-synchronized clocks

---

## 4. Retry Policy

* Retries occur automatically on failure
* Exponential backoff is applied:

  ```python
  delay = base_delay * (2 ** (attempts - 1))
  next_run = now + timedelta(seconds=delay)
  ```
* Configurable:

  * `base_delay_seconds`: Default 60
  * `max_attempts`: Default 5
* After max attempts, job is marked `dead_letter`

---

## 5. Dispatch System

Each job type maps to a handler:

```python
job_handlers = {
    "daily_summary": DailySummaryHandler,
    "user_sync": UserSyncHandler,
    # ...
}
```

Each handler implements:

```python
class BaseJobHandler:
    @classmethod
    def payload_model(cls) -> Type[BaseModel]: ...

    def handle(self, payload: BaseModel) -> None: ...
```

Payloads are parsed via Pydantic with per-type validation.

---

## 6. Worker Responsibilities

* Poll DynamoDB for due jobs by querying:

  * `PK == job`
  * `SK <= scheduled#<now>`
* Filter results in memory:

  * `status == pending` (jobs with `cancelled` or other states are ignored)
  * `lock_expires_at` is unset or in the past
* Polling frequency: every 30 seconds (configurable)
* Query limit: up to 25 jobs per poll (configurable)
* Jobs are processed in ascending scheduled order
* Acquire lock via conditional update
* Parse payload and dispatch to handler
* Handle success/failure state transitions
* Extend lock if job runs long
* Log and report exceptions

---

## 7. Monitoring & Error Handling

* All failures include structured error context:

  * `job_id`, `job_type`, `payload`, `traceback`, etc.
* Errors are reported to Sentry
* Dead-letter jobs are retained for audit

### Idempotency

* Handlers must be idempotent: re-executing the same job must not cause side effects to be repeated.
* Strategies include:

  * Logging prior completions (e.g. `summary_sent_at` timestamp)
  * Using deterministic Slack message tokens or UUIDs
* The system does not enforce global idempotency; it is the responsibility of each job type's handler to guard against duplication
