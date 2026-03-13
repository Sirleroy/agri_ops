from django.contrib import admin
from .models import SalesOrder, SalesOrderItem


class SalesOrderItemInline(admin.TabularInline):
    model = SalesOrderItem
    extra = 1


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'company', 'customer_name', 'status', 'order_date')
    list_filter = ('status', 'company')
    search_fields = ('order_number', 'customer_name', 'customer_email')
    inlines = [SalesOrderItemInline]
