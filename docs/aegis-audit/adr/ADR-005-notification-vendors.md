# ADR 005: Multi-Channel Emergency Notification Pipeline (Transactional Outbox)
**Status:** Approved (Phase 0 Baseline)  
**Date:** 2026-09-21  
**Decider Hat:** Principal Architect / Cybersecurity Analyst

---

## Context
When an emergency occurs, family contacts and emergency responders must be notified without delay. A failure in an external third-party SMS vendor must never abort the SOS creation transaction in the primary database.

## Decision
Implement the **Transactional Outbox Pattern**:
1. When an SOS is triggered, `sos_events` and per-contact `notification_deliveries` rows (`status: QUEUED`) are written in the same atomic database transaction.
2. Background asynchronous workers poll the outbox, dispatching messages across configured channels (FCM Push, DLT-compliant SMS, Email).
3. Delivery states transition: `QUEUED → SENT → DELIVERED | FAILED | SKIPPED`.
4. All valid contacts are processed independently. One recipient's network failure never blocks or delays notifications to other contacts.
