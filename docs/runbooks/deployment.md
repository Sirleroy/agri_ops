# Runbook — Deployment

**Last Updated:** March 2026
**Applies to:** Phase 3 — Production on Render

---

## Architecture

| Layer | Service | URL |
|---|---|---|
| Web app | Render (free tier) | app.agriops.io |
| Database | Render PostgreSQL (free tier) | Internal only |
| DNS + CDN | Cloudflare | agriops.io |
| CI/CD | GitHub Actions | On push to main |
| Docs | GitHub Pages | docs.agriops.io |

---

## Deployment Flow

Every push to `main` branch triggers:

1. GitHub Actions runs `python manage.py check`
2. GitHub Actions runs all 12 tests against a fresh PostgreSQL container
3. If tests pass → Render deploy hook is called
4. Render pulls latest code, runs build command, restarts gunicorn

**Build command on Render:**
```
pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
```

**Start command on Render:**
```
gunicorn agri_ops_project.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

---

## Environment Variables on Render

| Variable | Purpose |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `SECRET_KEY` | Long random string |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `.onrender.com,.agriops.io` |
| `DATABASE_URL` | Injected automatically by Render PostgreSQL |
| `EMAIL_HOST` | `smtp.gmail.com` |
| `EMAIL_PORT` | `587` |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP password |
| `DEFAULT_FROM_EMAIL` | `AgriOps <noreply@agriops.io>` |

---

## DNS Configuration (Cloudflare)

| Record | Type | Target | Proxy |
|---|---|---|---|
| `app` | CNAME | `agriops.onrender.com` | DNS only |
| `api` | CNAME | `agriops.onrender.com` | DNS only |
| `docs` | CNAME | `sirleroy.github.io` | DNS only |
| `www` | CNAME | `www.app.agriops.io` | Proxied |

Page Rules:
- `agriops.io/*` → 301 redirect to `https://app.agriops.io`
- `www.agriops.io/*` → 301 redirect to `https://app.agriops.io`

---

## Manual Deployment

To trigger a manual deploy without pushing code:

1. Go to Render dashboard → agriops service
2. Click **Manual Deploy** → **Deploy latest commit**

Or via the deploy hook:
```bash
curl -X POST "$RENDER_DEPLOY_HOOK"
```

---

## Monitoring

- Render dashboard → **Logs** tab — real-time application logs
- Render dashboard → **Metrics** tab — CPU, memory, response times
- GitHub Actions → **Actions** tab — CI run history
- `/admin/axes/` — brute force attempt log

---

## Rollback

To roll back to a previous deployment:

1. Go to Render dashboard → agriops → **Deployments**
2. Find the last known good deployment
3. Click **Redeploy**

Or via git:
```bash
git revert HEAD
git push origin main
```

---

## Common Issues

### App returns 500 after deploy
Check Render logs immediately. Most common causes:
- Missing environment variable
- Failed migration
- Import error in new code

### Migrations not running
The build command includes `python manage.py migrate`. Check build logs in Render for migration output.

### Static files not loading
WhiteNoise serves static files. Run `python manage.py collectstatic --noinput` locally to verify no errors, then redeploy.
