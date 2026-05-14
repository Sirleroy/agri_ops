---
layout: default
title: "ADR 013 — Evidence-gated Compliance Readiness Sign-off"
---

# ADR 013 — Evidence-gated Compliance Readiness Sign-off

**Date:** May 2026
**Status:** Accepted — implemented
**Author:** Ezinna (Founder)

---

## Context

Until now, a farm's EUDR verification was a free checkbox. `Farm.is_eudr_verified`
was a boolean an operator ticked on the edit form, with `verified_by` / `verified_date` /
`verification_expiry` and `deforestation_risk_status` as adjacent free inputs. Nothing
required evidence behind the tick: a farm with no deforestation check, or a flagged one,
could still be marked verified — and that flowed straight through `compliance_status` to
a clean EUDR certificate PDF. The verification was an assertion, not a finding.

In parallel, the **deforestation engine** (`run_check` + `DeforestationCheck`) was built:
it intersects each farm polygon against satellite tree-cover-loss data and retains the
result as an auditable evidence record. With the engine producing real evidence, the
question became: *what should "verified" mean, now that the platform can independently
assess deforestation?*

Two broad options:

1. **Full automation.** The engine sets verification directly — a clear check makes the
   farm verified, no human in the loop.
2. **Evidence-gated human sign-off.** The engine produces the evidence; a manager signs
   off on it; the sign-off action is rejected unless the evidence is complete and current.

---

## Decision

**Adopt evidence-gated human sign-off.** Three sub-decisions:

1. **Verification is a manager-only, evidence-gated, audited action — not a field.**
   `is_eudr_verified` (and its metadata) is no longer on the edit form and is read-only
   over the API. It is set only by `ConfirmComplianceReadinessView` — manager-or-above,
   POST-only — which re-checks the evidence gate server-side, then records the sign-off
   and a 12-month expiry, audit-logged. `WithdrawComplianceReadinessView` reverses it.

2. **The user-facing concept is "Compliance Readiness"**, surfaced as a `readiness_state`
   lifecycle — `not_ready` → `awaiting_signoff` → `ready`, plus `disqualified` and
   `expired`. "EUDR Verified" was retired as user-facing wording: it overclaimed an
   authority AgriOps does not hold. `compliance_status` is now evidence-backed — a
   sign-off only counts as `compliant` when a clear, current, non-stale
   `DeforestationCheck` sits behind it.

3. **Disqualification is the engine's default with an audited manual override.** A
   flagged check disqualifies the farm; a manager may override via
   `land_cleared_after_cutoff` (e.g. a false positive, or clearing that predates the
   cut-off), which requires a documented reason and is audit-logged.

### Why human sign-off and not full automation

- **EUDR accountability is organisational.** A named person must own the compliance
  claim; "the algorithm decided" is not a posture auditors or regulators accept.
- **Field data quality varies**, and **satellite interpretation has edge cases** — false
  positives, coverage gaps, boundary mismatches. A human reviewing assembled evidence
  catches what the engine alone cannot.
- **Auditors trust reviewable workflows** over fully autonomous claims.
- AgriOps is **early in production exposure** — the conservative posture is the right
  one until the engine has a long track record.

The engine removes the *guesswork*; it does not remove the *accountability*.

---

## Consequences

- **Auto-invalidation.** A sign-off is withdrawn automatically when the polygon changes
  (`Farm.save()`) or a re-check is no longer clear (`run_check`), so `is_eudr_verified=True`
  always reflects current evidence. The automated withdrawal is audit-logged, matching
  the manual path.
- **Legacy data was reset.** Migration `0021` un-verified every farm whose sign-off had
  no clear, current check behind it. Remediation path: run `run_deforestation_checks`,
  then a manager re-signs off.
- **Consistency sweep required.** The stricter model had to be applied across every
  write path and outward display — the API serializer, buyer/public surfaces, and
  dashboard counts all initially still used the raw flag and were corrected.
- **Bulk sign-off is an open gap.** Per-farm sign-off does not scale to large imports
  (a 69-farm upload surfaced this). A *reviewed* bulk sign-off — evidence-gated per farm,
  one deliberate decision — is the planned answer; not yet built.

---

## Related Decisions

- [ADR 005 — EUDR Farm Model Separation](005-eudr-farm-model-separation.md) — the Farm
  model this sign-off operates on
- [ADR 011 — PostgreSQL Row-Level Security Deferral](011-postgres-row-level-security-deferral.md)
  — `compliance_status` / `readiness_state` are computed properties; count queries that
  need them iterate-with-prefetch today, and would benefit from RLS-era denormalisation
- `/docs/design/compliance-module.md` — the implementation detail
- `/docs/threat-model.md` §6 — "False verification" threat, now controlled by this gate
