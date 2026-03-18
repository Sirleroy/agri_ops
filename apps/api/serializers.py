from rest_framework import serializers
from apps.suppliers.models import Supplier, Farm
from apps.products.models import Product
from apps.inventory.models import Inventory
from apps.purchase_orders.models import PurchaseOrder
from apps.sales_orders.models import SalesOrder


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Supplier
        fields = ['id', 'name', 'category', 'contact_person', 'phone',
                  'email', 'country', 'city', 'is_active', 'reliability_score', 'created_at']
        read_only_fields = ['id', 'created_at']


class FarmSerializer(serializers.ModelSerializer):
    compliance_status = serializers.ReadOnlyField()

    class Meta:
        model  = Farm
        fields = ['id', 'supplier', 'name', 'farmer_name', 'country',
                  'state_region', 'commodity', 'area_hectares',
                  'deforestation_risk_status', 'is_eudr_verified',
                  'verified_date', 'verification_expiry',
                  'compliance_status', 'created_at']
        read_only_fields = ['id', 'compliance_status', 'created_at']


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Product
        fields = ['id', 'name', 'category', 'unit', 'unit_price',
                  'supplier', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class InventorySerializer(serializers.ModelSerializer):
    product_name  = serializers.ReadOnlyField(source='product.name')
    is_low_stock  = serializers.ReadOnlyField()

    class Meta:
        model  = Inventory
        fields = ['id', 'product', 'product_name', 'quantity',
                  'warehouse_location', 'low_stock_threshold',
                  'is_low_stock', 'last_updated']
        read_only_fields = ['id', 'product_name', 'is_low_stock', 'last_updated']


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.ReadOnlyField(source='supplier.name')

    class Meta:
        model  = PurchaseOrder
        fields = ['id', 'order_number', 'supplier', 'supplier_name',
                  'status', 'expected_delivery', 'notes', 'created_at']
        read_only_fields = ['id', 'supplier_name', 'created_at']


class SalesOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SalesOrder
        fields = ['id', 'order_number', 'customer_name', 'customer_email',
                  'customer_phone', 'status', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']
