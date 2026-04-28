#!/usr/bin/env bash
set -euo pipefail

# ── AgriOps Local Development Setup ──────────────────────────────────────────
# Idempotent — safe to run more than once.
# Usage: bash setup.sh [--seed]
#   --seed    Load demo data after migrations (optional)

SEED=false
for arg in "$@"; do
  [[ "$arg" == "--seed" ]] && SEED=true
done

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC}  $1"; }
warn() { echo -e "${YELLOW}!${NC}  $1"; }
fail() { echo -e "${RED}✗${NC}  $1"; exit 1; }
step() { echo -e "\n${GREEN}▶${NC}  $1"; }

# ── 1. Python version ─────────────────────────────────────────────────────────
step "Checking Python version"
PYTHON=$(command -v python3 || command -v python || fail "Python not found — install Python 3.12+")
VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
MAJOR=$(echo "$VERSION" | cut -d. -f1)
MINOR=$(echo "$VERSION" | cut -d. -f2)

if [[ "$MAJOR" -lt 3 || ( "$MAJOR" -eq 3 && "$MINOR" -lt 12 ) ]]; then
  fail "Python 3.12+ required — found $VERSION"
fi
ok "Python $VERSION"

# ── 2. Virtual environment ────────────────────────────────────────────────────
step "Setting up virtual environment"
if [[ ! -d "venv" ]]; then
  "$PYTHON" -m venv venv
  ok "Created venv/"
else
  ok "venv/ already exists — skipping"
fi

source venv/bin/activate
ok "Activated venv"

# ── 3. Dependencies ───────────────────────────────────────────────────────────
step "Installing dependencies"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "Dependencies installed"

# ── 4. Environment file ───────────────────────────────────────────────────────
step "Configuring environment"
if [[ ! -f ".env" ]]; then
  cp .env.example .env
  ok "Created .env from .env.example"

  # Generate a real SECRET_KEY
  SECRET=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
  # Cross-platform sed (macOS needs '' after -i, Linux does not)
  if sed --version 2>&1 | grep -q GNU; then
    sed -i "s|SECRET_KEY=replace-with-generated-key|SECRET_KEY=$SECRET|" .env
  else
    sed -i '' "s|SECRET_KEY=replace-with-generated-key|SECRET_KEY=$SECRET|" .env
  fi
  ok "Generated SECRET_KEY"

  echo ""
  warn "Review .env and set DB_PASSWORD before continuing."
  warn "Press Enter when ready, or Ctrl+C to exit and edit first."
  read -r
else
  ok ".env already exists — skipping"
fi

# ── 5. Database connection check ──────────────────────────────────────────────
step "Checking database connection"
export DJANGO_SETTINGS_MODULE=config.settings.development

if python manage.py inspectdb > /dev/null 2>&1; then
  ok "Database connection successful"
else
  fail "Cannot connect to database — check DB_NAME, DB_USER, DB_PASSWORD, DB_HOST in .env"
fi

# ── 6. Migrations ─────────────────────────────────────────────────────────────
step "Running migrations"
python manage.py migrate --no-input
ok "Migrations applied"

# ── 7. Static files ───────────────────────────────────────────────────────────
step "Collecting static files"
python manage.py collectstatic --no-input --quiet
ok "Static files collected"

# ── 8. Seed data (optional) ───────────────────────────────────────────────────
if [[ "$SEED" == true ]]; then
  step "Loading demo data"
  python manage.py seed_demo
  ok "Demo data loaded"
fi

# ── 9. Superuser prompt ───────────────────────────────────────────────────────
step "Superuser"
echo ""
warn "Do you want to create a superuser now? (y/N)"
read -r CREATE_SUPER
if [[ "$CREATE_SUPER" =~ ^[Yy]$ ]]; then
  python manage.py createsuperuser
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  AgriOps is ready.${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Start the server:   python manage.py runserver 8001"
echo "  Run tests:          pytest"
echo "  Ops dashboard:      http://localhost:8001/ops-access/9f3k/"
echo ""
