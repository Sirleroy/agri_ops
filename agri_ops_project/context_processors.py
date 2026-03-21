from django.conf import settings

def analytics(request):
    return {
        'POSTHOG_API_KEY': getattr(settings, 'POSTHOG_API_KEY', ''),
        'POSTHOG_HOST': getattr(settings, 'POSTHOG_HOST', ''),
    }
