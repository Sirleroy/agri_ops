import qrcode
import qrcode.image.svg
import io
from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate

from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp import devices_for_user

from django.conf import settings

from apps.audit.models import AuditLog
from apps.companies.models import Company
from apps.inventory.models import Inventory
from apps.sales_orders.models import SalesOrder
from apps.purchase_orders.models import PurchaseOrder
from apps.suppliers.models import Supplier, Farm, Farmer, FarmImportLog
from apps.users.models import CustomUser
from .models import OpsEventLog


# --- Helpers ---

def _log_event(request, event, user=None):
    OpsEventLog.objects.create(
        user=user,
        event=event,
        ip_address=request.META.get('REMOTE_ADDR'),
    )


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
            _log_event(request, 'otp_setup', user=user)
            return redirect('ops_otp_verify')
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
                request.session['otp_verified'] = True
                request.session.set_expiry(7200)
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
