# **Implementation Plan: Async Summary Endpoints**

## ✅ **PRECONDITIONS**

* Existing summary functions for `today`, `yesterday`, `lastweek`
* Working Slack client and message-sending helper
* Working job scheduler and logical job IDs
* App scaffolding with `/summary/*` endpoints in place

---

## 🔧 PHASE 1: Add `generate_summary` job

### 🔴 RED: Write a failing test for summary job

* `test_generate_summary_enqueues_send_job`
* Set up mock user and range (`today`)
* Call `generate_summary_job(user_id, range)`
* Assert that `send_slack_message_job` is scheduled with expected message

### ✅ TEST

* Run only this test to confirm failure

### 🟢 GREEN: Implement `generate_summary_job`

* Create function `generate_summary_job(user_id: str, range: str)`
* Retrieve summary using existing summarization logic
* Construct Slack message
* Generate UUID1
* Enqueue `send_slack_message_job` with ephemeral payload

### 🧹 LINT

* Run linters (e.g. `ruff`, `black`, `mypy`, `pyright`)

### ✅ TEST

* Run all tests

### 💾 COMMIT

```
feat: add generate_summary_job that enqueues Slack delivery
```

### ♻️ REFACTOR

* Extract helper: `get_summary(user_id, range)`
* Validate `range` early

### 🧹 LINT

### ✅ TEST

### 💾 COMMIT

```
refactor: extract summary generation logic to helper
```

---

## 🔧 PHASE 2: Add `send_slack_message` job

### 🔴 RED: Write failing test for Slack delivery

* `test_send_slack_message_sends_text`
* Provide ephemeral payload with `slack_user_id` and `message`
* Use Slack SDK mock
* Assert message is sent

### ✅ TEST

* Run this test

### 🟢 GREEN: Implement `send_slack_message_job`

* Accept ephemeral dict
* Use Slack WebClient to `chat.postMessage`
* Log INFO and DEBUG

### 🧹 LINT

### ✅ TEST

### 💾 COMMIT

```
feat: add send_slack_message_job to deliver messages
```

### ♻️ REFACTOR

* Add UUID logging
* Add retry decorator if available

### 🧹 LINT

### ✅ TEST

### 💾 COMMIT

```
refactor: add UUID logging and retry handling
```

---

## 🔧 PHASE 3: Make endpoint enqueue job and return 204

### 🔴 RED: Write failing test for endpoint

* `test_summary_today_endpoint_enqueues_job`
* Hit `/summary/today` as mock user
* Assert HTTP 204
* Assert job with ID `summary:today:{user_id}` was scheduled

### ✅ TEST

### 🟢 GREEN: Update endpoint implementation

* Extract `user_id` from request
* Schedule job with logical ID
* Use deduplication logic (e.g. skip if job ID exists)
* Return 204

### 🧹 LINT

### ✅ TEST

### 💾 COMMIT

```
feat: make summary endpoint schedule job and return 204
```

### ♻️ REFACTOR

* Extract `schedule_summary_job(user_id, range)` helper

### 🧹 LINT

### ✅ TEST

### 💾 COMMIT

```
refactor: extract job scheduling logic to helper
```

---

## 🔧 PHASE 4: Add fallback to inline summary generation

### 🔴 RED: Write test for fallback

* `test_summary_today_fallback_inline_if_scheduler_unavailable`
* Simulate missing scheduler
* Assert summary is generated and sent inline
* Assert HTTP 204

### ✅ TEST

### 🟢 GREEN: Implement fallback mode

* Detect scheduler presence (env var or runtime check)
* If unavailable, run `generate_summary_job` directly

### 🧹 LINT

### ✅ TEST

### 💾 COMMIT

```
feat: add fallback to inline execution when scheduler disabled
```

---

## 🔧 PHASE 5: Add logging

### 🔴 RED: Write test for logging (optional)

* `test_generate_summary_logs_info`
* Use log capture fixture
* Assert presence of `INFO` entries

### ✅ TEST

### 🟢 GREEN: Add INFO + DEBUG logging

* Each task logs on start and success
* Include job ID, UUID, user ID, and range

### 🧹 LINT

### ✅ TEST

### 💾 COMMIT

```
chore: add structured logging to summary and Slack jobs
```

---

## ✅ FINAL CHECKLIST

* [ ] Summary jobs generate content and schedule delivery
* [ ] Slack job sends ephemeral message
* [ ] Endpoints return immediately with 204
* [ ] Fallback works without scheduler
* [ ] Job IDs are logical and deduplicated
* [ ] Logging is present and informative
* [ ] Code is tested, linted, and committed

---

Would you like a parallel document version of this plan?
