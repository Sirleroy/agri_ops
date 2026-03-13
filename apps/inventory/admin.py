from django.contrib import admin
from .models import Inventory


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'company', 'quantity', 'warehouse_location', 'is_low_stock', 'last_updated')
    list_filter = ('company', 'warehouse_location')
    search_fields = ('product__name', 'warehouse_location')
