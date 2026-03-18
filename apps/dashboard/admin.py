from django.contrib import admin
from .models import AccessRequest


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display  = ('name', 'email', 'company', 'status', 'created_at', 'approved_at')
    list_filter   = ('status',)
    search_fields = ('name', 'email', 'company')
    readonly_fields = ('created_at', 'approved_at')
