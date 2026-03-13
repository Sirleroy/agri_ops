from django.contrib import admin
from .models import Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'category', 'contact_person', 'phone', 'is_active')
    list_filter = ('category', 'is_active', 'country')
    search_fields = ('name', 'contact_person', 'email')
