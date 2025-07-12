# SPEC: Scheduled Daily Summary Job Migration

## Overview

This specification describes the migration of the daily summary job from a polling-based mechanism to the event-driven job queue system. Each user should receive a summary at **7:00 AM in their local time zone**. The system should pre-schedule these jobs once daily, looking ahead 24 hours.

## Objective

Replace the existing summary-dispatching logic with a scheduled job that:

1. Runs once daily at a fixed time (e.g., 00:00 UTC).
2. For each user in the configured set of daily summary users:

   * Computes the next 7:00 AM in their local time zone.
   * Converts that time to UTC.
   * Enqueues a `daily_summary` job using the job queue system.
   * Ensures no duplicate jobs are scheduled.

## Job Type

* **Name**: `daily_summary`
* **Payload**: `{ "user_id": "<SlackUserID>" }`

## Trigger Job: `schedule_daily_summaries`

This job will be registered in the distributed scheduler.

### Logic

For each user in the `DAILY_SUMMARY_USERS` environment variable:

1. Retrieve the user's time zone via `UserSettingsStore`. If missing, default to UTC.
2. Compute the next 7:00 AM local time.
3. Convert that time to UTC.
4. Generate a logical job ID in the form:
   `daily_summary#<SlackUserID>#<YYYY-MM-DD>`
   where the date component is the local date of the **scheduled 7:00 AM**, in the user’s time zone.
5. Attempt deduplication via `JobDeduplicationIndex.try_reserve(logical_id)`.
6. If deduplication succeeds, enqueue a `daily_summary` job:

   * `scheduled_for`: computed UTC time
   * `job_type`: `daily_summary`
   * `payload`: `{ "user_id": "<SlackUserID>" }`
   * `job_id`: logical ID

### Scheduling

This job should be added to the `DistributedScheduler` and run **once per day** at:

```
CRON: 0 0 * * *  (00:00 UTC daily)
```

## Job Handler: `daily_summary`

### Purpose

Process and send a daily summary message for the specified user.

### Implementation

Registered with the `JobDispatcher` under job type `"daily_summary"`.

```python
@register_handler("daily_summary")
class DailySummaryHandler(BaseJobHandler):
    def run(self, payload: dict):
        user_id = payload["user_id"]
        summarize_today(user_id)
```

* This uses the existing `summarize_today()` function from `summarizer.py`.
* The handler assumes valid `user_id` in the payload.

## Environment Variables

* `DAILY_SUMMARY_USERS`: Comma-separated list of Slack user IDs to receive daily summaries

## Deduplication

* Logical job IDs are used for deduplication via `JobDeduplicationIndex`.
* Format: `daily_summary#<SlackUserID>#<YYYY-MM-DD>`
* The `YYYY-MM-DD` date corresponds to the date **in the user’s local timezone** of the scheduled 7:00 AM execution.
* Deduplication ensures that a job is not scheduled multiple times for the same user/date.

## Data Dependencies

* `UserSettingsStore` for timezone lookup (`timezone` field per user)
* Fallback to UTC if settings are not available

## Time Handling

* All timestamps are stored and scheduled in UTC.
* Local 7:00 AM time is computed per user using their configured time zone.
* Ensure daylight saving time is respected using `zoneinfo.ZoneInfo`.

## Integration Points

* `scheduler.py`: Register `schedule_daily_summaries` with the scheduler
* `job_dispatcher.py`: Register `daily_summary` job handler
* `job_table.py`: Used to insert scheduled jobs
* `deduplication.py`: Used to ensure uniqueness
