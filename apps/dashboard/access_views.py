"""
Request Access — auto-approval flow.
1. Saves AccessRequest to database
2. Creates Company + OrgAdmin user
3. Sends welcome email to applicant
4. Sends founder notification email
"""
import secrets
import string
from django.http import JsonResponse
from django.core.cache import cache
from django.views import View
from django.utils import timezone
from django.conf import settings


def _generate_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class RequestAccessView(View):
    def post(self, request):
        # ── Rate limiting — max 5 requests per IP per hour ───────
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
        cache_key = f'request_access_{ip}'
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            return JsonResponse({'error': 'Too many requests. Please try again later.'}, status=429)
        cache.set(cache_key, attempts + 1, timeout=3600)

        name    = request.POST.get('name', '').strip()
        email   = request.POST.get('email', '').strip()
        company = request.POST.get('company', '').strip()

        # ── Validate ──────────────────────────────────────────
        if not name or not email:
            return JsonResponse({'error': 'Name and email are required.'}, status=400)

        from apps.dashboard.models import AccessRequest
        if AccessRequest.objects.filter(email=email).exists():
            return JsonResponse({'error': 'This email has already requested access.'}, status=400)

        # ── Save request ──────────────────────────────────────
        access_request = AccessRequest.objects.create(
            name=name,
            email=email,
            company=company,
            status='pending'
        )

        # ── Auto-approve ──────────────────────────────────────
        try:
            from apps.companies.models import Company
            from apps.users.models import CustomUser

            # Create company
            company_name = company or f"{name}'s Organisation"
            company_obj, _ = Company.objects.get_or_create(
                name=company_name,
                defaults={
                    'country': 'Nigeria',
                    'city': '',
                    'email': email,
                    'plan_tier': 'free',
                }
            )

            # Generate username from email
            username_base = email.split('@')[0].lower().replace('.', '_')
            username = username_base
            counter = 1
            while CustomUser.objects.filter(username=username).exists():
                username = f"{username_base}{counter}"
                counter += 1

            # Generate temporary password
            temp_password = _generate_password()

            # Create user
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=temp_password,
                first_name=name.split()[0] if name else '',
                last_name=' '.join(name.split()[1:]) if len(name.split()) > 1 else '',
                company=company_obj,
                system_role='org_admin',
                job_title='Administrator',
            )

            # Update access request
            access_request.status = 'approved'
            access_request.approved_at = timezone.now()
            access_request.save()

            # ── Send welcome email ────────────────────────────
            _send_welcome_email(user, temp_password, company_obj)

            # ── Notify founder ────────────────────────────────
            _notify_founder(name, email, company_name, username)

            return JsonResponse({
                'success': True,
                'message': 'Access approved. Check your email for login credentials.'
            })

        except Exception as e:
            access_request.notes = str(e)
            access_request.save()
            return JsonResponse({
                'success': True,
                'message': 'Request received. We will be in touch within 48 hours.'
            })


def _send_welcome_email(user, temp_password, company):
    from django.core.mail import EmailMultiAlternatives
    site_url = getattr(settings, 'SITE_URL', 'https://app.agriops.io')

    subject = "Welcome to AgriOps — Your account is ready"
    body_text = (
        f"Welcome to AgriOps, {user.first_name}!\n\n"
        f"Your account has been created.\n\n"
        f"Organisation: {company.name}\n"
        f"Username: {user.username}\n"
        f"Temporary Password: {temp_password}\n\n"
        f"Please log in and change your password immediately.\n\n"
        f"Login: {site_url}/login/\n\n"
        f"AgriOps · app.agriops.io"
    )
    body_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8fafc;padding:24px;">
      <div style="background:#0a0f1a;padding:20px 24px;border-radius:8px 8px 0 0;">
        <p style="color:#22c55e;font-size:11px;letter-spacing:3px;margin:0 0 4px 0;">AGRIOPS</p>
        <h1 style="color:#ffffff;font-size:20px;margin:0;">Welcome to AgriOps</h1>
      </div>
      <div style="background:#ffffff;padding:24px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;">
        <p style="color:#1e293b;font-size:14px;">Hi <strong>{user.first_name}</strong>, your account is ready.</p>
        <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:16px;margin:20px 0;">
          <table style="width:100%;font-size:13px;">
            <tr><td style="color:#64748b;font-weight:bold;padding:4px 0;width:40%;">Organisation</td>
                <td style="color:#1e293b;">{company.name}</td></tr>
            <tr><td style="color:#64748b;font-weight:bold;padding:4px 0;">Username</td>
                <td style="color:#1e293b;font-family:monospace;">{user.username}</td></tr>
            <tr><td style="color:#64748b;font-weight:bold;padding:4px 0;">Temporary Password</td>
                <td style="color:#1e293b;font-family:monospace;">{temp_password}</td></tr>
          </table>
        </div>
        <div style="background:#fef9c3;border:1px solid #fde047;border-radius:6px;padding:10px 14px;margin-bottom:20px;">
          <p style="margin:0;color:#854d0e;font-size:12px;">⚠ Please change your password immediately after first login.</p>
        </div>
        <a href="{site_url}/login/"
           style="background:#22c55e;color:#0a0f1a;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:13px;">
          Log In to AgriOps
        </a>
        <p style="margin-top:24px;font-size:11px;color:#94a3b8;">
          AgriOps · app.agriops.io · Agricultural Supply Chain Intelligence
        </p>
      </div>
    </div>
    """
    msg = EmailMultiAlternatives(subject, body_text, settings.DEFAULT_FROM_EMAIL, [user.email])
    msg.attach_alternative(body_html, "text/html")
    msg.send(fail_silently=True)


def _notify_founder(name, email, company, username):
    from django.core.mail import EmailMultiAlternatives
    founder_email = getattr(settings, 'FOUNDER_EMAIL', '')
    if not founder_email:
        return
    subject = f"[AgriOps] New user onboarded — {name}"
    body_text = (
        f"New user auto-approved on AgriOps.\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Company: {company}\n"
        f"Username: {username}\n\n"
        f"View access requests: https://app.agriops.io/admin/dashboard/accessrequest/\n"
    )
    msg = EmailMultiAlternatives(subject, body_text, settings.DEFAULT_FROM_EMAIL, [founder_email])
    msg.send(fail_silently=True)
