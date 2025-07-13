# TODO: Implement `work_sampling_prompt` Feature

This plan follows a detailed TDD (Red/Green/Refactor) development process for implementing the work sampling prompt feature using the job scheduling architecture established in the Companion Memory project. Each phase includes linting, testing, and committing checkpoints. We assume 100% test coverage and strict type/lint gates throughout.

---

## 1. RED: Define Job Payload

* [ ] Create `WorkSamplingPayload` class in `job_models.py` or new module
* [ ] Add required fields: `user_id: str`, `slot_index: int`
* [ ] Write unit test in `test_job_models.py` to validate schema

### Checklist

* [ ] `WorkSamplingPayload` class exists
* [ ] Fields are type-annotated
* [ ] Pydantic validation is tested

---

## 2. GREEN: Implement Payload Model

* [ ] Implement `WorkSamplingPayload` with type annotations
* [ ] Make sure mypy passes
* [ ] Run `pytest` on test file

### Checklist

* [ ] All tests pass
* [ ] Lint: `ruff check --fix`
* [ ] Type: `mypy src tests`
* [ ] Commit: `feat: add WorkSamplingPayload`

---

## 3. RED: Create Job Handler Stub

* [ ] Create `work_sampling_handler.py`
* [ ] Define `WorkSamplingHandler` class with `handle()` stub
* [ ] Register handler with `@register_handler("work_sampling_prompt")`
* [ ] Write unit test in `test_work_sampling_handler.py` to ensure job dispatch and routing

### Checklist

* [ ] `handle()` is called for correct job type
* [ ] Basic handler dispatch logic tested

---

## 4. GREEN: Implement Basic Handler Functionality

* [ ] Implement `handle()` method to:

  * Load Slack client
  * Randomly choose from hardcoded prompt list
  * Send DM to `user_id`
* [ ] Add Slack client fixture to test
* [ ] Validate Slack API was called with expected payload

### Checklist

* [ ] Prompts hardcoded in module
* [ ] Slack API interaction mocked
* [ ] Prompt is sent
* [ ] Lint/type check/test
* [ ] Commit: `feat: implement WorkSamplingHandler`

---

## 5. REFACTOR: Improve Handler Internals

* [ ] Extract `PROMPT_VARIATIONS` list to module scope
* [ ] Extract Slack DM function if needed

### Checklist

* [ ] Readable, modular code
* [ ] Lint/type/test
* [ ] Commit: `refactor: extract prompt logic`

---

## 6. RED: Scheduler Function Test Stub

* [ ] Create `work_sampling_scheduler.py`
* [ ] Write test `test_work_sampling_scheduler.py`

  * Patch user store
  * Patch deduplication index
  * Patch job table
* [ ] Test that N jobs are scheduled for one user

### Checklist

* [ ] Verify local date computation
* [ ] Verify job IDs
* [ ] Verify seeded PRNG timing logic

---

## 7. GREEN: Implement Scheduler Logic

* [ ] Implement function `schedule_work_sampling_jobs()`:

  * Load all users
  * For each, compute local date and 8–17 window
  * Divide into N slots
  * Seed PRNG with `sha256(f"{user_id}-{date}-{slot_index}")`
  * Use dedup index
  * Create and write `ScheduledJob`

### Checklist

* [ ] Local timezone respected
* [ ] UTC conversion validated
* [ ] Determinism ensured
* [ ] Lint/type/test
* [ ] Commit: `feat: implement work sampling scheduler`

---

## 8. REFACTOR: Finalize Job ID and Seeding Utilities

* [ ] Move `make_work_sampling_job_id()` to shared module or local util
* [ ] Extract PRNG helper if reused

### Checklist

* [ ] DRY code
* [ ] Lint/type/test
* [ ] Commit: `refactor: extract job ID and PRNG helpers`

---

## 9. GREEN: Register Scheduler in Background Job Runner

* [ ] In `scheduler.py`, register `schedule_work_sampling_jobs()` to run daily at midnight UTC
* [ ] Add test coverage in `test_scheduler.py` if applicable

### Checklist

* [ ] Lint/type/test
* [ ] Commit: `feat: register work sampling scheduler`

---

## 10. Final Tests and Verification

* [ ] Run full test suite
* [ ] Ensure coverage 100%
* [ ] Run `ruff format`, `ruff check`, `mypy`
* [ ] Manual test: job appears in table; Slack message is sent at expected time

### Checklist

* [ ] All green
* [ ] Commit: `chore: verify work_sampling_prompt feature complete`
