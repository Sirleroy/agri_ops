#!/usr/bin/env bash
set -euo pipefail

# ── AgriOps Security & Integrity Verification ────────────────────────────────
# Runs the regression test suite covering the four highest-risk areas:
#   1. Tenant isolation        — no data leakage between companies
#   2. Suspended company       — blocked at web, dashboard, admin panel, and API
#   3. Audit integrity         — correct logging, company scoping, no cross-tenant leakage
#   4. Certificate blocking    — expired/non-compliant evidence cannot produce a certificate
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

if echo "yes" | python manage.py test \
  apps.companies.tests \
  apps.audit.tests \
  apps.suppliers.tests \
  apps.sales_orders.tests \
  --verbosity=2; then

  echo ""
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}  All checks passed. Safe to deploy.${NC}"
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  exit 0

else
  echo ""
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${RED}  Verification failed. Do not deploy.${NC}"
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  exit 1

fi
