---
layout: default
title: "ADR-006: Separate OpsEventLog from Tenant AuditLog"
---
# ADR-006: Separate OpsEventLog from Tenant AuditLog

**Date:** 2026-03-19
**Status:** Accepted

## Context

The existing `AuditLog` model uses a constrained `ACTION_CHOICES` field (`create`, `update`, `delete`) designed for tenant-scoped data operations. The ops dashboard required logging of authentication events (`ops_login`, `ops_login_failed`, `otp_setup`, `otp_verified`, `otp_failed`, `ops_logout`) which do not fit this schema.

Options considered:
1. Extend `AuditLog.ACTION_CHOICES` with ops event types
2. Add a free-text `detail` field to `AuditLog`
3. Create a separate `OpsEventLog` model in the `ops_dashboard` app

## Decision

Create a separate `OpsEventLog` model in the `ops_dashboard` app with its own `EVENT_CHOICES`, `ip_address`, `detail`, and `timestamp` fields.

## Rationale

- Tenant audit logs and ops authentication events are different concerns with different consumers
- Extending `AuditLog` would couple tenant data integrity logging to platform security logging
- A separate model keeps ops concerns self-contained in the `ops_dashboard` app
- No migration impact on the existing `audit` app

## Consequences

- Two separate audit trails to query for full platform history
- `OpsEventLog` is ops-only and never surfaces in tenant-facing views
