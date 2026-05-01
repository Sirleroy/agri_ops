# Geometry Drift Detection — Test Runbook

## Test Objective

Verify that `check_geometry_integrity` catches geometry mutations made outside of
the normal `save()` path — simulating tampering via direct DB write, bulk `update()`,
or admin bypass. This is the primary detection mechanism for Layer 2 of the geometry
integrity controls.

---

## Why This Test Matters

`Farm.save()` recomputes `geometry_hash` automatically whenever `geolocation` changes.
The threat model is not a UI edit — the audit log catches those. The threat is a
back-channel write that bypasses `save()`: a direct DB UPDATE, a Django admin bulk
action, an ORM `update()` call, or a compromised import pipeline. This test
simulates exactly that scenario.

---

## Prerequisites

- Local dev environment with venv activated, OR access to the Render shell
- At least one Farm record with a stored `geolocation` polygon (not null)
- `check_geometry_integrity` management command present (committed 2026-04-30)

---

## Procedure

**Step 1 — Open the Django shell**

```bash
python manage.py shell
```

**Step 2 — Select a mapped farm**

```python
from apps.suppliers.models import Farm
f = Farm.objects.exclude(geolocation=None).first()
print(f.pk, f.name, f.geometry_hash[:16])
```

Note the farm pk and the first 16 characters of the stored hash. You will verify
these appear correctly in the drift report.

**Step 3 — Inject drift via QuerySet.update()**

```python
import copy
new_geo = copy.deepcopy(f.geolocation)
new_geo['coordinates'][0][0][0] += 0.000001   # shift first longitude point by ~0.1m
Farm.objects.filter(pk=f.pk).update(geolocation=new_geo)
print('Drift injected on Farm', f.pk, f.name)
```

`update()` writes directly to the DB, bypassing `save()` and leaving `geometry_hash`
pointing at the old polygon. This is the mutation the check is designed to catch.

**Step 4 — Exit the shell and run the check**

```bash
python manage.py check_geometry_integrity
```

**Step 5 — Verify expected output**

```
Checking N farm(s)…

  ✓ Clean:   N-1
  ⚠ Missing: 0
  ✕ Drifted: 1

Farms with DRIFTED hash (geometry may have changed):
  Farm <pk> [<Company>] <Farm Name>
    stored:   <first 32 chars of original hash>…
    computed: <first 32 chars of recomputed hash>…

1 drifted hash(es) detected. Investigate before using --fix.
```

Confirm:
- Drift count is exactly 1
- The correct farm (by pk and name) is identified
- The stored and computed hashes differ and are both shown

**Step 6 — Check /ops/geometry/ (production only)**

If running against the production DB, load `/ops/geometry/` in the ops dashboard.
The drifted farm should appear in the red table with stored vs computed hash columns
and a link to the audit log. Note: this step only applies if the test was run against
production — the ops dashboard reads the production DB, not local dev.

**Step 7 — Restore clean state**

```bash
python manage.py check_geometry_integrity --fix
```

Output should confirm the hash was rewritten:
```
    → hash updated
```

Run the check one more time to confirm clean state:

```bash
python manage.py check_geometry_integrity
# Expected: All geometry hashes are clean.
```

---

## Expected Results Summary

| Check | Expected |
|---|---|
| Drift count | Increments by 1 |
| Farm identified | Correct pk and name |
| Hash mismatch shown | stored ≠ computed, both printed |
| `--fix` restores clean | Second run shows 0 drifted |
| Ops dashboard (prod) | Farm appears in red table with audit log link |

---

## When to Run This Test

- After any change to `Farm.save()` or the geometry hash logic
- After any bulk import or migration that touches `geolocation`
- As part of a security review before handing credentials to a new team member
- Before a compliance audit if there is any question about data integrity

---

## Notes

- The `0.000001` longitude shift is approximately 0.1 metres at the equator — enough
  to produce a different hash but invisible on a map. This is intentional: the test
  mimics a subtle tamper, not an obvious one.
- `--fix` should never be run without first reviewing the audit log for the drifted
  farm. The command surfaces drift; the audit log tells you whether it was a legitimate
  edit or a back-channel write.
- `--company-id <id>` scopes the check to a single tenant if needed.
