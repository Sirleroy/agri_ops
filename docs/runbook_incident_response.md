# Incident Response Runbook

**Owner:** Ezinna Ohah — founder@agriops.io  
**Last reviewed:** 2026-05-04

---

## Scenario 1 — Tenant reports seeing another tenant's data

**Symptoms:** A user says they can see farms, orders, or farmer records that don't belong to their company.

### Immediate (within 1 hour)
1. **Suspend both companies** via Ops Dashboard → Companies → Suspend. Do not wait to investigate first — contain the exposure.
2. **Snapshot the database** immediately before any further writes (Render dashboard → your Postgres → create manual backup).
3. **Preserve the request** — ask the reporting user for the exact URL, the pk in the URL, and a screenshot if possible.

### Investigate
4. Pull `AuditLog` for the affected company around the reported time:
   ```
   python manage.py shell -c "
   from apps.audit.models import AuditLog
   from django.utils import timezone
   import datetime
   logs = AuditLog.objects.filter(
       timestamp__gte=timezone.now() - datetime.timedelta(hours=2)
   ).order_by('-timestamp')[:50]
   for l in logs: print(l)
   "
   ```
5. Identify which view served the cross-tenant object. Check if `CompanyOwnedMixin` is present on that view — a missing mixin is the most likely cause.
6. Check if the issue is reproducible: log in as a test user in the affected tenant and try to access the reported pk directly.

### Resolve
7. Fix the missing tenant guard in code, test, deploy.
8. Reactivate companies once the fix is confirmed.
9. Notify NDPC within **72 hours** if personal data (farmer NIN, names, GPS) was exposed. Email: info@ndpc.gov.ng. Include: what data, how many individuals, how long exposed, what was done.
10. Notify the affected tenant by email with a clear factual summary — no speculation, no minimising.

---

## Scenario 2 — Suspected credential compromise

**Symptoms:** Unknown login from unfamiliar IP, user reports they didn't perform an action shown in audit log, django-axes lockout email for a known user.

### Immediate (within 30 minutes)
1. **Force password reset** for the affected user via Django admin or:
   ```python
   from django.contrib.auth import get_user_model
   User = get_user_model()
   u = User.objects.get(email='user@example.com')
   u.set_unusable_password()
   u.save()
   ```
2. **Flush all sessions** for that user:
   ```python
   from django.contrib.sessions.models import Session
   # Sessions are not user-keyed by default — flush all active sessions
   Session.objects.all().delete()
   ```
   Warning: this logs out all users. Do it off-peak if possible.
3. **Check django-axes** for the IP that triggered the lockout and block it at Render / Cloudflare level if identifiable.

### Investigate
4. Review `AuditLog` for actions taken under that user account in the past 24 hours.
5. If a platform superuser (ops dashboard) account is suspected: invalidate the TOTP device via Django admin → django_otp → TOTP devices.
6. Review Sentry for any unusual error patterns tied to that `company_id` tag in the same window.

### Resolve
7. Send the user a secure password-reset link.
8. If ops dashboard credentials were compromised: rotate `SECRET_KEY` in Render env vars and redeploy (this invalidates all sessions and TOTP backup codes).
9. Document what was accessed and when in a private incident log.

---

## Scenario 3 — Data loss

**Symptoms:** Missing records, accidental bulk delete, failed migration on production, database corruption.

### Immediate
1. **Stop writes if possible** — put the app in maintenance mode (set `ALLOWED_HOSTS=[]` temporarily in Render env vars to return 400 on all requests).
2. **Do not run any further migrations or management commands** until the extent of the loss is known.

### Recover
3. Identify the last clean backup in Render → your Postgres → Backups.
4. Restore to a staging environment first — never restore directly to production without verifying the backup is clean.
5. Compare restored data to production to scope what was lost.
6. If partial recovery is possible (e.g. only one tenant's data is lost), restore that company's records selectively.

### Resolve
7. Re-enable the app once data integrity is confirmed.
8. If farmer personal data was permanently lost and unrecoverable: notify NDPC within 72 hours.
9. Run `python manage.py check_geometry_integrity` after any restore to verify GPS polygon hashes are intact.
10. Post-incident: document root cause and add a test or migration check to prevent recurrence.

---

## NDPA Breach Notification (applies to Scenarios 1 and 3)

Under the Nigeria Data Protection Act 2023, a personal data breach must be reported to NDPC within **72 hours** of becoming aware of it.

**Contact:** Nigeria Data Protection Commission — info@ndpc.gov.ng  
**Include in notification:**
- Nature of the breach (what happened)
- Categories and approximate number of individuals affected
- Categories of personal data involved (name, NIN, phone, GPS, etc.)
- Likely consequences of the breach
- Measures taken or proposed to address it

Keep a copy of the notification and any NDPC response on file.
