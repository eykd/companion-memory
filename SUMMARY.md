# Companion Memory - Codebase Summary

## Overview

Companion Memory is a work activity tracking and summarization system that integrates with Slack to capture user logs and generate AI-powered summaries. The system features both time-based scheduling and event-driven job processing, follows hexagonal architecture principles, and uses DynamoDB for storage with distributed coordination for background jobs.

## Architecture

The system uses **hexagonal architecture** to separate business logic from external concerns:

- **Core Domain**: Business logic for log summarization, user settings, and time zone handling
- **Ports**: Protocol interfaces that define contracts (e.g., `LogStore`, `LLMClient`, `UserSettingsStore`)
- **Adapters**: Concrete implementations for external systems (DynamoDB, Slack API, LLM services)
- **Application Layer**: Flask web application for webhooks and CLI commands

### Key Design Patterns

- **Single Table Design**: DynamoDB uses a single table with composite keys (`PK`, `SK`) for all data
- **Distributed Scheduling**: Uses DynamoDB locks for coordinating background jobs across workers
- **Protocol-Based Dependency Injection**: Interfaces defined as Python Protocols for clean separation
- **Event-Driven Job Processing**: Asynchronous job queue with retries, deduplication, and distributed locking
- **Test-First Development**: Comprehensive test coverage with TDD practices

## Project Structure

```
src/companion_memory/
├── __init__.py                  # Package entry point
├── cli.py                      # Click-based CLI interface
├── commands.py                 # CLI command implementations
├── app.py                      # Flask web application
├── wsgi.py                     # WSGI entry point for production
├── exceptions.py               # Custom exception hierarchy
├── storage.py                  # Log storage interfaces and implementations
├── user_settings.py            # User settings storage
├── user_sync.py                # User profile synchronization from Slack
├── scheduler.py                # Distributed background job scheduling
├── summarizer.py               # AI-powered log summarization
├── llm_client.py               # LLM service integration
├── slack_auth.py               # Slack webhook signature validation
├── job_models.py               # Job queue data models
├── job_table.py                # DynamoDB job storage operations
├── job_dispatcher.py           # Type-safe job routing and validation
├── job_worker.py               # Job processing and execution
├── deduplication.py            # Job deduplication logic
├── retry_policy.py             # Exponential backoff and retry handling
└── daily_summary_scheduler.py  # Event-driven daily summary scheduling

tests/
├── test_*.py           # Test modules mirroring source structure
└── conftest.py         # Shared test fixtures
```

## Core Modules

### Application Layer

#### `cli.py` - Command Line Interface
- **Purpose**: Click-based CLI with commands for scheduler, web server, job worker, and Slack testing
- **Commands**:
  - `comem scheduler` - Run background scheduler
  - `comem web` - Run Flask development server
  - `comem job-worker` - Run standalone job worker
  - `comem slack-test` - Test Slack connectivity
- **Entry Point**: `comem` command via pyproject.toml

#### `commands.py` - Command Implementations
- **Purpose**: Implementation functions for CLI commands
- **Key Functions**:
  - `run_scheduler()` - Start background scheduler
  - `run_web_server()` - Start Flask development server
  - `run_job_worker()` - Start standalone job worker with polling loop
  - `test_slack_connection()` - Validate Slack API integration

#### `app.py` - Flask Web Application
- **Purpose**: HTTP server for Slack webhooks and API endpoints
- **Routes**:
  - `/` - Health check endpoint
  - `/scheduler/status` - Scheduler monitoring
  - `/slack/log` - Handle `/log` slash command
  - `/slack/events` - Slack events webhook
  - `/slack/lastweek`, `/slack/yesterday`, `/slack/today` - Summary commands
- **Features**: Signature validation, dependency injection, scheduler integration

#### `wsgi.py` - Production Entry Point
- **Purpose**: WSGI application for production deployment
- **Configuration**: Logging, Sentry integration, DynamoDB/LLM setup
- **Deployment**: Compatible with Gunicorn and other WSGI servers

### Storage Layer

#### `storage.py` - Log Storage
- **Protocol**: `LogStore` - Interface for log persistence
- **Implementations**:
  - `MemoryLogStore` - In-memory storage for testing
  - `DynamoLogStore` - DynamoDB persistence with single-table design
- **Features**: Timezone-aware queries, pagination support, UTC normalization

#### `user_settings.py` - User Settings Storage
- **Protocol**: `UserSettingsStore` - Interface for user preference storage
- **Implementation**: `DynamoUserSettingsStore` - DynamoDB storage
- **Data Model**: PK: `user#<USER_ID>`, SK: `settings`
- **Usage**: Currently stores user timezone preferences

### Business Logic

#### `summarizer.py` - AI-Powered Summarization
- **Protocol**: `LLMClient` - Interface for AI model interaction
- **Core Functions**:
  - `summarize_week()` - Weekly activity summary
  - `summarize_day()` - Daily activity summary
  - `summarize_yesterday()` - Previous day summary in user timezone
  - `summarize_today()` - Current day summary in user timezone
- **Features**: Timezone-aware date calculations, formatted prompts, automatic user sync
- **Legacy**: `check_and_send_daily_summaries()` - Replaced by event-driven job queue system

#### `llm_client.py` - LLM Integration
- **Implementation**: `LLMLClient` - Concrete LLM client using `llm` library
- **Configuration**: Model selection via `LLM_MODEL_NAME` environment variable
- **Default Model**: Claude 3.5 Haiku (`anthropic/claude-3-haiku-20240307`)
- **Error Handling**: Custom exceptions for configuration and generation errors

### Job Queue System

#### `job_models.py` - Job Data Models
- **Core Model**: `ScheduledJob` - Pydantic model for job queue entries
- **Attributes**: job_id, job_type, payload, scheduled_for, status, attempts, locking fields
- **Helpers**: `make_job_sk()`, `parse_job_sk()` - DynamoDB sort key utilities
- **Status Enum**: JobStatus (pending, in_progress, completed, failed, dead_letter)

#### `job_table.py` - Job Storage Operations
- **Class**: `JobTable` - DynamoDB operations for scheduled jobs
- **Methods**:
  - `put_job()` - Store new jobs with conditional writes
  - `get_due_jobs()` - Query jobs ready for processing
  - `update_job_status()` - Atomic status updates with locking
- **Design**: Uses single table with `PK: job`, `SK: scheduled#<timestamp>`

#### `job_dispatcher.py` - Type-Safe Job Routing
- **Protocol**: `BaseJobHandler` - Interface for job handlers
- **Class**: `JobDispatcher` - Routes jobs to registered handlers
- **Features**: Pydantic payload validation, type-safe handler registration
- **Registration**: `@register_handler` decorator for handler classes

#### `job_worker.py` - Job Processing Engine
- **Class**: `JobWorker` - Main job processing orchestrator
- **Methods**:
  - `poll_and_process_jobs()` - Main polling loop
  - `register_handler()` - Add job type handlers
  - `_claim_and_run()` - Atomic job claiming and execution
- **Features**: Distributed locking, error handling, Sentry integration

#### `deduplication.py` - Job Deduplication
- **Class**: `DeduplicationIndex` - Prevents duplicate job scheduling
- **Method**: `try_reserve()` - Atomic reservation with logical job IDs
- **Design**: Uses conditional writes with `PK: dedup#<logical_id>#<date>`
- **Purpose**: Ensures exactly-once job scheduling for identical requests

#### `daily_summary_scheduler.py` - Daily Summary Scheduling
- **Purpose**: Event-driven daily summary job scheduling system
- **Core Functions**:
  - `schedule_daily_summaries()` - Main scheduling function (runs daily at midnight UTC)
  - `get_next_7am_utc()` - Calculates next 7:00 AM in user's timezone
  - `make_daily_summary_job_id()` - Generates logical job IDs for deduplication
- **Handler**: `DailySummaryHandler` - Processes daily summary jobs
- **Features**: Timezone-aware scheduling, job deduplication, automatic user settings integration
- **Migration**: Replaced legacy polling-based daily summary system

#### `retry_policy.py` - Failure Handling
- **Class**: `RetryPolicy` - Configurable retry and backoff logic
- **Methods**:
  - `calculate_delay()` - Exponential backoff calculation
  - `should_retry()` - Determines if job should be retried
  - `is_dead_letter()` - Identifies jobs exceeding max attempts
- **Features**: Configurable base delay, max attempts, dead letter handling

### Infrastructure

#### `scheduler.py` - Distributed Scheduling
- **Components**:
  - `SchedulerLock` - DynamoDB-based distributed locking
  - `DistributedScheduler` - APScheduler with distributed coordination
  - `get_slack_client()` - Slack SDK client factory
- **Jobs**:
  - Heartbeat logging (60 seconds)
  - Daily summary checking (hourly)
  - User timezone sync (6 hours)
  - Job worker polling (30 seconds) - Integrated event-based job processing
- **Features**: Lock acquisition/refresh, worker coordination, automatic failover, unified job processing

#### `user_sync.py` - Slack Profile Synchronization
- **Functions**:
  - `sync_user_timezone()` - Scheduled sync from environment variable
  - `sync_user_timezone_from_slack()` - On-demand sync for specific users
- **Integration**: Automatic fallback in summarizer when user record missing
- **Error Handling**: Graceful degradation to UTC timezone

#### `slack_auth.py` - Security
- **Function**: `validate_slack_signature()` - HMAC-SHA256 signature verification
- **Purpose**: Ensures webhook requests originate from Slack
- **Implementation**: Secure comparison using `hmac.compare_digest()`

#### `exceptions.py` - Error Handling
- **Hierarchy**:
  - `CompanionMemoryError` - Base application exception
  - `LLMConfigurationError` - LLM setup issues
  - `LLMGenerationError` - LLM generation failures
- **Usage**: Specific exceptions for different failure modes

## Data Model

### DynamoDB Single Table Design

The system uses a single DynamoDB table (`CompanionMemory`) with the following patterns:

#### Log Entries
- **PK**: `user#<SLACK_USER_ID>`
- **SK**: `log#<ISO_TIMESTAMP>`
- **Attributes**: `user_id`, `timestamp`, `text`, `log_id`

#### User Settings
- **PK**: `user#<SLACK_USER_ID>`
- **SK**: `settings`
- **Attributes**: `timezone`, other user preferences

#### Scheduler Locks
- **PK**: `system#scheduler`
- **SK**: `lock#main`
- **Attributes**: `process_id`, `timestamp`, `ttl`, `instance_info`

#### Scheduled Jobs
- **PK**: `job`
- **SK**: `scheduled#<ISO_TIMESTAMP>`
- **Attributes**: `job_id`, `job_type`, `payload`, `status`, `attempts`, `locked_by`, `lock_expires_at`

#### Job Deduplication Index
- **PK**: `dedup#<LOGICAL_ID>#<DATE>`
- **SK**: `index`
- **Attributes**: `job_pk`, `job_sk`, `reserved_at`

### Environment Variables

#### Required
- `SLACK_BOT_TOKEN` - Slack app bot token
- `SLACK_SIGNING_SECRET` - Slack webhook signature verification

#### Optional
- `SLACK_USER_ID` - Default user for scheduled sync jobs
- `DAILY_SUMMARY_USERS` - Comma-separated user IDs for 7am summaries
- `LLM_MODEL_NAME` - AI model selection (default: Claude 3.5 Haiku)
- `SENTRY_DSN` - Error tracking configuration

## Testing Strategy

### Test Organization
- **Structure**: Tests mirror source module structure (`test_<module>.py`)
- **Location**: `tests/` directory with shared fixtures in `conftest.py`
- **Coverage**: 100% line coverage maintained for all source code

### Testing Approaches

#### Unit Testing
- **Framework**: pytest with extensive mocking
- **Protocols**: Mock implementations for external dependencies
- **Isolation**: Each module tested independently
- **Fixtures**: Reusable test data and mock objects

#### Integration Testing
- **DynamoDB**: Tests with mocked boto3 resources
- **Slack API**: Mocked WebClient interactions
- **LLM**: Mocked model responses
- **Flask**: Full application testing with test client

#### Test Quality Gates
- **Coverage**: 100% line coverage required
- **Linting**: Ruff with comprehensive rule set
- **Type Checking**: mypy with strict configuration
- **TDD Process**: Red-Green-Refactor cycle enforced

### Test Execution
- **Command**: `./scripts/runtests.sh` (wrapper around pytest)
- **Coverage Reporting**: Terminal output with missing lines
- **CI Integration**: All tests must pass before commits

## Development Practices

### Code Quality
- **Style**: PEP8 with Ruff formatting and linting
- **Type Safety**: Full type annotations with mypy validation
- **Documentation**: Google-style docstrings for all public APIs
- **Conventions**: Documented in `CLAUDE.md` project guidelines

### Development Workflow
- **TDD**: Test-first development with Red-Green-Refactor
- **Architecture**: Hexagonal architecture with clean separation
- **Dependencies**: uv for package management with lock files
- **Commits**: Conventional commit messages with automated testing

### Quality Tools
- **Formatter**: `uv run ruff format`
- **Linter**: `uv run ruff check --fix`
- **Type Checker**: `uv run mypy src tests`
- **Test Runner**: `./scripts/runtests.sh`
- **Coverage**: pytest-cov with 100% requirement

## Deployment

### Production Environment
- **WSGI**: Gunicorn with multiple workers
- **Storage**: AWS DynamoDB for persistence
- **Monitoring**: Sentry for error tracking
- **Logging**: Structured logging to stdout
- **Scheduling**: Distributed coordination across workers
- **Job Processing**: Unified time-based and event-driven job execution

### Infrastructure Requirements
- **AWS**: DynamoDB table with appropriate IAM permissions
- **Slack**: App with bot token and webhook endpoints
- **LLM**: Anthropic API access or compatible service
- **Runtime**: Python 3.13+ with uv package manager

This architecture provides a robust, scalable system for work activity tracking with clean separation of concerns, unified job processing (both time-based and event-driven), comprehensive testing, and production-ready deployment capabilities. The system supports both immediate webhook responses and asynchronous background processing with automatic retries and failure handling.
