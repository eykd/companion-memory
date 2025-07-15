# Heartbeat Feature: TDD Implementation Plan

This document outlines an extremely detailed test-driven development (TDD) plan for implementing the Heartbeat feature described in the "Heartbeat Scheduler Spec." Each task follows a RED → TEST → GREEN → LINT → TEST → COMMIT → REFACTOR → LINT → TEST → COMMIT cycle. Each GREEN and REFACTOR step includes committing changes. Tasks are grouped by function and implementation order.

---

## ENV CONFIG SUPPORT

### ✅ RED: Add failing test for ENABLE\_HEARTBEAT env var

* Add test in config/test\_settings.py (or equivalent) asserting `is_heartbeat_enabled()` returns True when `ENABLE_HEARTBEAT=1`.

### ✅ GREEN: Implement `is_heartbeat_enabled()` helper

* Return True/False based on environment variable using `os.getenv()`.

### ✅ LINT

### ✅ TEST

### ✅ COMMIT: "Implement heartbeat feature flag via env var"

### ✅ REFACTOR: Co-locate related feature-flag helpers

### ✅ LINT

### ✅ TEST

### ✅ COMMIT: "Refactor heartbeat flag helper for reuse"

---

## TIMED JOB IMPLEMENTATION

### ✅ RED: Add failing test to scheduler bootstrapper

* Test: When heartbeat enabled, a cron job is registered to run every minute.

### ✅ GREEN: Register heartbeat job at startup

* Use APScheduler cron expression: `* * * * *`
* Function: `schedule_heartbeat_job()` in `jobs/heartbeat.py`

### ✅ LINT

### ✅ TEST

### ✅ COMMIT: "Register timed heartbeat cron job when enabled"

### ✅ REFACTOR: Extract cron expression to constant

### ✅ LINT

### ✅ TEST

### ✅ COMMIT: "Refactor heartbeat cron expression"

---

## TIMED JOB LOGIC

### ✅ RED: Add failing unit test for `run_heartbeat_timed_job()`

* Should log `Heartbeat (timed)` with UUIDv1 and schedule event-based job with same UUID.

### ✅ GREEN: Implement `run_heartbeat_timed_job()`

* Generate UUIDv1
* Log at INFO level
* Schedule event-based job with 10-second delay, passing UUID

### ✅ LINT

### ✅ TEST

### ✅ COMMIT: "Implement timed heartbeat job logic with UUID"

### ✅ REFACTOR: Extract logging to shared function if necessary

### ✅ LINT

### ✅ TEST

### ✅ COMMIT: "Refactor: extract heartbeat logging function"

---

## EVENT-BASED JOB LOGIC

### ✅ RED: Add failing test for `run_heartbeat_event_job()`

* Should log `Heartbeat (event)` with same UUID

### ✅ GREEN: Implement `run_heartbeat_event_job()`

* Accept UUID argument
* Log at INFO level
* No further action

### ✅ LINT

### ✅ TEST

### ✅ COMMIT: "Implement event-based heartbeat job logic"

### ✅ REFACTOR: Co-locate timed/event heartbeat functions

### ✅ LINT

### ✅ TEST

### ✅ COMMIT: "Refactor: group heartbeat job logic"

---

## JOB SCHEDULING UTILITIES

### ✅ RED: Add failing test for scheduling event job with delay

* Ensure scheduled time is \~10s from now

### ✅ GREEN: Implement `schedule_event_heartbeat_job(uuid)`

* Use scheduler API to enqueue with 10s delay

### ✅ LINT

### ✅ TEST

### ✅ COMMIT: "Add helper to schedule delayed heartbeat event job"

---

## FAILURE HANDLING

### ✅ RED: Add integration test for exception during heartbeat job

* Should log exception; job framework must not crash

### ✅ GREEN: Allow normal error path to handle exception

### ✅ LINT

### ✅ TEST

### ✅ COMMIT: "Verify heartbeat job error handling logs correctly"

---

## FINAL SMOKE TESTS

### ✅ RED: Add system-level test

* Enable heartbeat
* Verify that:

  * Every minute a timed heartbeat is logged
  * 10s later an event heartbeat is logged with matching UUID

### ✅ GREEN: Manually test in dev or test environment

### ✅ LINT

### ✅ TEST

### ✅ COMMIT: "Smoke test heartbeat system end-to-end"

---

## Optional: DISABLE FEATURE WHEN NOT ENABLED

### ✅ RED: Add test: heartbeat jobs not scheduled if `ENABLE_HEARTBEAT` unset

### ✅ GREEN: Add conditional logic around job registration

### ✅ LINT

### ✅ TEST

### ✅ COMMIT: "Disable heartbeat jobs if feature not enabled"

---

## COMPLETION CHECKLIST

* [ ] Feature flag support via env var
* [ ] Cron-style timed heartbeat job every minute
* [ ] Timed job logs and schedules event job with UUID
* [ ] Event job logs with same UUID and exits
* [ ] Jobs handled like any other—normal error logging
* [ ] Feature isolated in `jobs/heartbeat.py`
* [ ] All code tested, linted, and committed using TDD discipline
