from django.contrib import admin
from .models import Inventory


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display  = ('product', 'lot_number', 'quantity', 'quality_grade',
                     'moisture_content', 'warehouse_location', 'origin_state',
                     'is_low_stock', 'last_updated')
    list_filter   = ('quality_grade', 'origin_state')
    search_fields = ('product__name', 'lot_number', 'warehouse_location')
    readonly_fields = ('created_at', 'last_updated')
