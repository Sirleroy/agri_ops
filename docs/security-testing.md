---
layout: default
title: Security Testing Log
---
# AgriOps — Security Testing Log

A running record of red team exercises, penetration findings, and resolutions.
Updated as new tests are run. All findings reference the validator or view under test and the actual codebase behaviour.

---

## RT-001 — GeoJSON Validator Red Team
**Date:** 6 April 2026
**Method:** Static analysis — five malicious payloads passed through a replica of `_validate_geojson_polygon`
**Target:** `apps/suppliers/forms.py` — `_validate_geojson_polygon`
**Tester:** External (AI-assisted simulation)

---

### Findings

| Payload | Attack Type | Claimed Result | Actual Result | Notes |
|---|---|---|---|---|
| 01 | Self-intersecting polygon (bow-tie) | REJECTED ✅ | REJECTED ✅ | Confirmed — Shapely `is_valid` check catches crossed boundary |
| 02 | Coordinate bomb (large integers / excess decimal places) | REJECTED ✅ | REJECTED ✅ | Confirmed — out-of-range lon/lat check fires before geometry processing |
| 03 | Zero-area sliver (3 collinear points) | REJECTED ✅ | REJECTED ✅ | Confirmed — Shapely flags collinear ring as invalid geometry |
| 04 | Boundary breach (valid polygon outside Nigeria) | **BYPASSED ⚠️** | **REJECTED ✅** | **False positive** — Nigeria bounding box check already present (lines 197–209). Replica used was missing this logic. |
| 05 | Null geometry (Feature with `geometry: null`) | REJECTED ✅ | REJECTED ✅ | Confirmed — Feature unwrap guard raises ValidationError on null geometry |

---

### False Positive — Payload 04

**Claimed:** Validator lacks a spatial fence. A polygon in the Atlantic Ocean or at `(0,0)` would bypass validation.

**Reality:** The Nigeria bounding box check has been live since Phase 4.7:

```python
_NGA_LON_MIN, _NGA_LON_MAX = 2.5, 15.0
_NGA_LAT_MIN, _NGA_LAT_MAX = 4.0, 14.2

avg_lon = sum(float(c[0]) for c in outer) / len(outer)
avg_lat = sum(float(c[1]) for c in outer) / len(outer)
if not (_NGA_LON_MIN <= avg_lon <= _NGA_LON_MAX and _NGA_LAT_MIN <= avg_lat <= _NGA_LAT_MAX):
    raise forms.ValidationError(...)
```

The centroid of the outer ring is checked against Nigerian bounds. A polygon centred in the Atlantic, Brazil, or at `(0,0)` is rejected with a clear error message referencing coordinate order and CRS.

**Root cause of false positive:** The replica function used for testing was not a faithful copy of the production validator — it was missing the bounding box logic added in Phase 4.7.

**Resolution:** No code change required. Test suite already covers this case via `test_swapped_lat_lon_raises`.

---

### Zero-Area Sliver — Verification

Payload 03 was marked REJECTED by the simulation. Verified against the live validator:

```
Input: POLYGON((7.0 9.0, 7.5 9.0, 8.0 9.0, 7.0 9.0))  # 3 collinear points, closed
Result: ValidationError — "This polygon's boundary crosses itself (self-intersecting geometry)."
```

Shapely correctly identifies a zero-area collinear ring as invalid geometry. Caught by the self-intersection check.

---

### Summary

All 5 payloads are rejected by the production validator. The red team exercise confirmed the validator's coverage but was run against an incomplete replica — the bounding box (Payload 04) and sliver (Payload 03) findings were pre-solved. No remediation required.

**CI coverage:** All scenarios are represented in `apps/suppliers/tests/test_geojson_validation.py` and run on every deployment via GitHub Actions.

---

*Next scheduled review: before Phase 5 (Buyer Portal) — new attack surface introduced by public-facing batch traceability endpoints.*

---

## RT-003 — OWASP ZAP Baseline Scan (Phase 4 Pre-Tenant)
**Date:** 5 May 2026
**Method:** Active + passive scan. OWASP ZAP 2.16 headless daemon on WSL2. Authenticated session cookie injected. Full spider + active scan against `http://localhost:8001`. Scan duration ~45 minutes.
**Target:** Full application — all authenticated views, login endpoint, API, static file serving
**Tester:** Founder (Ezinna Ohah) — ZAP automated, manual triage post-scan

---

### Findings

| ID | Severity | Location | Finding | Verdict | Status |
|---|---|---|---|---|---|
| ZAP-01 | High | `/login/` POST — `next` param | SQL Injection (SQLite) — time-based, `randomblob()` payload | False positive — app uses PostgreSQL; SQLite-specific function; 136ms timing delta is noise; `next` never enters SQL | Closed — false positive |
| ZAP-02 | Medium | All authenticated pages (44×) | CSP: `unsafe-eval` present | Structural constraint — required by Alpine.js CDN | Accepted — documented |
| ZAP-03 | Medium | All authenticated pages (44×) | CSP: `unsafe-inline` present | Structural constraint — required by Tailwind CDN | Accepted — documented |
| ZAP-04 | Medium | `/login/` POST (1×) | CSP header not set | ZAP inspecting 302 redirect body — CSP is present on all 200 responses | Closed — false positive |
| ZAP-05 | Medium | Static favicon PNGs (2×) | CORS `Access-Control-Allow-Origin: *` | Intentional — WhiteNoise default for public static assets | Accepted — intentional |
| ZAP-06 | Low | CDN script includes (29×) | Cross-domain JS source inclusion | Known CDN dependencies (Tailwind, Alpine.js, Leaflet, Flatpickr, Google Fonts) — all in CSP allowlist | Accepted — intentional |
| ZAP-07 | Info | `/login/` — `next` param reflection | Potential XSS via reflected parameter | Django auto-escapes all template values — no XSS vector | Closed — false positive |
| ZAP-08 | Info | Alpine.js / Leaflet source (multiple) | Suspicious JS comments containing SQL keywords | Library source code comments — not dynamic SQL | Closed — false positive |
| ZAP-09 | Info | `/login/` user agent fuzzer (576×) | Long username causes server crash | **Real finding** — ZAP-sent 255+ char username overflowed `AccessAttempt.username varchar(255)` in django-axes. Sentry captured live `DataError`. | **Fixed** — see ZAP-09 detail below |

---

### ZAP-09 — django-axes Username Overflow (Real Finding, Fixed)

**Finding:** During ZAP's automated user agent fuzzing pass, a username exceeding 255 characters was submitted to `/login/`. This caused a live server crash captured in Sentry:

```
DataError at /login/
value too long for type character varying(255)
  File "axes/models.py" — AccessAttempt save
```

**Root cause:** django-axes intercepts the login request before Django's own form validation runs. It writes the submitted username directly to `AccessAttempt.username` (varchar(255)). There is no truncation in axes itself before the database write.

**Fix applied in `config/settings/base.py`:**
```python
AXES_USERNAME_CALLABLE = lambda request, credentials: (credentials.get('username') or '')[:150]
```

This callable runs before axes stores the attempt. Usernames are now truncated to 150 characters (Django's own username field max length) before reaching the database. Axes runs this callable on every failed login attempt.

**Why 150?** Django's `AbstractUser.username` field is `max_length=150`. Truncating to the same length means any stored value could correspond to a valid Django username — consistent semantics, not an arbitrary limit.

**Verification:** Sentry error class confirmed gone after deployment. ZAP fuzzer re-run produced HTTP 429 (rate-limited) instead of 500.

---

### ZAP-01 — SQL Injection (SQLite) False Positive — Detail

**Payload used by ZAP:**
```
next=1%20AND%201%3D1%20UNION%20SELECT%20CASE%20WHEN%20%281%3D1%29%20THEN%20randomblob%2899999999%29%20ELSE%201%20END--
```

Decoded: `next=1 AND 1=1 UNION SELECT CASE WHEN (1=1) THEN randomblob(99999999) ELSE 1 END--`

**Why this is not exploitable on AgriOps:**

1. **Wrong database engine.** `randomblob(N)` is a SQLite built-in that generates N random bytes, causing intentional delay. PostgreSQL has no `randomblob` function — it would return an `undefined function` error, not delay.

2. **`next` is a redirect target, not a query parameter.** Django's `LoginView` passes `next` to `url_has_allowed_host_and_scheme()` for safety validation, then to `HttpResponseRedirect()`. It is never interpolated into a queryset, filter, or raw SQL call.

3. **Timing delta is within noise.** ZAP measured 907ms vs 771ms baseline (136ms). A real time-based blind SQLi payload on PostgreSQL would use `pg_sleep()` and produce a consistent 5–10 second delay. 136ms is indistinguishable from query-to-query latency variance.

4. **ORM prevents interpolation.** Even if `next` were used in a query (it isn't), Django's ORM parameterises all values — string interpolation into SQL is not possible through the ORM layer.

**Resolution:** False positive. No code change required. Documented here for audit trail.

---

### Summary

One real finding (ZAP-09 — axes overflow), found live during the scan, fixed and verified in the same session. Eight false positives — all attributable to: SQLite-specific payloads on a PostgreSQL app, ZAP inspecting redirect response bodies, CDN dependencies listed in the CSP allowlist, and Django's default auto-escaping.

**Net actionable findings: 1. Net open findings after fix: 0.**

**CI coverage:** No automated test needed for the axes truncation — it is a configuration-level fix enforced on every server startup. Manual verification: run `python manage.py check` and confirm settings load without error.

---

*Next scheduled review: before Phase 5 (Buyer Portal) — unauthenticated attack surface on public batch traceability endpoints requires a fresh ZAP scan profile with no session cookie.*

---

## RT-002 — Security Posture Audit (Phase 4.9)
**Date:** 8 April 2026
**Method:** Static analysis of full codebase — views, models, ops dashboard, API layer, settings
**Tester:** AI-assisted (Claude Code)

---

### Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| SA-01 | Medium | `apps/suppliers/views.py:114,573` | `session_key` read from GET param without validation — arbitrary session key enumeration possible | **Fixed** |
| SA-02 | Low | `ops_dashboard/views.py:72,111` | `/ops-access/9f3k/` path hardcoded in `@login_required` decorators — maintenance risk | **Fixed** |
| SA-03 | *(false positive)* | `.env` in git | Agent flagged `.env` in repository | False positive — `.env` is in `.gitignore`, never committed |
| SA-04 | *(false positive)* | `config/settings/development.py` | `DEBUG=True` reported as production risk | False positive — `production.py` explicitly sets `DEBUG=False`. Development-only setting. |
| SA-05 | *(false positive)* | `apps/reports/pdf.py` | N+1 query on `b.farms.all()` in PDF generator | False positive — PDF generator calls `prefetch_related('farms')` before the loop; `.all()` hits the prefetch cache. |

---

### SA-01 — Session Key Whitelist

**Finding:** Both import error download views (`FarmerImportErrorsView`, `FarmImportErrorsView`) accepted a `session_key` GET parameter and used it directly to read from `request.session`. An authenticated user could enumerate arbitrary session keys.

**Fix applied:**
```python
# Before
session_key = request.GET.get('session_key', 'farmer_import_errors')
error_rows = request.session.get(session_key, [])

# After
session_key = 'farmer_import_errors'
error_rows = request.session.get(session_key, [])
```

Both views now use hardcoded constants. Template links still include `?session_key=` (backward-compatible) but the parameter is ignored.

---

### SA-02 — Ops URL Constant

**Finding:** `@login_required(login_url='/ops-access/9f3k/')` appeared twice in `ops_dashboard/views.py`. The URL was already defined as `settings.OPS_LOGIN_URL` in `config/settings/base.py` but the decorators were not using it.

**Fix applied:** Both decorators now reference `settings.OPS_LOGIN_URL`. Single source of truth for the ops login path.

---

### Summary

Two genuine findings, both low-effort, both fixed in the same session. Three false positives driven by incomplete replicas or incorrect assumptions about configuration. No production risk outstanding from this audit.

**CI coverage:** Session key fix is tested by the existing import flow integration; ops URL change is a constant reference with no logic to test.

---

*Next scheduled review: before Phase 5 (Buyer Portal) — public-facing batch traceability endpoints introduce a new unauthenticated attack surface.*
