from django.contrib import admin
from .models import Supplier, Farm, ComplianceDocument


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display  = ('name', 'category', 'company', 'country', 'is_active')
    list_filter   = ('category', 'is_active', 'country')
    search_fields = ('name', 'contact_person', 'email')


class ComplianceDocumentInline(admin.TabularInline):
    model = ComplianceDocument
    extra = 0
    readonly_fields = ('uploaded_at', 'uploaded_by')


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display  = ('name', 'supplier', 'company', 'commodity',
                     'deforestation_risk_status', 'is_eudr_verified', 'verification_expiry')
    list_filter   = ('deforestation_risk_status', 'is_eudr_verified', 'commodity')
    search_fields = ('name', 'farmer_name', 'supplier__name')
    readonly_fields = ('created_at', 'updated_at')
    inlines       = [ComplianceDocumentInline]


@admin.register(ComplianceDocument)
class ComplianceDocumentAdmin(admin.ModelAdmin):
    list_display  = ('farm', 'doc_type', 'uploaded_by', 'uploaded_at', 'is_current')
    list_filter   = ('doc_type', 'is_current')
    readonly_fields = ('uploaded_at',)
