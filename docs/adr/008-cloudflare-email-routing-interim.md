---
layout: default
title: "ADR-008: Cloudflare Email Routing as Interim Founder Email"
---
# ADR-008: Cloudflare Email Routing as Interim Founder Email

**Date:** 2026-03-21
**Status:** Accepted (interim)

## Context

A `founder@agriops.io` address was needed to receive platform notifications (new tenant signups, security alerts). Google Workspace setup was blocked by a pre-existing domain association with a previous Google trial account.

## Decision

Use Cloudflare Email Routing to forward `founder@agriops.io` to `ohahezinna@gmail.com`. This is an interim solution.

## Rationale

- Free, configured in under 5 minutes
- No conflict with future Google Workspace setup — Cloudflare routing handles inbound only
- Allows `FOUNDER_EMAIL=founder@agriops.io` in production settings immediately
- Compatible with SendGrid outbound — separate concerns

## Migration Path

When Google Workspace domain conflict is resolved, disable the Cloudflare routing rule and Google Workspace takes over. No code changes required.

## Consequences

- Replies to `founder@agriops.io` notifications must be sent manually from Gmail
- Cannot send outbound email from `founder@agriops.io` until Google Workspace is resolved
