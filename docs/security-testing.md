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
