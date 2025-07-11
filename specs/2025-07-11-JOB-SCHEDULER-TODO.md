Here is an **extremely detailed development plan** for the job scheduler based on the provided specification. It follows the RED / TEST / GREEN / LINT / TEST / COMMIT / REFACTOR / LINT / TEST / COMMIT cycle at each step.

---

# 🛠️ DEVELOPMENT PLAN: Scheduled Job Queue

Each unit builds one behavior or component from the spec and walks through the full TDD loop.

---

## 1. Define Job Data Model

### Goal: Implement `ScheduledJob` Pydantic model and DynamoDB key helpers

**RED**

* Add a failing test: `test_job_model_serializes_correctly`

**TEST**

* Run: `pytest tests/unit/test_models.py::test_job_model_serializes_correctly`

**GREEN**

* Implement `ScheduledJob` Pydantic model with fields from spec
* Implement `make_job_sk(scheduled_for: datetime, job_id: UUID)` and `parse_job_sk(sk: str)` helpers

**LINT**

* Run: `ruff check src tests && black src tests`

**TEST**

* Run: `pytest`

**COMMIT**

* Message: `feat: implement ScheduledJob model and SK helpers`

**REFACTOR**

* Clean up any duplication between model and helper functions

**LINT / TEST / COMMIT**

* As above
* Message: `refactor: simplify SK formatting logic`

✅ **Checklist**

* [ ] Pydantic model `ScheduledJob`
* [ ] Helpers for sort key formatting/parsing
* [ ] Unit tests verifying serialization and key logic

---

## 2. Write Job Table Client

### Goal: Implement DynamoDB client for fetching, inserting, updating jobs

**RED**

* Test: `test_job_persistence_round_trip`

**TEST**

* `pytest tests/unit/test_job_table.py`

**GREEN**

* Implement `JobTable.put_job()`, `get_due_jobs()`, `update_job_status()`
* Use Moto for mocking DynamoDB in tests

**LINT / TEST / COMMIT**

* Message: `feat: job table read/write methods with unit tests`

**REFACTOR**

* Extract conditional write logic to reusable helpers

**LINT / TEST / COMMIT**

* Message: `refactor: extracted condition helpers for job writes`

✅ **Checklist**

* [ ] `put_job`
* [ ] `get_due_jobs(now)`
* [ ] `update_job_status(job_id, status)`
* [ ] Unit tests with Moto

---

## 3. Implement Deduplication Index Logic

### Goal: Prevent rescheduling identical logical jobs

**RED**

* Test: `test_deduplication_prevents_duplicate_scheduling`

**TEST / GREEN**

* Implement `DeduplicationIndex.try_reserve(logical_id, date, job_ref)`
* Use conditional write with `ConditionExpression=attribute_not_exists(PK)`

**LINT / TEST / COMMIT**

* Message: `feat: implement deduplication index with conditional write`

**REFACTOR**

* Inline deduplication logic into a higher-level `schedule_if_needed()` function

**LINT / TEST / COMMIT**

* Message: `refactor: add schedule_if_needed convenience wrapper`

✅ **Checklist**

* [ ] Write deduplication record
* [ ] Check job presence
* [ ] Handle duplicate case
* [ ] Tests verifying conditional behavior

---

## 4. Write JobHandler Base and Dispatcher

### Goal: Parse payloads and route to handlers

**RED**

* Test: `test_dispatch_calls_correct_handler`

**TEST / GREEN**

* Create `BaseJobHandler` and dispatcher registry
* Validate payload using `payload_model().parse_obj(...)`
* Call `.handle(...)` on registered handler

**LINT / TEST / COMMIT**

* Message: `feat: implement dispatcher with type-based payload validation`

**REFACTOR**

* Move registration to decorator: `@register_handler("type")`

**LINT / TEST / COMMIT**

* Message: `refactor: add handler registration decorator`

✅ **Checklist**

* [ ] BaseJobHandler
* [ ] Registry
* [ ] Payload validation
* [ ] Tests for routing and error handling

---

## 5. Job Worker Poll Loop

### Goal: Poll DynamoDB and dispatch due jobs

**RED**

* Test: `test_worker_claims_and_dispatches_job`

**TEST / GREEN**

* Implement polling logic:

  * Query jobs SK <= now
  * Filter `status == pending`, lock expired/unset
* Attempt conditional update to claim
* On success: parse + dispatch
* On failure: mark as failed, apply backoff

**LINT / TEST / COMMIT**

* Message: `feat: implement job poll/claim/dispatch flow with retries`

**REFACTOR**

* Extract lease acquisition and failure flow

**LINT / TEST / COMMIT**

* Message: `refactor: extracted claim_and_run() from poller`

✅ **Checklist**

* [ ] Claim logic
* [ ] Lock expiration
* [ ] Status updates
* [ ] Dispatch + backoff
* [ ] All tests pass

---

## 6. Retry and Backoff Logic

### Goal: Ensure failed jobs are retried with exponential delay

**RED**

* Test: `test_backoff_applied_after_failure`

**TEST / GREEN**

* Implement exponential backoff calculation:

  ```python
  delay = base * (2 ** (attempts - 1))
  ```
* Update `scheduled_for` after failure
* Cap attempts at `max_attempts`, then mark as `dead_letter`

**LINT / TEST / COMMIT**

* Message: `feat: retry policy with exponential backoff and dead letter threshold`

**REFACTOR**

* Move retry logic to reusable `RetryPolicy` class

**LINT / TEST / COMMIT**

* Message: `refactor: encapsulate backoff logic in RetryPolicy`

✅ **Checklist**

* [ ] Backoff delay logic
* [ ] Cap on retries
* [ ] Tests for each case

---

## 7. Sentry Error Reporting

### Goal: Report all job errors to Sentry with full context

**RED**

* Test: `test_sentry_report_called_on_error`

**TEST / GREEN**

* Patch job dispatch to catch and report exceptions
* Include `job_id`, `payload`, `traceback` in report

**LINT / TEST / COMMIT**

* Message: `feat: sentry reporting for job failures`

**REFACTOR**

* Extract reporter to `JobErrorReporter`

**LINT / TEST / COMMIT**

* Message: `refactor: use JobErrorReporter for Sentry reporting`

✅ **Checklist**

* [ ] Error context
* [ ] Traceback included
* [ ] Mocked test verifies call

---

## 8. Integration Tests

### Goal: End-to-end test: schedule, claim, execute, complete

**RED**

* Test: `test_end_to_end_job_flow`

**TEST / GREEN**

* Set up:

  * Add job
  * Run worker
  * Assert job completes

**LINT / TEST / COMMIT**

* Message: `test: full job lifecycle e2e test`

**REFACTOR**

* Factor test harness helpers

**LINT / TEST / COMMIT**

* Message: `refactor: extracted integration test helpers`

✅ **Checklist**

* [ ] E2E coverage
* [ ] Setup + teardown
* [ ] Job status assertions

---

## 9. CLI Entrypoint

### Goal: Add `click`-based CLI to run worker loop

**RED**

* Test: `test_run_worker_command`

**TEST / GREEN**

* Add `click` command: `run-worker`
* Invoke poll loop in `while True:`

**LINT / TEST / COMMIT**

* Message: `feat: CLI worker runner with click`

**REFACTOR**

* Extract polling to `WorkerRunner` class

**LINT / TEST / COMMIT**

* Message: `refactor: use WorkerRunner for CLI entrypoint`

✅ **Checklist**

* [ ] Click command
* [ ] Runs loop
* [ ] Test command output with `CliRunner`

---

Would you like this formatted into a `TODO.md` file ready for handoff?
