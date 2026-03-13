# Runbook — Backup and Restore

**Last Updated:** March 2026
**Owner:** Ezinna (Founder)
**Applies to:** Phase 2 onwards (local) — Phase 3 (cloud)

---

## Overview

AgriOps stores commercially sensitive supply chain data and EUDR compliance records. Data loss is not recoverable from the application — it must be prevented through regular, verified backups. This runbook documents the backup strategy, backup procedures, restore procedures, and backup verification process.

**Backup philosophy:** A backup that has not been tested is not a backup. Every backup procedure includes a verification step.

---

## What Must Be Backed Up

| Data | Location | Criticality | Notes |
|---|---|---|---|
| PostgreSQL database | DB server | Critical | All application data |
| Compliance documents | `media/compliance_docs/` | Critical | Uploaded files — farm maps, certifications |
| Environment configuration | `.env` | Critical | Never commit to git — back up securely |
| Application code | GitHub | High | Already version controlled |

---

## Backup Strategy

### Phase 2 — Local Development

**Database:** Manual backup before any significant migration or data change.

**Frequency:** Before every Phase 2 build session and before any migration.

**Retention:** Keep last 5 backups locally.

---

## Local Backup Procedures

### PostgreSQL Database Backup

```bash
# Create backup directory if it doesn't exist
mkdir -p ~/agri_ops_backups

# Create a timestamped backup
pg_dump -U postgres -d agri_ops_db -F c -f ~/agri_ops_backups/agriops_$(date +%Y%m%d_%H%M%S).dump

# Verify the backup was created and has a reasonable size
ls -lh ~/agri_ops_backups/
```

Expected output: a `.dump` file with non-zero size. A zero-byte file means the backup failed.

### Verify the backup is readable

```bash
# List the contents of the backup without restoring it
pg_restore --list ~/agri_ops_backups/agriops_YYYYMMDD_HHMMSS.dump | head -30
```

If this command produces output, the backup file is valid. If it errors, the backup is corrupt — take another one.

### Media files backup (compliance documents)

```bash
# Backup the media directory
tar -czf ~/agri_ops_backups/agriops_media_$(date +%Y%m%d_%H%M%S).tar.gz ~/agri_ops/media/

# Verify
tar -tzf ~/agri_ops_backups/agriops_media_YYYYMMDD_HHMMSS.tar.gz | head -20
```

---

## Restore Procedures

### Restore PostgreSQL Database from Backup

**Warning:** This will overwrite all data in the target database. Only proceed if you understand the consequences.

```bash
# Step 1 — Stop the application
pkill -f "manage.py runserver"

# Step 2 — Drop and recreate the database
psql -U postgres -c "DROP DATABASE agri_ops_db;"
psql -U postgres -c "CREATE DATABASE agri_ops_db;"

# Step 3 — Restore from backup
pg_restore -U postgres -d agri_ops_db ~/agri_ops_backups/agriops_YYYYMMDD_HHMMSS.dump

# Step 4 — Verify restoration
psql -U postgres -d agri_ops_db -c "SELECT COUNT(*) FROM companies_company;"
psql -U postgres -d agri_ops_db -c "SELECT COUNT(*) FROM suppliers_supplier;"
psql -U postgres -d agri_ops_db -c "SELECT COUNT(*) FROM users_customuser;"

# Step 5 — Run Django check
cd ~/agri_ops
source venv/bin/activate
python manage.py check

# Step 6 — Restart application
python manage.py runserver 8001
```

### Restore Media Files

```bash
# Restore compliance documents
cd ~/agri_ops
tar -xzf ~/agri_ops_backups/agriops_media_YYYYMMDD_HHMMSS.tar.gz

# Verify key directories exist
ls media/compliance_docs/
```

---

## Phase 3 — Cloud Backup Strategy

When deployed to Railway or Render, the following backup strategy applies:

### Automated Database Backups

**Provider-managed backups:**
- Railway Postgres: daily automated backups, 7-day retention (free tier)
- Supabase: daily automated backups, point-in-time recovery on paid plans

**Supplement with manual backups:**
```bash
# Connect to production database and dump remotely
pg_dump $DATABASE_URL -F c -f backups/agriops_prod_$(date +%Y%m%d).dump
```

### Media Files — Cloud Storage (Phase 3)

Compliance documents will be stored in cloud object storage (AWS S3 or equivalent) with:
- Versioning enabled — deleted files recoverable
- Cross-region replication — geographic redundancy
- Lifecycle policy — automatic transition to cheaper storage after 90 days

### Backup Schedule (Phase 3 Target)

| Backup Type | Frequency | Retention | Storage |
|---|---|---|---|
| Full database | Daily | 30 days | Provider + off-site |
| Media files | On upload (versioned) | Indefinite | S3 with versioning |
| Configuration | On change | Indefinite | Encrypted secure notes |

---

## Backup Verification Schedule

Backups are only useful if they can be restored. Test restores must be performed regularly.

| Test | Frequency | Procedure |
|---|---|---|
| Backup file integrity | Every backup | `pg_restore --list` on dump file |
| Full restore to test DB | Monthly | Restore to `agri_ops_db_test`, verify record counts |
| Media file restore | Monthly | Extract to temp directory, spot-check files |

### Monthly restore test procedure

```bash
# Create a test database
psql -U postgres -c "CREATE DATABASE agri_ops_db_restore_test;"

# Restore latest backup to test database
pg_restore -U postgres -d agri_ops_db_restore_test ~/agri_ops_backups/latest.dump

# Verify record counts match production
psql -U postgres -d agri_ops_db -c "SELECT COUNT(*) FROM suppliers_supplier;" 
psql -U postgres -d agri_ops_db_restore_test -c "SELECT COUNT(*) FROM suppliers_supplier;"
# Counts must match

# Clean up test database
psql -U postgres -c "DROP DATABASE agri_ops_db_restore_test;"
```

---

## Pre-Migration Backup Checklist

Before running any Django migration that modifies existing tables:

```bash
# 1. Take a database backup
pg_dump -U postgres -d agri_ops_db -F c -f ~/agri_ops_backups/pre_migration_$(date +%Y%m%d_%H%M%S).dump

# 2. Verify the backup
pg_restore --list ~/agri_ops_backups/pre_migration_*.dump | wc -l
# Should return a non-zero number

# 3. Note the current record counts
psql -U postgres -d agri_ops_db -c "
SELECT
  'companies' as table, COUNT(*) FROM companies_company
UNION ALL SELECT 'users', COUNT(*) FROM users_customuser
UNION ALL SELECT 'suppliers', COUNT(*) FROM suppliers_supplier
UNION ALL SELECT 'products', COUNT(*) FROM products_product;
"

# 4. Only then run the migration
python manage.py migrate

# 5. Verify record counts are unchanged
# Re-run the query above and confirm counts match
```

---

## Disaster Recovery Targets (Phase 3+)

| Metric | Target | Notes |
|---|---|---|
| RPO (Recovery Point Objective) | 24 hours | Maximum data loss acceptable |
| RTO (Recovery Time Objective) | 4 hours | Maximum time to restore service |

These targets will be validated through quarterly disaster recovery drills from Phase 3 onwards.

---

## Related Documents

- `/docs/runbooks/incident-response.md` — if backup is needed due to an incident
- `/docs/runbooks/deployment.md` — deployment configuration including backup tooling
- `/docs/threat-model.md` — data loss listed as a risk
