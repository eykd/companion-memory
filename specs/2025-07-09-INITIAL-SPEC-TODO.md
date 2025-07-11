# ✅ Companion Memory — Development Plan (TDD + Hexagonal Architecture)

This file outlines an incremental, test-driven development (TDD) plan for implementing the Companion Memory project. Each step strictly follows the Red/Green/Refactor/Commit cycle.

---

## ✅ PHASE 1: Log Storage Abstraction

### Step 1: Define LogStore interface

* RED: Write a failing test that tries to call `write_log()` and `fetch_logs()` on a log store instance.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Define a `LogStore` protocol or abstract base class.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Add LogStore interface with write/fetch methods`
* REFACTOR: Make it better.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor LogStore interface`

### Step 2: Implement MemoryLogStore - write

* RED: Write a failing test that verifies `write_log()` stores a record.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Implement `MemoryLogStore.write_log()` using an in-memory `dict`.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Implement write_log for MemoryLogStore`
* REFACTOR: Make it better.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor MemoryLogStore write logic`

### Step 3: Implement MemoryLogStore - fetch

* RED: Write a failing test that fetches logs within a date range.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Implement `fetch_logs()` to filter from memory.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Implement fetch_logs for MemoryLogStore`
* REFACTOR: Extract shared timestamp handling logic.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor timestamp filtering logic`

---

## ✅ PHASE 2: `/log` Endpoint (Flask)

### Step 4: Create Flask app

* RED: Write a failing test that root URL returns 200.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Create basic Flask app with healthcheck.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Add Flask app with healthcheck route`
* REFACTOR: Move app to `app.py`, extract create\_app().
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor app structure`

### Step 5: Validate Slack signature

* RED: Write a failing test that invalid signature returns 403.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Implement Slack signing secret validation.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Secure /log with Slack signature verification`
* REFACTOR: Move signature logic to helper.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor Slack signature helper`

### Step 6: Accept and store `/log` entries

* RED: Write a failing test valid `/log` request triggers `write_log()`.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Implement `/log` route to parse and store entry.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Add /log endpoint to store logs`
* REFACTOR: Extract request parsing and formatting.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor /log parsing logic`

---

## ✅ PHASE 3: Scheduler + Work Sampling

### Step 7: Set up APScheduler

* RED: Write a failing test that a job runs after a short delay.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Add `BlockingScheduler` with dummy job.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Set up basic APScheduler`
* REFACTOR: Make it better.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor scheduler base config`

### Step 8: Send random sampling prompts

* RED: Write a failing test that a job sends Slack DM via mocked client.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Schedule random "What are you doing?" messages.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Send work sampling DMs at random intervals`
* REFACTOR: Extract DM sender into Slack client adapter.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor Slack DM sender`

### Step 9: Handle sampling responses

* RED: Simulate sampling response and expect storage.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Accept responses via `/log` and log them.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Log sampling responses via /log`
* REFACTOR: Make it better.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor sampling response handling`

---

## ✅ PHASE 4: DynamoDB Integration

### Step 10: Implement DynamoLogStore - write

* RED: Write a failing test `write_log()` using Dynamo mock.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Implement write using `boto3.put_item()`.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Write logs to DynamoDB`
* REFACTOR: Extract partition/sort key generator.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor Dynamo key strategy`

### Step 11: Implement DynamoLogStore - fetch

* RED: Write a failing test `fetch_logs()` returns recent logs.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Query using key prefix and time filter.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Read logs from DynamoDB by date`
* REFACTOR: Handle pagination, fallback.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor Dynamo fetch logic`

---

## ✅ PHASE 5: Summarization

### Step 12: Summarize past week

* RED: Write a failing test that 7-day logs are summarized with mock `llm.complete()`.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Generate 7-day summary and format message.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Generate 7-day summary with llm`
* REFACTOR: Extract prompt builder and message formatter.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor summary prompt logic`

### Step 13: Summarize past day

* RED: Same structure as above but for 1-day context.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Generate and append 1-day summary.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Generate 1-day summary with llm`
* REFACTOR: Combine shared logic with 7-day.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor daily/weekly summarizer`

### Step 14: Send summary message

* RED: Write a failing test that combined summary is sent to Slack.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Format and send via Slack client.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Send summary DM to user`
* REFACTOR: Make it better.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor summary delivery`

---

## ✅ PHASE 6: CLI

### Step 15: Add CLI entrypoint

* RED: Write a failing test `companion-scheduler` prints help text.
* LINT: Run the linters and fix any errors you encounter.
* GREEN: Implement `click`-based CLI with `run` command.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Add CLI entrypoint using click`
* REFACTOR: Move command handlers to module.
* LINT: Run the linters and fix any errors you encounter.
* TEST: Run the complete test suite and fix any errors you encounter.
* COMMIT: `Refactor CLI command structure`
