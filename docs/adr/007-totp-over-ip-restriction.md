---
layout: default
title: "ADR-007: TOTP Over IP Restriction for Ops Access"
---
# ADR-007: TOTP Over IP Restriction for Ops Access

**Date:** 2026-03-19
**Status:** Accepted

## Context

The ops dashboard at `/ops-access/9f3k/` requires a second authentication factor. The two primary options were IP allowlisting via Cloudflare WAF and TOTP (time-based one-time password).

## Decision

Use TOTP via `django-otp` with Google Authenticator. IP restriction deferred until a fixed office IP is available.

## Rationale

- Founder operates remotely with a dynamic IP — IP allowlisting would require constant updates
- TOTP provides strong second-factor security regardless of network location
- `django-otp` integrates cleanly with Django's authentication middleware
- Combined with a non-obvious login URL, 2-hour session timeout, and random username, TOTP provides adequate perimeter without a fixed IP

## Future

When a fixed office IP is available, add Cloudflare WAF rule on `ops.agriops.io` as an additional layer. TOTP remains even then.

## Consequences

- Founder must have authenticator app available to access ops dashboard
- Lost authenticator app requires manual device reset via Django shell
