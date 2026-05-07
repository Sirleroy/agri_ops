import sentry_sdk

_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
    "cdn.tailwindcss.com cdn.jsdelivr.net unpkg.com cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline' "
    "fonts.googleapis.com cdn.jsdelivr.net unpkg.com cdnjs.cloudflare.com; "
    "font-src 'self' fonts.gstatic.com; "
    "img-src 'self' data: *.tile.openstreetmap.org server.arcgisonline.com; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)

_PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Content-Security-Policy'] = _CSP
        response['Permissions-Policy'] = _PERMISSIONS_POLICY
        return response


class SentryTenantContextMiddleware:
    """
    Tags every Sentry event with the requesting user's company and role,
    and binds the user id (no username/email — those are PII). Lets us
    filter Sentry by tenant when a customer reports an issue.
    No-op if SENTRY_DSN is unset.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            sentry_sdk.set_user({'id': user.id})
            company = getattr(user, 'company', None)
            if company is not None:
                sentry_sdk.set_tag('company_id', company.pk)
            role = getattr(user, 'system_role', None)
            if role:
                sentry_sdk.set_tag('system_role', role)
        return self.get_response(request)
