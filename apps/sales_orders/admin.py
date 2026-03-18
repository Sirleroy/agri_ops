from django.contrib import admin
from .models import SalesOrder, SalesOrderItem
from .batch import Batch


class SalesOrderItemInline(admin.TabularInline):
    model = SalesOrderItem
    extra = 0


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display  = ('order_number', 'customer_name', 'status', 'order_date', 'company')
    list_filter   = ('status', 'company')
    search_fields = ('order_number', 'customer_name')
    inlines       = [SalesOrderItemInline]


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display  = ('batch_number', 'commodity', 'company', 'sales_order', 'created_at')
    list_filter   = ('commodity', 'company')
    search_fields = ('batch_number', 'commodity')
    readonly_fields = ('public_token', 'created_at', 'updated_at')
    filter_horizontal = ('farms',)
