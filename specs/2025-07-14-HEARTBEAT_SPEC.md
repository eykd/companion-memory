# Heartbeat Feature Specification

## Purpose

The heartbeat feature provides a global diagnostic mechanism to verify both the time-based and event-based scheduling paths in the system. It is designed to:

* Run a timed job every minute via the scheduler
* Log a heartbeat message
* Schedule a follow-up event-based job that also logs a heartbeat message 10 seconds later

This functionality will be gated by an environment variable and should behave like any other scheduled job, without special treatment or visibility.

---

## Activation

The heartbeat feature is controlled by the following environment variable:

```env
ENABLE_HEARTBEAT=1
```

If unset or falsey, no heartbeat jobs should be scheduled.

---

## Behavior

### 1. Timed Heartbeat Job

* **Frequency:** Every minute
* **Type:** Cron-style, recurring job
* **Scheduler:** APScheduler
* **Action:**

  * Generate a UUIDv1 (includes timestamp)
  * Log at `INFO` level: `"Heartbeat (timed): UUID={uuid}"`
  * Schedule an event-based heartbeat job 10 seconds in the future, passing the UUID as context

### 2. Event-Based Heartbeat Job

* **Trigger:** Scheduled by the timed job with a 10-second delay
* **Action:**

  * Log at `INFO` level: `"Heartbeat (event): UUID={uuid}"`
  * Do not schedule any further jobs

---

## Logging

Both the timed and event-based jobs should log:

* The appropriate label (`timed` or `event`)
* The shared UUID

Example:

```
INFO: Heartbeat (timed): UUID=01D3B4F8-1F35-11EF-AC22-7B4E4C2AD94E
INFO: Heartbeat (event): UUID=01D3B4F8-1F35-11EF-AC22-7B4E4C2AD94E
```

---

## Error Handling

* Any exceptions raised during job execution should be logged using the existing job error handling infrastructure.
* No special alerting, retry, or escalation is required for heartbeat job failures.

---

## Implementation Notes

* The heartbeat job definitions should be loaded at application startup if `ENABLE_HEARTBEAT=1`.
* Job logic should live in its own module (`jobs/heartbeat.py`), mirroring the structure of other job types.
* The UUIDv1 should be passed to the event-based job via job metadata or arguments as appropriate to the scheduler’s interface.
* This feature is purely diagnostic and should have no side effects beyond logging.

---

## Summary Checklist

* [ ] Timed job scheduled every minute via cron
* [ ] Timed job logs with UUID and schedules follow-up event
* [ ] Event-based job runs 10 seconds later, logs using same UUID
* [ ] Logs are distinguishable (`timed` vs. `event`)
* [ ] Controlled by `ENABLE_HEARTBEAT` env var
* [ ] Failures are logged normally
* [ ] No external visibility or filtering required
