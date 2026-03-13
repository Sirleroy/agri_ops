# Runbook — Incident Response

**Last Updated:** March 2026
**Owner:** Ezinna (Founder)
**Applies to:** All phases

---

## Overview

This runbook defines the procedure for identifying, containing, investigating, and recovering from security incidents affecting the AgriOps platform. It covers credential compromise, data breaches, unauthorised access, and service disruption.

An incident is any event that has compromised or has the potential to compromise the confidentiality, integrity, or availability of AgriOps data or systems.

---

## Severity Classification

| Severity | Definition | Response Time |
|---|---|---|
| P1 — Critical | Active breach, data exfiltration confirmed or suspected, service down | Immediate — drop everything |
| P2 — High | Credential compromise, suspected cross-tenant access, auth system failure | Within 1 hour |
| P3 — Medium | Suspicious activity, failed attack attempts, non-critical service degradation | Within 4 hours |
| P4 — Low | Policy violation, minor configuration issue, vulnerability with no exploit | Within 24 hours |

---

## Phase 1 — Identify

### Signs of a potential incident

- Unexpected login from unknown IP or geography
- Multiple failed login attempts followed by success (credential stuffing)
- User reports they did not perform an action shown in audit log
- Unexpected data in another company's records
- Error monitoring (Sentry) showing unusual spike in 403/404 errors
- Database queries returning unexpected record counts
- Application behaving differently than expected without code changes

### First actions

1. **Do not panic. Do not delete anything.**
2. Note the exact time you became aware of the incident.
3. Screenshot or copy any error messages, log entries, or anomalous data you see.
4. Classify the severity using the table above.
5. Move to the appropriate containment procedure.

---

## Phase 2 — Contain

### P1 — Critical: Suspected active breach

```bash
# 1. Take the application offline immediately
# On Railway/Render: set service to maintenance mode via dashboard
# Locally: stop the server
pkill -f "manage.py runserver"

# 2. Revoke all active sessions
# In Django shell:
python manage.py shell
>>> from django.contrib.sessions.models import Session
>>> Session.objects.all().delete()
>>> print("All sessions cleared")

# 3. Rotate the SECRET_KEY immediately
# Generate new key:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# Update .env with new SECRET_KEY
# Restart application
```

### P2 — High: Credential compromise

```bash
# 1. Disable the compromised account immediately
python manage.py shell
>>> from apps.users.models import CustomUser
>>> user = CustomUser.objects.get(username='compromised_user')
>>> user.is_active = False
>>> user.save()
>>> print(f"Account {user.username} disabled")

# 2. Invalidate all sessions for that user
>>> from django.contrib.sessions.models import Session
>>> import json
>>> for session in Session.objects.all():
...     data = session.get_decoded()
...     if data.get('_auth_user_id') == str(user.id):
...         session.delete()

# 3. Review audit log for actions taken by compromised account
>>> from apps.audit.models import AuditLog
>>> logs = AuditLog.objects.filter(user=user).order_by('-timestamp')
>>> for log in logs[:50]:
...     print(f"{log.timestamp} | {log.action} | {log.model_name} | {log.object_id}")
```

### P3 — Medium: Suspicious activity

1. Review audit log for the relevant user and time period
2. Review access logs for the relevant IP address
3. Document findings before taking any action
4. Escalate to P2 if suspicious activity is confirmed as malicious

---

## Phase 3 — Investigate

### Audit log review

```bash
python manage.py shell

# All actions by a specific user in the last 24 hours
>>> from apps.audit.models import AuditLog
>>> from django.utils import timezone
>>> from datetime import timedelta
>>> logs = AuditLog.objects.filter(
...     user__username='username_here',
...     timestamp__gte=timezone.now() - timedelta(hours=24)
... ).order_by('timestamp')
>>> for log in logs:
...     print(f"{log.timestamp} | {log.action} | {log.model_name}:{log.object_id} | IP: {log.ip_address}")

# All actions from a specific IP address
>>> logs = AuditLog.objects.filter(
...     ip_address='x.x.x.x'
... ).order_by('timestamp')

# All delete actions across the platform in last 7 days
>>> logs = AuditLog.objects.filter(
...     action='delete',
...     timestamp__gte=timezone.now() - timedelta(days=7)
... ).order_by('-timestamp')
```

### Cross-tenant access investigation

```bash
# Check if any records were accessed across tenant boundaries
# This should be impossible by design — any occurrence is a critical finding

>>> from apps.audit.models import AuditLog
>>> # Look for audit log entries where user's company differs from record's company
>>> # (Requires joining audit log to user and the affected model — adapt per model)
```

### Questions to answer during investigation

1. What was the first sign of the incident and when did it occur?
2. Which accounts were involved?
3. Which IP addresses were involved?
4. What data was accessed, modified, or deleted?
5. Was any cross-tenant access achieved?
6. How long was the attacker active?
7. Was any data exfiltrated (copied out of the system)?
8. What was the attack vector — how did they get in?

---

## Phase 4 — Eradicate

1. Remove the attack vector that allowed the incident:
   - If credential compromise: force password reset for affected account, review for similar weak credentials
   - If application vulnerability: identify the vulnerable code, patch it, deploy the fix
   - If configuration issue: correct the configuration

2. Verify the fix:
   - Reproduce the attack vector in a test environment
   - Confirm the fix prevents reproduction

3. Scan for persistence:
   - Check for any accounts created during the incident period
   - Check for any configuration changes made during the incident period
   - Check for any unexpected files uploaded

---

## Phase 5 — Recover

1. Re-enable the application if it was taken offline
2. Re-enable affected user accounts if appropriate — after password reset
3. Notify affected users if their data was involved
4. Monitor closely for 48 hours post-recovery for signs of re-entry

---

## Phase 6 — Document and Learn

Every incident — regardless of severity — produces an incident report.

### Incident Report Template

```
AGRIOPS INCIDENT REPORT
═══════════════════════════════════════

Incident ID:        INC-YYYY-MM-DD-001
Date Detected:      
Date Resolved:      
Severity:           P1 / P2 / P3 / P4
Status:             Resolved / Ongoing

SUMMARY
-------
[2-3 sentence description of what happened]

TIMELINE
--------
[Time] — [Event]
[Time] — [Event]
[Time] — [Event]

AFFECTED ASSETS
---------------
[List affected systems, data, users]

ROOT CAUSE
----------
[What allowed this to happen]

IMPACT
------
[What data or systems were affected. Was any data exfiltrated?]

CONTAINMENT ACTIONS
-------------------
[What was done to stop the incident]

ERADICATION ACTIONS
-------------------
[What was done to remove the cause]

RECOVERY ACTIONS
----------------
[What was done to restore normal operation]

LESSONS LEARNED
---------------
[What can be improved to prevent recurrence]

FOLLOW-UP ACTIONS
-----------------
[ ] Action item — Owner — Due date
[ ] Action item — Owner — Due date
```

---

## Notification Obligations

### NDPR (Nigeria Data Protection Regulation)
If personal data of Nigerian users is involved in a breach:
- Notify the Nigeria Data Protection Commission (NDPC) within **72 hours** of becoming aware
- Notify affected users without undue delay

### GDPR (if EU users are affected)
- Notify the relevant supervisory authority within **72 hours**
- Notify affected data subjects if high risk to their rights and freedoms

### Contractual obligations
- Review any customer contracts for breach notification clauses
- EUDR compliance data breach may have specific notification requirements to EU buyers

---

## Contact Reference

| Role | Contact | When to Contact |
|---|---|---|
| Founder / Incident Lead | Ezinna | All incidents |
| Hosting Provider Support | Railway/Render support portal | P1 — infrastructure involved |
| Legal Counsel | TBD — Phase 3 | P1/P2 — data breach confirmed |

---

## Related Documents

- `/docs/threat-model.md` — full threat landscape
- `/docs/runbooks/backup-restore.md` — if data recovery is needed
- `/docs/design/tenant-model.md` — tenant isolation architecture
