# Project Plan: Scheduled Daily Summary Job Migration

This plan implements the `schedule_daily_summaries` functionality described in the corresponding specification. The implementation will follow a strict **TDD Red/Green/Refactor** process. Each step includes:

* **RED**: Write a failing test.
* **GREEN**: Implement code to pass the test.
* **LINT**: Run linters.
* **TEST**: Run full test suite.
* **COMMIT**: Commit changes.
* **REFACTOR**: Improve code clarity or structure without changing behavior.
* **LINT/TEST/COMMIT**: Repeat quality gates after refactor.

---

## STEP 1: Define and isolate test fixtures

### RED

* Write test fixtures to mock:

  * `UserSettingsStore` with known timezones
  * `JobTable.put_job`
  * `JobDeduplicationIndex.try_reserve`

### GREEN

* Implement these fixtures in `conftest.py` or local test scope

### LINT/TEST/COMMIT

* Run `ruff`, `pytest`, and commit changes

---

## STEP 2: Compute next 7am local time

### RED

* Add test: given a fixed UTC time and timezone, assert correct local 7am UTC equivalent

### GREEN

* Add function `get_next_7am_utc(user_tz: ZoneInfo, now_utc: datetime) -> datetime`

### LINT/TEST/COMMIT

* Quality check and commit

### REFACTOR

* Move to `utils.py` or `scheduler.py` as appropriate

### LINT/TEST/COMMIT

* Confirm coverage and clarity

---

## STEP 3: Build job ID from local date

### RED

* Write test: generate `daily_summary#<user_id>#<local_date>` from time and zone

### GREEN

* Add function `make_daily_summary_job_id(user_id: str, user_tz: ZoneInfo, local_7am_dt: datetime) -> str`

### LINT/TEST/COMMIT

* Format and test

### REFACTOR

* Collocate or document helper

### LINT/TEST/COMMIT

* Confirm integrity

---

## STEP 4: Write `schedule_daily_summaries()` logic

### RED

* Add integration test: verify that given multiple users, `put_job()` is called exactly once per user with correct UTC time and ID

### GREEN

* Implement `schedule_daily_summaries()` in `scheduler.py`:

  * Load from `DAILY_SUMMARY_USERS`
  * Get user timezones via `UserSettingsStore`
  * Compute local 7am → UTC
  * Check deduplication
  * Enqueue job

### LINT/TEST/COMMIT

* Validate formatting and full suite

### REFACTOR

* Break long function, improve naming

### LINT/TEST/COMMIT

* Finalize structure

---

## STEP 5: Register scheduled job

### RED

* Write test: scheduler starts and `schedule_daily_summaries()` is added with correct cron expression

### GREEN

* Modify `run_scheduler()` to register job:

```python
scheduler.add_job(schedule_daily_summaries, 'cron', hour=0)
```

### LINT/TEST/COMMIT

* Confirm it’s registered and clean

### REFACTOR

* Extract `add_scheduled_jobs()` for clarity if needed

### LINT/TEST/COMMIT

* Finalize structure

---

## STEP 6: Add job handler for `daily_summary`

### RED

* Write test: handler calls `summarize_today(user_id)` with correct payload

### GREEN

* Add handler in `job_dispatcher.py`:

```python
@register_handler("daily_summary")
class DailySummaryHandler(BaseJobHandler):
    def run(self, payload: dict):
        user_id = payload["user_id"]
        summarize_today(user_id)
```

### LINT/TEST/COMMIT

* Quality and commit

### REFACTOR

* Extract summarization logic to shared service if bloated

### LINT/TEST/COMMIT

* Lock in changes

---

## STEP 7: End-to-end test coverage

### RED

* Write test: simulated environment with mock clock, timezones, and assertions that scheduled jobs are correct

### GREEN

* Build full integration test case

### LINT/TEST/COMMIT

* Validate entire suite

### REFACTOR

* Improve test naming and modularity

### LINT/TEST/COMMIT

* Complete

---

## STEP 8: Remove legacy logic

### RED

* Add test: ensure legacy `check_and_send_daily_summaries()` is not triggered

### GREEN

* Remove or disable old implementation

### LINT/TEST/COMMIT

* Sanitize codebase

### REFACTOR

* Remove any now-unused helpers

### LINT/TEST/COMMIT

* Confirm clean state

---

## Completion Criteria

* Daily summary jobs are scheduled once per user per day at 7am local time.
* No duplicate jobs are created.
* All tests pass with 100% coverage.
* Code is fully linted and type-checked.
* Old summary logic is removed.
* Behavior is validated via end-to-end test.
