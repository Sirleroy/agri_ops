# Runbook — Local Development Setup

**Last Updated:** March 2026
**Applies to:** Phase 2 codebase

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ | Use pyenv for version management |
| PostgreSQL | 15+ | Local installation required |
| Git | Any recent | |
| WSL2 | Ubuntu 22.04+ | Windows users only |

---

## 1. Clone the Repository
```bash
git clone https://github.com/Sirleroy/agri_ops.git
cd agri_ops
```

---

## 2. Create and Activate Virtual Environment
```bash
python -m venv venv

# Linux / WSL / macOS
source venv/bin/activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

You should see `(venv)` in your terminal prompt.

---

## 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables
```bash
cp .env.example .env
```

Edit `.env` with your local values:
```env
SECRET_KEY=your-long-random-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=agri_ops_db
DB_USER=postgres
DB_PASSWORD=your-postgres-password
DB_HOST=localhost
DB_PORT=5432
```

**Never commit `.env` to git.** It is in `.gitignore`.

To generate a secure `SECRET_KEY`:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 5. Create PostgreSQL Database
```bash
psql -U postgres
```
```sql
CREATE DATABASE agri_ops_db;
\q
```

---

## 6. Run Migrations
```bash
python manage.py migrate
```

Expected output: all migrations applied, no errors.

---

## 7. Create Superuser
```bash
python manage.py createsuperuser
```

Use any username and password. Email is optional locally.

---

## 8. Load Seed Data
```bash
python manage.py seed_data
```

Creates two demo tenants with realistic Nigerian agri-SME data. Safe to run multiple times — idempotent. Use `--flush` to wipe and rebuild.

---

## 9. Start the Development Server
```bash
python manage.py runserver 8001
```

**Note:** Port 8001 is used because Splunk occupies port 8000 on the development machine.

---

## 10. Verify Setup

| URL | Expected |
|---|---|
| http://localhost:8001/login/ | Login page |
| http://localhost:8001/ | Dashboard (redirects to login if not authenticated) |
| http://localhost:8001/admin/ | Django admin panel |
| http://localhost:8001/suppliers/ | Suppliers list |
| http://localhost:8001/suppliers/farms/ | Farms list |
| http://localhost:8001/products/ | Products list |
| http://localhost:8001/inventory/ | Inventory list |
| http://localhost:8001/purchase-orders/ | Purchase orders |
| http://localhost:8001/sales-orders/ | Sales orders |
| http://localhost:8001/companies/ | Companies |
| http://localhost:8001/users/ | Users |
| http://localhost:8001/api/v1/ | DRF API root (requires JWT) |

---

## 11. Test the API

Obtain a JWT token:
```bash
curl -s -X POST http://localhost:8001/api/v1/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "ake_admin", "password": "agriops2026!"}' \
  | python3 -m json.tool
```

Use the access token:
```bash
curl -s http://localhost:8001/api/v1/suppliers/ \
  -H "Authorization: Bearer <access_token>" \
  | python3 -m json.tool
```

---

## Settings Structure

Settings are split into three files under `config/settings/`:

| File | Purpose |
|---|---|
| `base.py` | All shared settings — imports secrets via python-decouple |
| `development.py` | DEBUG=True, local overrides |
| `production.py` | HTTPS, HSTS, secure cookies, file logging |

`agri_ops_project/settings.py` simply imports from `config.settings.development`.

---

## Common Issues

### "django.db.utils.OperationalError: could not connect to server"
PostgreSQL is not running. Start it:
```bash
sudo service postgresql start   # Linux / WSL
brew services start postgresql  # macOS
```

### "relation does not exist"
Migrations have not been run. Run:
```bash
python manage.py migrate
```

### "No module named X"
Virtual environment is not activated or dependencies not installed. Run:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 403 Forbidden on a page
Your user's `system_role` does not have permission for that action. Check the RBAC matrix in `/docs/design/system-overview.md`.

### API returns 401 Unauthorized
JWT token is missing, expired, or malformed. Obtain a fresh token via `/api/v1/token/`.
