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
