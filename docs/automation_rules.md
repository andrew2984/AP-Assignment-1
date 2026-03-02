# Automation Rules — Background Monitoring (Lean SLA Model)

**Project:** Test Machine Booking 
**Scope:** Formal specification for all time-based automation executed by the background monitoring system, including **current** and **planned** rules.  
**Rule set version:** `automation_rules_v1.0`  
**Out of scope:** Implementation code, schema redesign, access-window state machine.

---

## 1. Purpose

This document defines the **time-based rules** used by the background monitoring system to:
- evaluate and act on time-based states (e.g., pending approvals, stale requests)
- automatically flag operational events (e.g., no-shows)
- trigger warnings and breaches against agreed thresholds
- optionally expire stale requests
- produce consistent, auditable system actions

This ruleset exists to ensure all automation is:
- deterministic
- testable
- auditable
- consistent across the UI and background jobs

---

## 2. Terminology and Assumptions

### 2.1 Time Source and Timezone
- All automation compares timestamps in **UTC**.
- Database timestamps are treated as UTC (even if displayed in local time).

### 2.2 “Now”
- “Now” (`now_utc`) is the timestamp captured at the start of each monitoring job run.
- All evaluations within that run use the same `now_utc`.

### 2.3 System Actor
System-driven events must identify the actor as:
- `actor_type = SYSTEM`
- `actor_id = scheduler`
- For schemas that only support an email identity, use: `actor_email = "system@scheduler"`

### 2.4 Rule Status Labels
To avoid ambiguity, each rule in this document is labelled as one of:
- **IMPLEMENTED:** exists in the current codebase automation jobs
- **PLANNED:** agreed target rule, not yet implemented

---

## 3. Current Implemented Automations (as of `main`)

### 3.1 Notification Dispatch (IMPLEMENTED)
**Purpose:** deliver queued notifications.

- **Job cadence:** runs periodically (background scheduler)
- **Selection rule:** notifications where `sent_at is null`
- **Action:** mark `sent_at = now_utc` after simulated dispatch
- **Idempotency:** a notification is only dispatched once because `sent_at` is set

**Audit expectation (recommended):**
- Dispatch actions MAY be audited, but are not required for SLA evidence (message-level persistence already exists).

### 3.2 Booking No-Show Detection (IMPLEMENTED)
**Entity:** `BookingRequest`

A booking is considered a **no-show** when all are true:
- `status == "approved"`
- `end_at < (now_utc - 15 minutes)`
- `checked_in == false`
- `no_show == false`

**Action:**
- set `no_show = true`
- queue a notification to the requester: *"No-show recorded for booking #{id}..."*

**Idempotency / de-duplication:**
- A booking is only marked once because the rule only applies when `no_show == false`.

**Audit (recommended):**
- When a booking transitions to `no_show=true`, an audit event SHOULD be recorded (see Section 9).

---

## 4. Planned / Target Automations (Lean SLA Model)

### 4.1 Entity in Scope: Access Request (PLANNED)
An **Access Request** is a permission-gate record that represents a user request to gain authorised access (e.g., to a site / controlled resource), requiring an approval decision.

Access Requests are expected to have (at minimum):
- an identifier (`id`)
- a `status`
- a creation timestamp (`created_at`)
- optionally decision fields (`resolved_at`, `resolved_by`, `decision_note`)
- optionally a status/audit history record

---

## 5. Canonical Status Values

### 5.1 Canonical casing
Canonical status values in this project are documented in **lowercase** to match current model conventions.

### 5.2 AccessRequest.status (PLANNED canonical model)
| Status | Meaning |
|---|---|
| `pending` | Awaiting decision/approval |
| `approved` | Access granted |
| `rejected` | Access denied |
| `revoked` | Access was granted then withdrawn |
| `expired` | Automatically closed due to exceeding time limits (system action) |

**Notes**
- Only `pending` is subject to SLA evaluation in this lean ruleset.
- `expired` is optional in implementation, but recommended for strong automation evidence.

---

## 6. SLA Thresholds (Lean) — Access Requests (PLANNED)

These thresholds are intentionally simple and easy to demonstrate. Adjust only by updating this document and bumping the rule version.

### 6.1 Overdue Approval SLA
**Applies when:** `status == "pending"`

- **SLA start time:** `created_at`
- **Warning threshold:** `created_at + 8 hours`
- **Breach threshold:** `created_at + 48 hours`

### 6.2 Auto-expiry (Recommended)
**Applies when:** `status == "pending"`

- **Expiry threshold:** `created_at + 7 days`
- **Outcome:** transition to `expired`

---

## 7. Classification Rules (PLANNED)

For a given Access Request in `pending`, compute elapsed time:

`age = now_utc - created_at`

Classify as:

1. **OK**
   - Condition: `age < 8 hours`
   - Meaning: No SLA action required.

2. **SLA_WARNING_APPROVAL**
   - Condition: `8 hours <= age < 48 hours`
   - Meaning: Approvals are overdue soon; prompt action.

3. **SLA_BREACH_APPROVAL**
   - Condition: `48 hours <= age < 7 days`
   - Meaning: SLA is breached; escalate.

4. **AUTO_EXPIRE**
   - Condition: `age >= 7 days`
   - Meaning: Request is stale; close automatically.

**Priority rule:** If multiple thresholds could apply, choose the most severe by time:
`AUTO_EXPIRE` > `SLA_BREACH_APPROVAL` > `SLA_WARNING_APPROVAL` > `OK`

---

## 8. Actions (Spec-Level)

The rule engine returns **structured actions**. The action handler applies them.

### 8.1 Action Types
| Action | Description |
|---|---|
| `NOTIFY_WARNING` | Queue a warning notification |
| `NOTIFY_BREACH` | Queue a breach/escalation notification |
| `STATUS_SET_EXPIRED` | Change status from `pending` to `expired` |
| `AUDIT_EVENT` | Write a structured audit record of automated action |

### 8.2 Notification recipients (PLANNED)
For AccessRequest SLA events, notifications are sent to:
- **Admins** (users with role `admin`)

*(No requester notifications are required by this v1.0 ruleset.)*

### 8.3 Action Rules
#### A) Warning
If classification is `SLA_WARNING_APPROVAL`:
- Queue `NOTIFY_WARNING` to admins
- Write `AUDIT_EVENT` with reason code `SLA_WARNING_APPROVAL`

#### B) Breach
If classification is `SLA_BREACH_APPROVAL`:
- Queue `NOTIFY_BREACH` to admins
- Write `AUDIT_EVENT` with reason code `SLA_BREACH_APPROVAL`

#### C) Auto-expire
If classification is `AUTO_EXPIRE`:
- Apply `STATUS_SET_EXPIRED`
- Queue `NOTIFY_BREACH` to admins (or a dedicated “expired” message — implementation choice)
- Write `AUDIT_EVENT` with reason code `AUTO_EXPIRE`

---

## 9. Idempotency and De-duplication Rules

Automation must be safe to run repeatedly without spamming users.

### 9.1 Notification De-duplication
- A given request should receive **at most one** warning notification for `SLA_WARNING_APPROVAL`.
- A given request should receive **at most one** breach notification for `SLA_BREACH_APPROVAL`.
- Auto-expiry should occur **once**.

### 9.2 How to Achieve De-duplication (Implementation-Agnostic)
Any one of the following is acceptable:
- check audit/history records for existing reason codes before sending
- store a “last_notified_at + notification_type” marker
- store boolean markers (e.g., `warning_sent`, `breach_sent`) — only if absolutely necessary

This document requires the behaviour; it does not mandate a storage mechanism.

---

## 10. Audit Event Specification (System Actions)

All automated actions that affect operational state should write a structured audit event.

### 10.1 Minimum Audit Fields (canonical)
| Field | Type | Example |
|---|---|---|
| `event_id` | string/uuid | `...` |
| `timestamp_utc` | ISO-8601 | `2026-03-02T15:10:00Z` |
| `actor_type` | enum | `SYSTEM` |
| `actor_id` | string | `scheduler` |
| `actor_email` | string | `system@scheduler` |
| `entity_type` | enum | `AccessRequest` |
| `entity_id` | int/string | `123` |
| `action` | enum | `SLA_WARNING_SENT`, `SLA_BREACH_SENT`, `STATUS_CHANGED`, `NO_SHOW_RECORDED` |
| `previous_status` | string/null | `pending` |
| `new_status` | string/null | `expired` |
| `reason_code` | enum | `SLA_WARNING_APPROVAL`, `SLA_BREACH_APPROVAL`, `AUTO_EXPIRE`, `NO_SHOW_RULE` |
| `rule_version` | string | `automation_rules_v1.0` |
| `details` | JSON | `{ "age_hours": 52, "warning_hours": 8, "breach_hours": 48 }` |

### 10.2 Audit Rules
- If no change occurs, do not log an event.
- If multiple actions occur in one run (e.g., expire + notify), either:
  - log one combined event with multiple action tags, or
  - log multiple events with the same `event_id` grouping key.

### 10.3 Mapping to current `AuditLog` table (IMPLEMENTATION COMPATIBILITY NOTE)
The current codebase audit storage (e.g., `AuditLog`) may only support:
- `at` (timestamp)
- `actor_email`
- `action` (string)
- `detail` (string)

Until a richer schema exists, the canonical audit fields MUST be encoded as follows:

- `AuditLog.at` = `timestamp_utc`
- `AuditLog.actor_email` = `"system@scheduler"` for system actions
- `AuditLog.action` = a stable string, recommended format:
  - `automation:<reason_code>` (e.g., `automation:SLA_WARNING_APPROVAL`)
  - `automation:NO_SHOW_RULE`
- `AuditLog.detail` = a single-line structured payload (JSON or key=value), recommended:
  - `rule_version=automation_rules_v1.0 entity_type=AccessRequest entity_id=123 previous_status=pending new_status=expired details={"age_hours":52,...}`

This preserves audit traceability without requiring schema redesign.

---

## 11. Acceptance Checklist (Task 19)

- [x] `docs/automation_rules.md` created/updated and committed
- [x] Thresholds explicitly defined: warning, breach, expiry
- [x] Canonical status values agreed and documented
- [x] Audit fields and system actor definition documented
- [x] No implementation code included

---
