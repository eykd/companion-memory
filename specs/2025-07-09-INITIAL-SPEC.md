# 🧠 Companion Memory — Project Specification

## Project Purpose

Companion Memory is a lightweight personal assistant for developers who operate with intermittent focus and irregular rhythms. It captures moments of progress, reflects back daily and weekly summaries, and helps reestablish continuity through gentle Slack-based interaction. The system uses a hybrid architecture: a webhook handler deployed on Fly.io, and a local scheduler running on macOS.

---

## 🧩 Core Features

### 1. `/log` Command (Manual Entry)

* Slack slash command `/log` accepts freeform text (e.g. “Debugged deploy script”).
* Webhook validates request with Slack signing secret.
* Entry is written to DynamoDB with sort key `log:<ISO-8601 timestamp>` under the partition key `user:<slack_user_id>`.
* Returns ephemeral confirmation in Slack.

### 2. Work Sampling Prompts (Random)

* Scheduler running locally sends 3–5 random DMs during work hours (e.g., 9am–5pm).
* Message: “What are you doing right now?”
* User replies naturally; message is logged like any other entry via the same DynamoDB pattern.
* These responses contribute to the same continuity and summary system.

### 3. Daily Prompt Summary

* Once daily, the system sends a Slack message with two summaries:

  * A **7-day** overview
  * A **1-day** focus report
* Uses the [`llm`](https://llm.datasette.io/en/stable/python-api.html) library to summarize all log entries for the given time window.
* Model is configurable via environment variable (e.g., OpenAI, Claude, local LLM).

**Slack Message Format:**

```markdown
## Here’s what you’ve been up to this past week:
{summary_week}

## Here’s what you were focused on yesterday:
{summary_day}
```

---

## 🗃 Data Storage (DynamoDB)

### Table: `CompanionMemoryLogs`

* **Partition key**: `user:<slack_user_id>`
* **Sort key**: One of the following:

  * `log:<timestamp>` — manual logs or sampling responses
  * `job:<id>` — persisted scheduled tasks

### Additional Fields

* `timestamp` — ISO 8601 format
* `text` — log content
* `log_id` — UUID (for uniqueness)
* `job_definition` — JSON (for APScheduler job metadata)

### Table Config

* Billing mode: `PAY_PER_REQUEST`
* Region: `us-west-2`

---

## 🧱 Technical Overview

### Webhook Component (Fly.io)

* Flask app deployed via Fly.io
* Responds to Slack `/log` requests
* Authenticates requests using Slack signing secret
* Writes to DynamoDB

### Scheduler Component (macOS)

* Python script using `APScheduler` (`BlockingScheduler`)
* Manages random work sampling prompts
* Sends daily summaries using `slack_sdk`
* Persists jobs to DynamoDB using a `job:<id>` sort key

---

## 🔐 Configuration & Secrets

### Required Environment Variables

* `SLACK_BOT_TOKEN`
* `SLACK_USER_ID`
* `SLACK_SIGNING_SECRET`
* `AWS_ACCESS_KEY_ID`
* `AWS_SECRET_ACCESS_KEY`
* `AWS_REGION`
* `DYNAMODB_TABLE`

Use `fly secrets` on Fly.io, and `.env` locally with `python-dotenv`.

---

## ⚙️ Tooling

### Project Setup

* Python 3.13
* Managed using [`uv`](https://github.com/astral-sh/uv`)
* Virtual environment, dependencies, and scripts declared in `pyproject.toml`

### Dependencies

* `Flask`
* `slack_sdk`
* `boto3`
* `python-dotenv`
* `APScheduler`
* `llm`

---

## 🚀 Deployment

### Fly.io (Webhook)

* Deployed via `fly launch`
* Container accepts incoming Slack requests

### macOS (Scheduler)

* Runs as a background process
* Can be triggered manually or started with login

---

## 🧪 Testing Strategy

### Architectural Principle

The system is designed using **hexagonal architecture** (also known as ports and adapters). Core logic (e.g., log storage, summarization, prompt scheduling) is defined against abstract interfaces. Concrete implementations (e.g., DynamoDB or in-memory) are supplied at runtime via dependency injection.

### Primary Test Goals

* Verify correctness of behavior without requiring AWS services or network I/O
* Enable fast, isolated, deterministic test runs for CI and local development

### Storage Abstraction

All reads and writes to logs and jobs pass through a storage interface such as:

```python
class LogStore:
    def write_log(self, user_id: str, timestamp: str, text: str, log_id: str): ...
    def fetch_logs(self, user_id: str, since: datetime): ...
```

### Production Adapter

* `DynamoLogStore`: reads/writes to AWS DynamoDB, using the partition/sort key strategy defined in the spec

### Test Adapter

* `MemoryLogStore`: in-memory `dict[str, list[dict]]` keyed by `user_id`
* Optionally supports time filtering and simulated job persistence

### Test Focus Areas

* `/log` endpoint: test request validation and logging logic using `MemoryLogStore`
* Work sampling: simulate scheduled prompts and user replies without sending real Slack messages
* Summary generation: test the summarizer module using fixed logs
* Scheduler state: ensure job persistence logic respects the `job:` namespace, even if mocked

### Additional Techniques

* Use `pytest` with fixtures for component isolation
* Mock `llm.complete()` or inject a summarization stub for deterministic tests
* Consider testing with SQLite or file-based persistence as an optional third adapter

## ✅ MVP Acceptance Criteria

* Manual logging via `/log` works
* Work sampling messages are sent and recorded
* Daily summaries are delivered with correct content
* Job state is preserved across restarts
* System is resilient and requires minimal maintenance
