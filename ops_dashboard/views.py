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
    from django.db.models import OuterRef, Subquery

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
        last_activity=Subquery(last_activity_sq),
    ).order_by('-created_at')
    return render(request, 'ops_dashboard/tenants.html', {'tenants': tenants})


@ops_required
def ops_tenant_detail(request, pk):
    from django.shortcuts import get_object_or_404
    from apps.suppliers.models import Farm
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
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    monthly_orders = (
        SalesOrder.objects
        .filter(created_at__gte=thirty_days_ago)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    context = {
        'total_sales_orders': SalesOrder.objects.count(),
        'total_purchase_orders': PurchaseOrder.objects.count(),
        'total_suppliers': Supplier.objects.count(),
        'total_inventory_items': Inventory.objects.count(),
        'monthly_orders': list(monthly_orders),
    }
    return render(request, 'ops_dashboard/metrics.html', context)


@ops_required
def ops_health(request):
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
