from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'category', 'supplier', 'unit_price', 'unit', 'is_active')
    list_filter = ('category', 'is_active', 'unit')
    search_fields = ('name', 'description')
