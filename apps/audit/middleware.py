import sentry_sdk


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
