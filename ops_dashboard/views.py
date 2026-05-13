import hashlib
import json
import threading
import qrcode
import qrcode.image.svg
import io
from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate

from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp import devices_for_user

from django.conf import settings

from apps.audit.models import AuditLog
from apps.companies.models import Company
from apps.dashboard.models import AccessRequest
from apps.inventory.models import Inventory
from apps.sales_orders.models import SalesOrder
from apps.purchase_orders.models import PurchaseOrder
from apps.suppliers.models import Supplier, Farm, Farmer, FarmImportLog
from apps.users.models import CustomUser
from .models import OpsEventLog


# --- Helpers ---

def _log_event(request, event, user=None, detail=''):
    OpsEventLog.objects.create(
        user=user,
        event=event,
        detail=detail,
        ip_address=request.META.get('REMOTE_ADDR'),
    )


def _mark_ops_otp_verified(request):
    request.session['otp_verified'] = True
    request.session.set_expiry(getattr(settings, 'OPS_SESSION_COOKIE_AGE', 7200))


# --- Decorators ---

def ops_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('ops_login')
        if not request.user.is_staff:
            return redirect('ops_login')
        if not request.session.get('otp_verified'):
            return redirect('ops_otp_verify')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# --- Auth views ---

def ops_login(request):
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user and user.is_staff:
            login(request, user)
            _log_event(request, 'ops_login', user=user)
            devices = list(devices_for_user(user, confirmed=True))
            if not devices:
                return redirect('ops_otp_setup')
            return redirect('ops_otp_verify')
        else:
            _log_event(request, 'ops_login_failed')
            error = 'Invalid credentials.'
    return render(request, 'ops_dashboard/login.html', {'error': error})


@login_required(login_url=settings.OPS_LOGIN_URL)
def ops_otp_setup(request):
    if not request.user.is_staff:
        return redirect('ops_login')

    user = request.user

    # Get existing unconfirmed device or create one — never delete on GET
    device, created = TOTPDevice.objects.get_or_create(
        user=user,
        name='AgriOps Ops Dashboard',
        defaults={'confirmed': False}
    )

    # Generate QR from stable device secret
    otp_url = device.config_url
    img = qrcode.make(otp_url, image_factory=qrcode.image.svg.SvgPathImage)
    buffer = io.BytesIO()
    img.save(buffer)
    svg_content = buffer.getvalue().decode('utf-8')
    if '<?xml' in svg_content:
        svg_content = svg_content[svg_content.index('<svg'):]
    qr_svg = svg_content

    if request.method == 'POST':
        token = request.POST.get('token', '').replace(' ', '')
        if device.verify_token(token):
            device.confirmed = True
            device.save()
            _mark_ops_otp_verified(request)
            _log_event(request, 'otp_setup', user=user)
            return redirect('ops_dashboard')
        return render(request, 'ops_dashboard/otp_setup.html', {
            'qr_svg': qr_svg,
            'error': 'Invalid code. Try again.'
        })

    return render(request, 'ops_dashboard/otp_setup.html', {'qr_svg': qr_svg})


@login_required(login_url=settings.OPS_LOGIN_URL)
def ops_otp_verify(request):
    if not request.user.is_staff:
        return redirect('ops_login')

    error = None
    if request.method == 'POST':
        token = request.POST.get('token', '').replace(' ', '')
        devices = list(devices_for_user(request.user, confirmed=True))
        for device in devices:
            if device.verify_token(token):
                _mark_ops_otp_verified(request)
                _log_event(request, 'otp_verified', user=request.user)
                return redirect('ops_dashboard')
        _log_event(request, 'otp_failed', user=request.user)
        error = 'Invalid code. Try again.'

    return render(request, 'ops_dashboard/otp_verify.html', {'error': error})


def ops_logout(request):
    if request.user.is_authenticated:
        _log_event(request, 'ops_logout', user=request.user)
    request.session.flush()
    logout(request)
    return redirect('ops_login')


# --- Dashboard views ---

@ops_required
def ops_dashboard(request):
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    # Active tenants = companies with any audit activity in last 30 days
    # (more reliable than last_login which is null for users who've never logged in)
    active_company_ids = (
        AuditLog.objects
        .filter(timestamp__gte=thirty_days_ago, company__isnull=False)
        .values_list('company_id', flat=True)
        .distinct()
    )

    # ── Platform signals ──────────────────────────────────────────────────────
    from django.db.models import Q as _Q
    from apps.sales_orders.batch import Batch

    total_farms_all    = Farm.objects.count()
    verified_farms_all = Farm.objects.filter(is_eudr_verified=True).count()
    eudr_pct_all       = round(verified_farms_all / total_farms_all * 100, 1) if total_farms_all else 0
    pending_farms      = total_farms_all - verified_farms_all
    batches_locked_month = Batch.objects.filter(
        updated_at__gte=thirty_days_ago, is_locked=True
    ).count()

    # ── Data quality impact (from FarmImportLog) ─────────────────────────────
    live_logs = FarmImportLog.objects.filter(dry_run=False)
    agg = live_logs.aggregate(
        total_ingested=Sum('total'),
        total_created=Sum('created'),
        total_auto_corrected=Sum('auto_corrected'),
        total_warnings=Sum('warning_count'),
        total_errors=Sum('errors'),
        total_blocked=Sum('blocked'),
        import_sessions=Count('id'),
    )
    total_ingested      = agg['total_ingested']      or 0
    total_created       = agg['total_created']       or 0
    total_auto_corrected= agg['total_auto_corrected'] or 0
    total_warnings      = agg['total_warnings']       or 0
    total_rejected      = (agg['total_errors'] or 0) + (agg['total_blocked'] or 0)
    import_sessions     = agg['import_sessions']      or 0

    # Sum transformation event counts from JSON arrays (small dataset — fine in Python)
    total_transformations = sum(
        len(log.transformation_log)
        for log in live_logs.only('transformation_log')
        if log.transformation_log
    )

    pct_normalised = round(total_auto_corrected / total_created * 100, 1) if total_created else 0
    pct_flagged    = round(total_warnings       / total_created * 100, 1) if total_created else 0
    pct_rejected   = round(total_rejected       / total_ingested * 100, 1) if total_ingested else 0

    if total_created > 0:
        impact_narrative = (
            f"AgriOps has ingested {total_ingested:,} farm records across "
            f"{import_sessions} import session{'s' if import_sessions != 1 else ''} — "
            f"{pct_normalised}% of saved records were automatically normalised before human review, "
            f"with {total_transformations:,} field-level transformation event"
            f"{'s' if total_transformations != 1 else ''} logged, attributable, and auditable."
        )
    else:
        impact_narrative = None

    context = {
        'total_tenants':  Company.objects.count(),
        'active_tenants': active_company_ids.count(),
        'total_users':    CustomUser.objects.filter(is_staff=False).count(),
        'total_farms':    Farm.objects.count(),
        'total_farmers':  Farmer.objects.count(),
        'total_suppliers': Supplier.objects.count(),
        'total_orders':   SalesOrder.objects.count(),
        'orders_this_month': SalesOrder.objects.filter(created_at__gte=thirty_days_ago).count(),
        'total_inventory': Inventory.objects.count(),
        'recent_audit':   AuditLog.objects.select_related('user').order_by('-timestamp')[:10],
        'recent_events':  OpsEventLog.objects.select_related('user').order_by('-timestamp')[:10],
        # platform signals
        'eudr_pct_all':          eudr_pct_all,
        'pending_farms':         pending_farms,
        'batches_locked_month':  batches_locked_month,
        # impact stats
        'impact': {
            'total_ingested':       total_ingested,
            'total_created':        total_created,
            'total_auto_corrected': total_auto_corrected,
            'total_transformations':total_transformations,
            'import_sessions':      import_sessions,
            'pct_normalised':       pct_normalised,
            'pct_flagged':          pct_flagged,
            'pct_rejected':         pct_rejected,
        },
        'impact_narrative': impact_narrative,
    }
    return render(request, 'ops_dashboard/dashboard.html', context)


@ops_required
def ops_tenants(request):
    from django.db.models import OuterRef, Subquery, Q

    last_activity_sq = (
        AuditLog.objects
        .filter(company=OuterRef('pk'))
        .order_by('-timestamp')
        .values('timestamp')[:1]
    )

    tenants = Company.objects.annotate(
        user_count=Count('employees', distinct=True),
        order_count=Count('sales_orders', distinct=True),
        farm_count=Count('farms', distinct=True),
        supplier_count=Count('suppliers', distinct=True),
        verified_farm_count=Count('farms', filter=Q(farms__is_eudr_verified=True), distinct=True),
        last_activity=Subquery(last_activity_sq),
    ).order_by('-created_at')

    # Compute health score per tenant (verified / total farms %)
    for t in tenants:
        if t.farm_count:
            t.eudr_pct = round(t.verified_farm_count / t.farm_count * 100)
        else:
            t.eudr_pct = None

    return render(request, 'ops_dashboard/tenants.html', {'tenants': tenants})


@ops_required
def ops_tenant_detail(request, pk):
    from django.shortcuts import get_object_or_404
    from apps.suppliers.models import Farm, FarmImportLog
    from django.db.models import Sum

    company = get_object_or_404(Company, pk=pk)

    users = CustomUser.objects.filter(company=company).order_by('system_role', 'username')

    farms = Farm.objects.filter(company=company).select_related('supplier').order_by('name')
    farm_area = farms.aggregate(total=Sum('area_hectares'))['total'] or 0
    farms_verified = farms.filter(is_eudr_verified=True).count()

    suppliers = Supplier.objects.filter(company=company).order_by('name')

    recent_pos = (
        PurchaseOrder.objects
        .filter(company=company)
        .select_related('supplier')
        .order_by('-created_at')[:10]
    )
    recent_sos = (
        SalesOrder.objects
        .filter(company=company)
        .order_by('-created_at')[:10]
    )
    recent_audit = (
        AuditLog.objects
        .filter(company=company)
        .select_related('user')
        .order_by('-timestamp')[:20]
    )

    recent_imports = (
        FarmImportLog.objects
        .filter(company=company, dry_run=False)
        .select_related('uploaded_by', 'supplier')
        .order_by('-created_at')[:5]
    )
    # Annotate each log with its transformation event count
    for log in recent_imports:
        log.transformation_count = len(log.transformation_log) if log.transformation_log else 0

    context = {
        'company': company,
        'users': users,
        'farms': farms,
        'farm_area': farm_area,
        'farms_verified': farms_verified,
        'suppliers': suppliers,
        'recent_pos': recent_pos,
        'recent_sos': recent_sos,
        'recent_audit': recent_audit,
        'recent_imports': recent_imports,
    }
    return render(request, 'ops_dashboard/tenant_detail.html', context)


@ops_required
def ops_security(request):
    audit_logs = AuditLog.objects.order_by('-timestamp')[:100]
    ops_events = OpsEventLog.objects.order_by('-timestamp')[:50]
    failed_logins = OpsEventLog.objects.filter(
        event='ops_login_failed'
    ).order_by('-timestamp')[:20]
    role_changes = AuditLog.objects.filter(
        action='update',
        model_name='CustomUser',
        changes__has_key='system_role',
    ).order_by('-timestamp')[:20]
    return render(request, 'ops_dashboard/security.html', {
        'audit_logs': audit_logs,
        'ops_events': ops_events,
        'failed_logins': failed_logins,
        'role_changes': role_changes,
    })


@ops_required
def ops_metrics(request):
    from django.db.models import Q, FloatField, ExpressionWrapper, F
    from django.utils import timezone as tz
    from apps.sales_orders.batch import Batch
    from apps.suppliers.models import FarmImportLog

    now = tz.now()
    sixty_days = now + timedelta(days=60)

    # ── EUDR health ───────────────────────────────────────────────────────────
    total_farms    = Farm.objects.count()
    verified_farms = Farm.objects.filter(is_eudr_verified=True).count()
    high_risk      = Farm.objects.filter(deforestation_risk_status='high').count()
    expiring_soon  = Farm.objects.filter(
        is_eudr_verified=True,
        verification_expiry__isnull=False,
        verification_expiry__lte=sixty_days,
        verification_expiry__gte=now,
    ).count()
    already_expired = Farm.objects.filter(
        is_eudr_verified=True,
        verification_expiry__isnull=False,
        verification_expiry__lt=now,
    ).count()
    eudr_pct = round(verified_farms / total_farms * 100, 1) if total_farms else 0

    # ── Commodity breakdown ───────────────────────────────────────────────────
    commodity_rows = []
    for row in (Farm.objects
                .values('commodity')
                .annotate(
                    total=Count('id'),
                    verified=Count('id', filter=Q(is_eudr_verified=True)),
                )
                .order_by('-total')):
        total = row['total']
        v     = row['verified']
        commodity_rows.append({
            'commodity': row['commodity'] or 'Unknown',
            'total':     total,
            'verified':  v,
            'pct':       round(v / total * 100) if total else 0,
        })

    # ── Import pipeline stats ─────────────────────────────────────────────────
    live_logs = FarmImportLog.objects.filter(dry_run=False)
    imp = live_logs.aggregate(
        sessions=Count('id'),
        ingested=Sum('total'),
        created=Sum('created'),
        corrected=Sum('auto_corrected'),
        errors=Sum('errors'),
        blocked=Sum('blocked'),
    )
    imp_sessions  = imp['sessions']  or 0
    imp_ingested  = imp['ingested']  or 0
    imp_created   = imp['created']   or 0
    imp_corrected = imp['corrected'] or 0
    imp_rejected  = (imp['errors'] or 0) + (imp['blocked'] or 0)
    imp_transformations = sum(
        len(l.transformation_log)
        for l in live_logs.only('transformation_log')
        if l.transformation_log
    )
    imp_correction_rate = round(imp_corrected / imp_created  * 100, 1) if imp_created  else 0
    imp_rejection_rate  = round(imp_rejected  / imp_ingested * 100, 1) if imp_ingested else 0

    # Most active importer by tenant
    top_importer = (
        live_logs
        .values('company__name')
        .annotate(n=Count('id'))
        .order_by('-n')
        .first()
    )

    # ── Batch & traceability ──────────────────────────────────────────────────
    total_batches  = Batch.objects.count()
    locked_batches = Batch.objects.filter(is_locked=True).count()
    eu_batches     = Batch.objects.filter(sales_order__is_eu_export=True).count()

    context = {
        # EUDR
        'total_farms':     total_farms,
        'verified_farms':  verified_farms,
        'eudr_pct':        eudr_pct,
        'high_risk':       high_risk,
        'expiring_soon':   expiring_soon,
        'already_expired': already_expired,
        # Commodity
        'commodity_rows':  commodity_rows,
        # Import
        'imp_sessions':       imp_sessions,
        'imp_ingested':       imp_ingested,
        'imp_created':        imp_created,
        'imp_transformations':imp_transformations,
        'imp_correction_rate':imp_correction_rate,
        'imp_rejection_rate': imp_rejection_rate,
        'top_importer':       top_importer,
        # Batch
        'total_batches':  total_batches,
        'locked_batches': locked_batches,
        'eu_batches':     eu_batches,
    }
    return render(request, 'ops_dashboard/metrics.html', context)


@ops_required
def ops_health(request):
    from apps.suppliers.models import FarmImportLog

    checks = []

    try:
        Company.objects.count()
        checks.append({'name': 'Database', 'status': 'ok', 'detail': 'Responsive'})
    except Exception as e:
        checks.append({'name': 'Database', 'status': 'error', 'detail': str(e)})

    try:
        recent = AuditLog.objects.order_by('-timestamp').first()
        checks.append({
            'name': 'Audit Log',
            'status': 'ok',
            'detail': f'Last entry: {recent.timestamp.strftime("%Y-%m-%d %H:%M") if recent else "No entries yet"}'
        })
    except Exception as e:
        checks.append({'name': 'Audit Log', 'status': 'error', 'detail': str(e)})

    unverified = TOTPDevice.objects.filter(confirmed=False).count()
    checks.append({
        'name': 'TOTP Devices',
        'status': 'warning' if unverified else 'ok',
        'detail': f'{unverified} unconfirmed device(s)' if unverified else 'All devices confirmed'
    })

    total_ops_users = CustomUser.objects.filter(is_staff=True).count()
    checks.append({
        'name': 'Ops Users',
        'status': 'ok',
        'detail': f'{total_ops_users} staff user(s) registered'
    })

    # EUDR expiry
    now_dt = timezone.now()
    thirty_ahead  = now_dt + timedelta(days=30)
    sixty_ahead   = now_dt + timedelta(days=60)
    expired_count = Farm.objects.filter(
        is_eudr_verified=True,
        verification_expiry__isnull=False,
        verification_expiry__lt=now_dt,
    ).count()
    expiring_30   = Farm.objects.filter(
        is_eudr_verified=True,
        verification_expiry__isnull=False,
        verification_expiry__gte=now_dt,
        verification_expiry__lte=thirty_ahead,
    ).count()
    expiring_60   = Farm.objects.filter(
        is_eudr_verified=True,
        verification_expiry__isnull=False,
        verification_expiry__gt=thirty_ahead,
        verification_expiry__lte=sixty_ahead,
    ).count()
    if expired_count:
        checks.append({
            'name': 'EUDR Expiry',
            'status': 'error',
            'detail': f'{expired_count} farm verification{"s" if expired_count != 1 else ""} already expired — renewal required',
        })
    elif expiring_30:
        checks.append({
            'name': 'EUDR Expiry',
            'status': 'warning',
            'detail': f'{expiring_30} farm verification{"s" if expiring_30 != 1 else ""} expiring within 30 days',
        })
    elif expiring_60:
        checks.append({
            'name': 'EUDR Expiry',
            'status': 'warning',
            'detail': f'{expiring_60} farm verification{"s" if expiring_60 != 1 else ""} expiring within 60 days',
        })
    else:
        checks.append({
            'name': 'EUDR Expiry',
            'status': 'ok',
            'detail': 'All active verifications valid beyond 60 days',
        })

    # Import error rate
    live_logs = FarmImportLog.objects.filter(dry_run=False)
    imp_agg = live_logs.aggregate(
        total=Sum('total'), errors=Sum('errors'), blocked=Sum('blocked')
    )
    if imp_agg['total']:
        rejected = (imp_agg['errors'] or 0) + (imp_agg['blocked'] or 0)
        rej_pct  = round(rejected / imp_agg['total'] * 100, 1)
        status   = 'warning' if rej_pct > 25 else 'ok'
        checks.append({
            'name': 'Import Rejection Rate',
            'status': status,
            'detail': f'{rej_pct}% of ingested rows rejected across {live_logs.count()} session(s)',
        })
    else:
        checks.append({
            'name': 'Import Rejection Rate',
            'status': 'ok',
            'detail': 'No import sessions recorded yet',
        })

    # Sentry
    try:
        import sentry_sdk
        client = sentry_sdk.get_client()
        dsn = getattr(client, 'dsn', None)
        if dsn:
            checks.append({'name': 'Sentry', 'status': 'ok', 'detail': 'DSN configured — error tracking active'})
        else:
            checks.append({'name': 'Sentry', 'status': 'warning', 'detail': 'Sentry SDK loaded but no DSN set'})
    except Exception as e:
        checks.append({'name': 'Sentry', 'status': 'error', 'detail': str(e)})

    # Email (SendGrid)
    from django.conf import settings
    sg_key = getattr(settings, 'SENDGRID_API_KEY', None)
    email_host = getattr(settings, 'EMAIL_HOST', '')
    if sg_key:
        checks.append({'name': 'Email (SendGrid)', 'status': 'ok', 'detail': 'API key configured'})
    elif email_host and email_host != 'localhost':
        checks.append({'name': 'Email (SendGrid)', 'status': 'ok', 'detail': f'SMTP configured — {email_host}'})
    else:
        checks.append({'name': 'Email (SendGrid)', 'status': 'warning', 'detail': 'No email transport configured — transactional emails will not send'})

    return render(request, 'ops_dashboard/health.html', {'checks': checks})


@ops_required
def ops_tenant_suspend(request, pk):
    from django.shortcuts import get_object_or_404
    if request.method != 'POST':
        return redirect('ops_tenant_detail', pk=pk)

    company = get_object_or_404(Company, pk=pk)
    company.is_active = not company.is_active
    company.save(update_fields=['is_active'])

    action = 'tenant_unsuspended' if company.is_active else 'tenant_suspended'
    _log_event(request, action, user=request.user, detail=f'{company.pk}:{company.name}')

    status = 'reactivated' if company.is_active else 'suspended'
    from django.contrib import messages
    messages.success(request, f'"{company.name}" has been {status}.')
    return redirect('ops_tenant_detail', pk=pk)


@ops_required
def ops_tenant_delete(request, pk):
    from django.shortcuts import get_object_or_404
    from apps.purchase_orders.models import PurchaseOrder
    if request.method != 'POST':
        return redirect('ops_tenant_detail', pk=pk)

    company = get_object_or_404(Company, pk=pk)

    # Hard guard — refuse if any data exists
    blockers = []
    if Farm.objects.filter(company=company).exists():
        blockers.append('farms')
    if Supplier.objects.filter(company=company).exists():
        blockers.append('suppliers')
    if CustomUser.objects.filter(company=company).exists():
        blockers.append('users')
    if PurchaseOrder.objects.filter(company=company).exists():
        blockers.append('purchase orders')
    if SalesOrder.objects.filter(company=company).exists():
        blockers.append('sales orders')

    from django.contrib import messages
    if blockers:
        messages.error(
            request,
            f'Cannot delete "{company.name}" — it still has: {", ".join(blockers)}. '
            'Remove all data first or use Django admin for a forced delete.'
        )
        return redirect('ops_tenant_detail', pk=pk)

    name = company.name
    _log_event(request, 'tenant_deleted', user=request.user, detail=f'{company.pk}:{name}')
    company.delete()
    messages.success(request, f'Tenant "{name}" has been permanently deleted.')
    return redirect('ops_tenants')


@ops_required
def ops_corridor(request):
    from django.db.models import Q as _Q

    corridors = list(
        Farm.objects
        .values('state_region', 'commodity')
        .annotate(
            total=Count('id'),
            low_risk=Count('id', filter=_Q(deforestation_risk_status='low')),
            pending=Count('id', filter=_Q(deforestation_risk_status='standard')),
            high_risk=Count('id', filter=_Q(deforestation_risk_status='high')),
            eudr_verified=Count('id', filter=_Q(is_eudr_verified=True)),
            total_area=Sum('area_hectares'),
            tenant_count=Count('company', distinct=True),
        )
        .order_by('state_region', 'commodity')
    )

    for c in corridors:
        c['verified_pct'] = round(c['eudr_verified'] / c['total'] * 100) if c['total'] else 0
        c['label'] = f"{c['state_region'] or 'Unknown'} · {c['commodity'].title() if c['commodity'] else 'Unknown'}"

    total_farms    = sum(c['total'] for c in corridors)
    total_area     = round(sum(c['total_area'] or 0 for c in corridors), 1)
    total_verified = sum(c['eudr_verified'] for c in corridors)
    platform_pct   = round(total_verified / total_farms * 100) if total_farms else 0

    return render(request, 'ops_dashboard/corridor.html', {
        'corridors':       corridors,
        'total_farms':     total_farms,
        'total_area':      total_area,
        'total_verified':  total_verified,
        'platform_pct':    platform_pct,
        'corridor_count':  len(corridors),
    })


@ops_required
def ops_geometry(request):
    """
    Geometry Integrity — scans all farms with geolocation and surfaces any
    where the stored geometry_hash no longer matches a freshly computed hash.
    Drift means the polygon was modified after the hash was written, whether
    through the UI (audit log will have the update) or via a back-channel.
    """
    farms_qs = (
        Farm.objects
        .exclude(geolocation=None)
        .select_related('company')
        .prefetch_related('batches')
        .order_by('company__name', 'name')
    )

    total    = 0
    clean    = 0
    drifted  = []
    missing  = []

    for farm in farms_qs.iterator(chunk_size=200):
        total += 1
        try:
            canonical = json.dumps(farm.geolocation, sort_keys=True, separators=(',', ':'))
            computed  = hashlib.sha256(canonical.encode()).hexdigest()
        except (TypeError, ValueError):
            continue

        if not farm.geometry_hash:
            missing.append({
                'farm':        farm,
                'company':     farm.company.name,
                'locked_batches': [b for b in farm.batches.all() if b.is_locked],
            })
        elif farm.geometry_hash != computed:
            drifted.append({
                'farm':          farm,
                'company':       farm.company.name,
                'stored':        farm.geometry_hash,
                'computed':      computed,
                'locked_batches': [b for b in farm.batches.all() if b.is_locked],
            })
        else:
            clean += 1

    return render(request, 'ops_dashboard/geometry.html', {
        'total':   total,
        'clean':   clean,
        'drifted': drifted,
        'missing': missing,
    })


# --- Access request views ---

@ops_required
def ops_access_requests(request):
    filter_status = request.GET.get('status', 'pending')
    if filter_status == 'all':
        requests_qs = AccessRequest.objects.all()
    else:
        requests_qs = AccessRequest.objects.filter(status=filter_status)

    return render(request, 'ops_dashboard/access_requests.html', {
        'requests':      requests_qs,
        'filter_status': filter_status,
        'pending_count': AccessRequest.objects.filter(status='pending').count(),
    })


@ops_required
def ops_provision_tenant(request, pk):
    access_request = get_object_or_404(AccessRequest, pk=pk, status='pending')

    # Auto-derive first/last name from the submitted name field
    parts = access_request.name.strip().split(' ', 1)
    default_first = parts[0]
    default_last  = parts[1] if len(parts) > 1 else ''

    if request.method == 'GET':
        return render(request, 'ops_dashboard/provision_tenant.html', {
            'access_request': access_request,
            'default_first':  default_first,
            'default_last':   default_last,
            'plan_choices':   Company.PLAN_CHOICES,
        })

    # POST — create company + user + send credentials
    company_name = request.POST.get('company_name', '').strip()
    first_name   = request.POST.get('first_name', '').strip()
    last_name    = request.POST.get('last_name', '').strip()
    plan_tier    = request.POST.get('plan_tier', 'starter')
    country      = request.POST.get('country', '').strip()

    if not company_name or not first_name:
        messages.error(request, 'Company name and first name are required.')
        return redirect('ops_provision_tenant', pk=pk)

    if Company.objects.filter(name=company_name).exists():
        messages.error(request, f'A company named "{company_name}" already exists.')
        return redirect('ops_provision_tenant', pk=pk)

    if CustomUser.objects.filter(email=access_request.email).exists():
        messages.error(request, f'A user with email {access_request.email} already exists.')
        return redirect('ops_provision_tenant', pk=pk)

    # Create tenant
    company = Company.objects.create(
        name=company_name,
        plan_tier=plan_tier,
        country=country,
        is_active=True,
    )

    # Derive username from email prefix
    username_base = access_request.email.split('@')[0].lower().replace('.', '_')
    username = username_base
    counter  = 1
    while CustomUser.objects.filter(username=username).exists():
        username = f"{username_base}{counter}"
        counter += 1

    user = CustomUser.objects.create_user(
        username=username,
        email=access_request.email,
        password=None,
        first_name=first_name,
        last_name=last_name,
        company=company,
        system_role='org_admin',
    )

    # Generate set-password link
    site_url = getattr(settings, 'SITE_URL', 'https://app.agriops.io')
    uid      = urlsafe_base64_encode(force_bytes(user.pk))
    token    = default_token_generator.make_token(user)
    set_password_url = f"{site_url}/set-password/{uid}/{token}/"

    threading.Thread(
        target=_send_provisioning_email,
        args=(user, set_password_url, company),
        daemon=True,
    ).start()

    # Mark request approved
    access_request.status      = 'approved'
    access_request.approved_at = timezone.now()
    access_request.save(update_fields=['status', 'approved_at'])

    _log_event(
        request, 'tenant_provisioned', user=request.user,
        detail=f'company={company.pk}:{company.name} user={user.pk}:{user.username}',
    )

    messages.success(
        request,
        f'"{company.name}" provisioned — credentials sent to {access_request.email}.',
    )
    return redirect('ops_access_requests')


@ops_required
def ops_reject_request(request, pk):
    if request.method != 'POST':
        return redirect('ops_access_requests')

    access_request = get_object_or_404(AccessRequest, pk=pk, status='pending')
    note = request.POST.get('note', '').strip()
    access_request.status = 'rejected'
    access_request.notes  = note
    access_request.save(update_fields=['status', 'notes'])

    _log_event(
        request, 'access_request_rejected', user=request.user,
        detail=f'{access_request.email} — {note[:100]}',
    )
    messages.success(request, f'Request from {access_request.email} rejected.')
    return redirect('ops_access_requests')


def _send_provisioning_email(user, set_password_url, company):
    from django.core.mail import EmailMultiAlternatives
    from django.utils.html import conditional_escape

    first_name   = conditional_escape(user.first_name)
    company_name = conditional_escape(company.name)
    username     = conditional_escape(user.username)
    escaped_url  = conditional_escape(set_password_url)

    subject   = f"Your AgriOps account is ready — {company.name}"
    body_text = (
        f"Hi {user.first_name},\n\n"
        f"Your AgriOps account has been set up.\n\n"
        f"Organisation: {company.name}\n"
        f"Username: {user.username}\n\n"
        f"Set your password and sign in here (link valid for 24 hours):\n"
        f"{set_password_url}\n\n"
        f"Keep your username safe — you'll need it every time you sign in.\n\n"
        f"AgriOps · app.agriops.io"
    )
    body_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8fafc;padding:24px;">
      <div style="background:#0a0f1a;padding:20px 24px;border-radius:8px 8px 0 0;">
        <p style="color:#22c55e;font-size:11px;letter-spacing:3px;margin:0 0 4px 0;">AGRIOPS</p>
        <h1 style="color:#ffffff;font-size:20px;margin:0;">Your account is ready</h1>
      </div>
      <div style="background:#ffffff;padding:24px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;">
        <p style="color:#1e293b;font-size:14px;">Hi <strong>{first_name}</strong>,</p>
        <p style="color:#1e293b;font-size:14px;">
          Your AgriOps account has been set up for <strong>{company_name}</strong>.
        </p>
        <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:16px;margin:20px 0;">
          <table style="width:100%;font-size:13px;">
            <tr><td style="color:#64748b;font-weight:bold;padding:4px 0;width:40%;">Organisation</td>
                <td style="color:#1e293b;">{company_name}</td></tr>
            <tr><td style="color:#64748b;font-weight:bold;padding:4px 0;">Username</td>
                <td style="color:#1e293b;font-family:monospace;">{username}</td></tr>
          </table>
        </div>
        <p style="color:#1e293b;font-size:13px;">
          Click the button below to set your password and access your account.
          This link is valid for <strong>24 hours</strong>.
        </p>
        <a href="{escaped_url}"
           style="display:inline-block;background:#22c55e;color:#0a0f1a;padding:10px 20px;
                  border-radius:6px;text-decoration:none;font-weight:bold;font-size:13px;">
          Set Password &amp; Sign In
        </a>
        <p style="margin-top:20px;color:#64748b;font-size:12px;">
          Save your username — you'll need it every time you sign in.
        </p>
        <p style="margin-top:24px;font-size:11px;color:#94a3b8;">
          AgriOps · app.agriops.io · Agricultural Supply Chain Intelligence
        </p>
      </div>
    </div>
    """
    msg = EmailMultiAlternatives(
        subject, body_text, settings.DEFAULT_FROM_EMAIL, [user.email]
    )
    msg.attach_alternative(body_html, "text/html")
    msg.send(fail_silently=True)


@ops_required
def ops_deforestation(request):
    from django.db.models import Q, OuterRef, Subquery, Count
    from apps.suppliers.models import DeforestationCheck

    # Farms with at least one polygon
    farms_with_geom = Farm.objects.exclude(geolocation=None)

    # Latest check per farm (subquery)
    latest_check_qs = DeforestationCheck.objects.filter(
        farm=OuterRef('pk')
    ).order_by('-created_at')

    annotated = farms_with_geom.annotate(
        last_check_status=Subquery(latest_check_qs.values('risk_status')[:1]),
        last_check_date=Subquery(latest_check_qs.values('assessed_at')[:1]),
        last_check_hash=Subquery(latest_check_qs.values('geometry_hash_at_assessment')[:1]),
    ).select_related('company', 'supplier')

    unchecked = [f for f in annotated if f.last_check_status is None]
    flagged   = [f for f in annotated if f.last_check_status == 'flagged']
    stale     = [
        f for f in annotated
        if f.last_check_status is not None
        and f.last_check_hash
        and f.last_check_hash != f.geometry_hash
    ]

    # Per-tenant summary
    tenant_rows = []
    for company in Company.objects.filter(is_active=True).order_by('name'):
        company_farms = [f for f in annotated if f.company_id == company.pk]
        total    = len(company_farms)
        checked  = sum(1 for f in company_farms if f.last_check_status is not None)
        n_flagged = sum(1 for f in company_farms if f.last_check_status == 'flagged')
        n_stale  = sum(
            1 for f in company_farms
            if f.last_check_status is not None
            and f.last_check_hash and f.last_check_hash != f.geometry_hash
        )
        n_clear  = sum(1 for f in company_farms if f.last_check_status == 'clear')
        if total:
            tenant_rows.append({
                'company':  company,
                'total':    total,
                'checked':  checked,
                'unchecked': total - checked,
                'clear':    n_clear,
                'flagged':  n_flagged,
                'stale':    n_stale,
                'pct':      round(checked / total * 100),
            })

    total_with_geom = len(list(annotated))

    return render(request, 'ops_dashboard/deforestation.html', {
        'total_with_geom': total_with_geom,
        'unchecked_count': len(unchecked),
        'flagged_count':   len(flagged),
        'stale_count':     len(stale),
        'unchecked':       unchecked[:50],
        'flagged':         flagged,
        'stale':           stale,
        'tenant_rows':     tenant_rows,
    })
