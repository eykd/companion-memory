# Work Sampling Prompt Specification

## Purpose

This feature schedules and dispatches random, evenly spaced Slack direct messages to users during their local workday (8am–5pm). Each message asks the user what they are currently working on and prompts them to reply using the `/log` command. These prompts are intended to improve engagement and self-tracking throughout the day.

---

## Global Configuration

* `WORK_SAMPLING_PROMPTS_PER_DAY` (integer): Global constant determining how many prompts each user receives daily. This must be defined in a shared configuration module.

---

## Scheduling

### Trigger

* A background scheduler job runs once daily at **midnight UTC** to schedule all of the day’s work sampling prompts.

### Module

* Implemented in a new file: `src/companion_memory/work_sampling_scheduler.py`

### Responsibilities

For each user returned by `UserSettingsStore`:

1. Determine the local date corresponding to midnight UTC.
2. Define the workday range as 8:00–17:00 in the user’s local timezone.
3. Divide this range evenly into **N = `WORK_SAMPLING_PROMPTS_PER_DAY`** intervals.
4. For each interval:

   * Select a single random time within the interval using a **deterministic PRNG** seeded with:

     ```
     seed = sha256(f"{user_id}-{local_date}-{slot_index}").digest()
     ```
   * Construct a logical job ID:

     ```python
     f"work_sampling_prompt:{user_id}:{local_date.isoformat()}:{slot_index}"
     ```
   * Use `DeduplicationIndex.try_reserve(logical_id)` to deduplicate.
   * Schedule a `ScheduledJob` of type `"work_sampling_prompt"` with:

     * `user_id`: Slack user ID
     * `scheduled_for`: UTC time corresponding to selected local time
     * `payload`: `{ "user_id": <SLACK_USER_ID>, "slot_index": <int> }`

---

## Job Dispatch and Handling

### Job Type

* Job type string: `"work_sampling_prompt"`

### Payload Model

* Defined in `job_models.py` or a new dedicated module:

```python
class WorkSamplingPayload(BaseModel):
    user_id: str
    slot_index: int
```

### Handler

* New handler module: `src/companion_memory/work_sampling_handler.py`
* Class: `WorkSamplingHandler`
* Registered with the `JobDispatcher` via `@register_handler("work_sampling_prompt")`

### Handler Responsibilities

1. Load Slack client.
2. Select a prompt variation from a hardcoded list using `random.choice`.
3. Send a direct message to the `user_id` with content like:

   > "What are you working on right now? You can reply using the `/log` command."

---

## Prompt Variations

Hardcoded into the handler module, for example:

```python
PROMPT_VARIATIONS = [
    "What are you working on right now?",
    "Got a minute? Log what you're doing with `/log`.",
    "Quick check-in: what's your focus at the moment?",
    "Still on track? Drop a note with `/log`.",
    "Pause and reflect: what are you doing right now?"
]
```

---

## Timezone Handling

* User timezone is loaded from `UserSettingsStore`.
* If no timezone is set, default to `UTC`.
* All scheduled times are calculated in local time and converted to UTC for scheduling.

---

## Deduplication

* Deduplication uses `DeduplicationIndex` with logical ID format:

  ```text
  work_sampling_prompt:{user_id}:{local_date}:{slot_index}
  ```

---

## Testing

### Unit Tests

* Test random time selection with seeded PRNG
* Test deduplication logic with logical ID
* Test payload serialization and handler dispatch
* Test handler behavior with mocked Slack client

### Integration

* Test full scheduling behavior given a mock user list and fixed seed
* Confirm correct job count and scheduling times
* Confirm handler sends a Slack DM with a valid prompt

---

## Deployment

* Add the new scheduler function to the distributed scheduler (in `scheduler.py`)
* Ensure it runs daily at midnight UTC
