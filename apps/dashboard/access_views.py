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
from django.conf import settings
from django.contrib.auth import views as auth_views


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


class InvitePasswordSetView(auth_views.PasswordResetConfirmView):
    """PasswordResetConfirmView that passes the user into template context so the
    set-password page can display the username — critical because the login form
    asks for username, not email."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if getattr(self, 'user', None):
            context['invited_user'] = self.user
        return context


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
