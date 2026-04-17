from django.apps import AppConfig


class CompaniesConfig(AppConfig):
    name = 'apps.companies'

    def ready(self):
        import os
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured

        # Only validate in production — skip dev/test where env vars may be absent
        if not settings.DEBUG:
            required = [
                'SECRET_KEY',
                'DATABASE_URL',
                'ALLOWED_HOSTS',
            ]
            missing = [var for var in required if not os.environ.get(var)]
            if missing:
                raise ImproperlyConfigured(
                    f"AgriOps: required environment variable(s) not set: {', '.join(missing)}. "
                    f"Check your Render environment configuration."
                )
