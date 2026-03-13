
from django.contrib import admin
from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'city', 'plan_tier', 'is_active', 'created_at')
    list_filter = ('plan_tier', 'is_active', 'country')
    search_fields = ('name', 'email')
