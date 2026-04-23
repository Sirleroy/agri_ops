"""
Request Access — manual provisioning flow.
1. Saves AccessRequest to database (status: pending)
2. Notifies founder for manual review via ops dashboard
3. No Company or user account is created automatically

Self-service provisioning is disabled pending NDPA compliance formalisation.
Tenants are onboarded manually after DPO review and NDPC registration.
"""
from django.http import JsonResponse
from django.core.cache import cache
from django.views import View
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes


class RequestAccessView(View):
    def post(self, request):
        # ── Rate limiting — max 5 requests per IP per hour ───────
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
        cache_key = f'request_access_{ip}'
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            return JsonResponse({'error': 'Too many requests. Please try again later.'}, status=429)
        cache.set(cache_key, attempts + 1, timeout=3600)

        name      = request.POST.get('name', '').strip()
        email     = request.POST.get('email', '').strip()
        company   = request.POST.get('company', '').strip()
        commodity = request.POST.get('commodity', '').strip()

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
            commodity=commodity,
            status='pending'
        )

        # ── Notify founder — manual provisioning required ─────────────────
        # Self-service tenant provisioning is disabled pending NDPA compliance
        # formalisation. Access requests are reviewed and provisioned manually
        # via the ops dashboard.
        company_name = company or f"{name}'s Organisation"
        try:
            _notify_founder(name, email, company_name, None, commodity)
        except Exception:
            pass

        return JsonResponse({
            'success': True,
            'message': 'Request received. We will be in touch within 48 hours.'
        })


def _send_welcome_email(user, set_password_url, company):
    from django.core.mail import EmailMultiAlternatives

    subject = "Welcome to AgriOps — Set your password to get started"
    body_text = (
        f"Welcome to AgriOps, {user.first_name}!\n\n"
        f"Your account has been created.\n\n"
        f"Organisation: {company.name}\n"
        f"Username: {user.username}\n\n"
        f"Set your password using the link below (valid for 3 days):\n"
        f"{set_password_url}\n\n"
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
          </table>
        </div>
        <p style="color:#1e293b;font-size:13px;">Click the button below to set your password and access your account. This link is valid for <strong>3 days</strong>.</p>
        <a href="{set_password_url}"
           style="background:#22c55e;color:#0a0f1a;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:bold;font-size:13px;">
          Set My Password
        </a>
        <p style="margin-top:24px;font-size:11px;color:#94a3b8;">
          AgriOps · app.agriops.io · Agricultural Supply Chain Intelligence
        </p>
      </div>
    </div>
    """
    import threading
    def _do_send():
        msg = EmailMultiAlternatives(subject, body_text, settings.DEFAULT_FROM_EMAIL, [user.email])
        msg.attach_alternative(body_html, "text/html")
        msg.send(fail_silently=True)
    threading.Thread(target=_do_send, daemon=True).start()


def _notify_founder(name, email, company, username, commodity=''):
    import threading
    from django.core.mail import EmailMultiAlternatives
    founder_email = getattr(settings, 'FOUNDER_EMAIL', '')
    if not founder_email:
        return
    commodity_label = commodity.replace('_', ' ').title() if commodity else 'Not specified'
    subject = f"[AgriOps] New access request — {name}"
    body_text = (
        f"New access request received. Manual provisioning required.\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Company: {company}\n"
        f"Commodity: {commodity_label}\n\n"
        f"Review and provision via the ops dashboard:\n"
        f"https://app.agriops.io/ops/\n"
    )
    def _do_send():
        msg = EmailMultiAlternatives(subject, body_text, settings.DEFAULT_FROM_EMAIL, [founder_email])
        msg.send(fail_silently=True)
    threading.Thread(target=_do_send, daemon=True).start()
