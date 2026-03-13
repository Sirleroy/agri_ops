# Runbook — Deployment

**Last Updated:** March 2026
**Status:** Placeholder — full content in Phase 3

---

## Overview

This runbook will document the full deployment process for AgriOps from Phase 3 onwards, when the application is deployed to a cloud hosting provider.

---

## Planned Deployment Stack (Phase 3)

| Component | Technology | Notes |
|---|---|---|
| Hosting | Railway or Render | Decision to be finalised in Phase 3 |
| Database | Managed PostgreSQL | Railway Postgres or Supabase |
| Static files | WhiteNoise | Served from application |
| SSL | Let's Encrypt | Auto-managed by hosting provider |
| CI/CD | GitHub Actions | Auto-deploy on merge to main |
| Containers | Docker | Dev/prod parity |

---

## Environment Separation

```
development  — local machine, DEBUG=True, local PostgreSQL
staging      — cloud instance, DEBUG=False, mirrors production config
production   — live environment, real customer data
```

Settings split into `config/settings/base.py`, `development.py`, `production.py` in Phase 2.

---

## Sections to be completed in Phase 3

- Docker build and run instructions
- Environment variable configuration for production
- Database migration procedure for production
- Static file collection and serving
- GitHub Actions CI/CD pipeline configuration
- Health check verification post-deployment
- Rollback procedure
- SSL certificate setup
- Monitoring and alerting setup (Sentry)

---

## Pre-deployment Checklist (Draft)

- [ ] All tests passing
- [ ] No pending migrations
- [ ] Environment variables set in hosting provider
- [ ] DEBUG=False confirmed
- [ ] ALLOWED_HOSTS configured
- [ ] Database backup taken
- [ ] Health check endpoint responding
- [ ] Sentry error tracking active

---

*This document will be fully populated during Phase 3.*
