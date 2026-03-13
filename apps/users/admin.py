from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'system_role', 'job_title', 'company', 'is_active')
    list_filter = ('system_role', 'is_active')
    search_fields = ('username', 'email')
    fieldsets = UserAdmin.fieldsets + (
        ('Role & Company', {'fields': ('system_role', 'job_title', 'company', 'phone')}),
    )
