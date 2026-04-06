from django.db import models


class AccessRequest(models.Model):

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    COMMODITY_CHOICES = [
        ('cocoa',      'Cocoa'),
        ('coffee',     'Coffee'),
        ('soy',        'Soy'),
        ('palm_oil',   'Palm Oil'),
        ('multiple',   'Multiple commodities'),
        ('other',      'Other'),
    ]

    name        = models.CharField(max_length=255)
    email       = models.EmailField(unique=True)
    company     = models.CharField(max_length=255, blank=True)
    commodity   = models.CharField(max_length=20, choices=COMMODITY_CHOICES, blank=True)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at  = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    notes       = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.email} ({self.status})"
