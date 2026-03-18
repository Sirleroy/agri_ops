from django.db import models
from django.conf import settings

class OpsEventLog(models.Model):
    EVENT_CHOICES = [
        ('ops_login', 'Ops Login'),
        ('ops_login_failed', 'Ops Login Failed'),
        ('ops_logout', 'Ops Logout'),
        ('otp_setup', 'OTP Setup'),
        ('otp_verified', 'OTP Verified'),
        ('otp_failed', 'OTP Failed'),
    ]
    user       = models.ForeignKey(
                    settings.AUTH_USER_MODEL,
                    on_delete=models.SET_NULL,
                    null=True, blank=True,
                    related_name='ops_events'
                 )
    event      = models.CharField(max_length=30, choices=EVENT_CHOICES)
    detail     = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['event', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} | {self.user} | {self.event}"
