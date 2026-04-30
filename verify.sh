#!/usr/bin/env bash
set -euo pipefail

# ── AgriOps Security & Integrity Verification ────────────────────────────────
# Runs the regression test suite and geometry integrity check covering:
#   1. Tenant isolation        — no data leakage between companies
#   2. Suspended company       — blocked at web, dashboard, admin panel, and API
#   3. Audit integrity         — correct logging, company scoping, no cross-tenant leakage
#   4. Certificate blocking    — expired/non-compliant evidence cannot produce a certificate
#   5. Geometry integrity      — all farm GPS hashes match stored polygons (no drift)
#
# Run this:
#   - After setup.sh, to confirm the environment is healthy
#   - Before every deploy
#   - After any change touching auth, views, API, or tenant logic

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC}  $1"; }
fail() { echo -e "${RED}✗${NC}  $1"; }
step() { echo -e "\n${GREEN}▶${NC}  $1"; }

# ── Activate venv if not already active ──────────────────────────────────────
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ -f "venv/bin/activate" ]]; then
    source venv/bin/activate
    ok "Activated venv"
  else
    echo -e "${YELLOW}!${NC}  No venv found — run setup.sh first or activate your environment manually."
    exit 1
  fi
fi

export DJANGO_SETTINGS_MODULE=config.settings.development

# ── Run the suite ─────────────────────────────────────────────────────────────
step "Running AgriOps security regression suite (34 tests)"
echo ""

if ! echo "yes" | python manage.py test \
  apps.companies.tests \
  apps.audit.tests \
  apps.suppliers.tests \
  apps.sales_orders.tests \
  --verbosity=2; then

  echo ""
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${RED}  Regression tests failed. Do not deploy.${NC}"
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  exit 1

fi

# ── Geometry integrity check ──────────────────────────────────────────────────
step "Checking geometry hash integrity (production DB)"
echo ""

GEO_OUTPUT=$(python manage.py check_geometry_integrity 2>&1)
echo "$GEO_OUTPUT"

if echo "$GEO_OUTPUT" | grep -q "Drifted:.*[^0]$\|drifted hash"; then
  echo ""
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${RED}  Geometry drift detected. Investigate before deploying.${NC}"
  echo -e "${RED}  Review audit log per farm, then: python manage.py check_geometry_integrity --fix${NC}"
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  exit 1
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  All checks passed. Safe to deploy.${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
