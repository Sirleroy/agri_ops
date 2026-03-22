from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.conf import settings

from apps.users.models import CustomUser
from apps.audit.models import AuditLog


def org_admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.system_role != 'org_admin':
            return redirect('dashboard:index')
        if not request.user.company:
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


@org_admin_required
def admin_overview(request):
    company = request.user.company
    total_users = CustomUser.objects.filter(company=company).count()
    active_users = CustomUser.objects.filter(company=company, is_active=True).count()
    recent_audit = AuditLog.objects.filter(company=company).order_by('-timestamp')[:10]
    context = {
        'company': company,
        'total_users': total_users,
        'active_users': active_users,
        'recent_audit': recent_audit,
    }
    return render(request, 'admin_panel/overview.html', context)


@org_admin_required
def admin_users(request):
    company = request.user.company
    users = CustomUser.objects.filter(company=company).order_by('system_role', 'first_name')
    return render(request, 'admin_panel/users.html', {'users': users, 'company': company})


@org_admin_required
def admin_change_role(request, user_id):
    company = request.user.company
    user = get_object_or_404(CustomUser, id=user_id, company=company)
    if request.method == 'POST':
        new_role = request.POST.get('system_role')
        valid_roles = [r[0] for r in CustomUser.SYSTEM_ROLE_CHOICES]
        if new_role in valid_roles:
            # Prevent demoting yourself
            if user == request.user:
                messages.error(request, 'You cannot change your own role.')
                return redirect('admin_panel:users')
            old_role = user.system_role
            user.system_role = new_role
            user.save()
            AuditLog.objects.create(
                company=company,
                user=request.user,
                action='update',
                model_name='CustomUser',
                object_id=user.id,
                object_repr=str(user),
                changes={'system_role': {'from': old_role, 'to': new_role}},
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, f'Role updated for {user.get_full_name() or user.username}.')
        else:
            messages.error(request, 'Invalid role.')
    return redirect('admin_panel:users')


@org_admin_required
def admin_deactivate_user(request, user_id):
    company = request.user.company
    user = get_object_or_404(CustomUser, id=user_id, company=company)
    if request.method == 'POST':
        if user == request.user:
            messages.error(request, 'You cannot deactivate your own account.')
            return redirect('admin_panel:users')
        user.is_active = not user.is_active
        user.save()
        action = 'activated' if user.is_active else 'deactivated'
        messages.success(request, f'User {action} successfully.')
    return redirect('admin_panel:users')


@org_admin_required
def admin_invite_user(request):
    company = request.user.company
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        system_role = request.POST.get('system_role', 'staff')
        job_title = request.POST.get('job_title', '').strip()

        if not email or not first_name:
            messages.error(request, 'Email and first name are required.')
            return redirect('admin_panel:users')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'A user with this email already exists.')
            return redirect('admin_panel:users')

        username_base = email.split('@')[0].lower().replace('.', '_')
        username = username_base
        counter = 1
        while CustomUser.objects.filter(username=username).exists():
            username = f"{username_base}{counter}"
            counter += 1

        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=None,
            first_name=first_name,
            last_name=last_name,
            company=company,
            system_role=system_role,
            job_title=job_title,
        )
        user.set_unusable_password()
        user.save()

        # Send invite email with set-password link
        site_url = getattr(settings, 'SITE_URL', 'https://app.agriops.io')
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        set_password_url = f"{site_url}/set-password/{uid}/{token}/"
        _send_invite_email(user, set_password_url, company, request.user)

        messages.success(request, f'Invitation sent to {email}.')
    return redirect('admin_panel:users')


@org_admin_required
def admin_company_settings(request):
    company = request.user.company
    if request.method == 'POST':
        company.name = request.POST.get('name', company.name).strip()
        company.email = request.POST.get('email', company.email).strip()
        company.phone = request.POST.get('phone', company.phone).strip()
        company.city = request.POST.get('city', company.city).strip()
        company.address = request.POST.get('address', company.address).strip()
        company.nepc_registration_number = request.POST.get(
            'nepc_registration_number', company.nepc_registration_number
        ).strip()
        company.save()
        AuditLog.objects.create(
            company=company,
            user=request.user,
            action='update',
            model_name='Company',
            object_id=company.id,
            object_repr=str(company),
            changes={},
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, 'Company settings updated.')
        return redirect('admin_panel:company_settings')
    return render(request, 'admin_panel/company_settings.html', {'company': company})


@org_admin_required
def admin_audit_log(request):
    company = request.user.company
    audit_logs = AuditLog.objects.filter(company=company).order_by('-timestamp')[:200]
    return render(request, 'admin_panel/audit_log.html', {
        'audit_logs': audit_logs,
        'company': company,
    })


@org_admin_required
def admin_roles(request):
    company = request.user.company
    from django.db.models import Count
    role_summary = (
        CustomUser.objects
        .filter(company=company)
        .values('system_role')
        .annotate(count=Count('id'))
        .order_by('system_role')
    )
    users_by_role = {}
    for entry in role_summary:
        users_by_role[entry['system_role']] = entry['count']

    return render(request, 'admin_panel/roles.html', {
        'company': company,
        'users_by_role': users_by_role,
        'role_choices': CustomUser.SYSTEM_ROLE_CHOICES,
    })


def _send_invite_email(user, set_password_url, company, invited_by):
    from django.core.mail import EmailMultiAlternatives
    subject = f"You've been invited to join {company.name} on AgriOps"
    body_text = (
        f"Hi {user.first_name},\n\n"
        f"{invited_by.get_full_name() or invited_by.username} has invited you to join "
        f"{company.name} on AgriOps.\n\n"
        f"Username: {user.username}\n\n"
        f"Set your password here (valid for 3 days):\n{set_password_url}\n\n"
        f"AgriOps · app.agriops.io"
    )
    body_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8fafc;padding:24px;">
      <div style="background:#0a0f1a;padding:20px 24px;border-radius:8px 8px 0 0;">
        <p style="color:#22c55e;font-size:11px;letter-spacing:3px;margin:0 0 4px 0;">AGRIOPS</p>
        <h1 style="color:#ffffff;font-size:20px;margin:0;">You've been invited</h1>
      </div>
      <div style="background:#ffffff;padding:24px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;">
        <p style="color:#1e293b;font-size:14px;">Hi <strong>{user.first_name}</strong>,</p>
        <p style="color:#1e293b;font-size:14px;">
          <strong>{invited_by.get_full_name() or invited_by.username}</strong> has invited you
          to join <strong>{company.name}</strong> on AgriOps.
        </p>
        <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:16px;margin:20px 0;">
          <table style="width:100%;font-size:13px;">
            <tr><td style="color:#64748b;font-weight:bold;padding:4px 0;width:40%;">Organisation</td>
                <td style="color:#1e293b;">{company.name}</td></tr>
            <tr><td style="color:#64748b;font-weight:bold;padding:4px 0;">Username</td>
                <td style="color:#1e293b;font-family:monospace;">{user.username}</td></tr>
          </table>
        </div>
        <a href="{set_password_url}"
           style="background:#22c55e;color:#0a0f1a;padding:10px 20px;border-radius:6px;
                  text-decoration:none;font-weight:bold;font-size:13px;">
          Accept Invitation
        </a>
        <p style="margin-top:24px;font-size:11px;color:#94a3b8;">
          This link expires in 3 days. AgriOps · app.agriops.io
        </p>
      </div>
    </div>
    """
    msg = EmailMultiAlternatives(
        subject, body_text, settings.DEFAULT_FROM_EMAIL, [user.email]
    )
    msg.attach_alternative(body_html, "text/html")
    msg.send(fail_silently=True)
