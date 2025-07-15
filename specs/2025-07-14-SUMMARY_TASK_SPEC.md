# **Specification: Move Summary Endpoints to Asynchronous Execution**

## **Overview**

This change updates the `/summary/{range}` endpoints (`today`, `yesterday`, `lastweek`) to enqueue asynchronous jobs that generate and send summaries to Slack, instead of computing them inline during the request/response cycle. The endpoints will return immediately with HTTP 204.

## **Endpoints**

* `POST /summary/today`
* `POST /summary/yesterday`
* `POST /summary/lastweek`

### **Request**

* Authenticated request from user
* No payload

### **Response**

* HTTP 204 No Content
* Always returns immediately, regardless of job execution state

---

## **Job Scheduling**

### **Primary Job: `generate_summary:{range}:{user_id}`**

* Scheduled by the endpoint handler
* Idempotent: Only one job per `user_id` per `range` may be enqueued at a time
* Executes the following:

  * Retrieves the summary for the requested time range
  * Logs `INFO` message on start and success
  * Passes the result to the follow-up job (below)

### **Follow-up Job: `send_slack_message:{uuid}`**

* Enqueued by the `generate_summary` job
* Ephemeral payload contains:

  * Slack channel or user ID
  * Slack message content (the summary)
* Executes the following:

  * Sends the message to Slack
  * Logs `INFO` message on success
  * Logs `DEBUG` for request/response

---

## **Job ID Format**

* Summary generation: `summary:{range}:{user_id}`
* Slack send: `send_slack_message:{uuid}` (UUIDv1 for tracing)
* Ensures deduplication and traceability

---

## **Retry and Failure Handling**

* Both jobs:

  * Retry on failure with exponential backoff
  * Log exceptions using standard job error logging

---

## **Fallback Mode**

If the job scheduler is not running (e.g. dev or test environments):

* The summary is generated and sent inline
* Logs a warning or `DEBUG` that fallback was triggered

---

## **Logging**

Each task logs:

* `INFO`: Task start and success
* `DEBUG`: Intermediate details (e.g. timing, Slack response)
