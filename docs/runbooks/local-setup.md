# Runbook — Local Development Setup

**Last Updated:** March 2026
**Applies to:** Phase 1 and Phase 2 codebase

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | Use pyenv for version management |
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
SECRET_KEY=your-local-secret-key-here
DEBUG=True
DB_NAME=agri_ops_db
DB_USER=postgres
DB_PASSWORD=your-postgres-password
DB_HOST=localhost
DB_PORT=5432
```

**Never commit `.env` to git.** It is in `.gitignore`.

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

## 8. Load Seed Data (Optional)

```bash
python manage.py seed_data
```

This creates two sample companies with suppliers, products, inventory, and orders for testing. Safe to run multiple times (idempotent).

---

## 9. Start the Development Server

```bash
python manage.py runserver 8001
```

**Note:** Port 8001 is used because Splunk occupies port 8000 on the development machine. See ADR 001.

---

## 10. Verify Setup

Open your browser and check:

| URL | Expected |
|---|---|
| http://localhost:8001/ | Dashboard (redirects to login if not authenticated) |
| http://localhost:8001/admin/ | Django admin panel |
| http://localhost:8001/suppliers/ | Suppliers list |
| http://localhost:8001/products/ | Products list |
| http://localhost:8001/inventory/ | Inventory list |
| http://localhost:8001/purchase-orders/ | Purchase orders |
| http://localhost:8001/sales-orders/ | Sales orders |
| http://localhost:8001/companies/ | Companies |
| http://localhost:8001/users/ | Users |

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

### Static files not loading
Run:
```bash
python manage.py collectstatic
```

---

## Development Notes

- `settings.py` is excluded from git (contains local DB password). Use `.env.example` as reference.
- The `venv/` directory is excluded from git.
- All migrations are tracked in version control and should be committed when models change.
- Run `python manage.py showmigrations` to verify migration state.
