import json

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.suppliers.models import Supplier, Farm
from apps.products.models import Product
from apps.inventory.models import Inventory
from apps.purchase_orders.models import PurchaseOrder
from apps.sales_orders.models import SalesOrder
from apps.audit.mixins import log_action

from .serializers import (
    SupplierSerializer, FarmSerializer, ProductSerializer,
    InventorySerializer, PurchaseOrderSerializer, SalesOrderSerializer,
)
from .permissions import IsTenantMember, IsManagerOrAbove


class TenantScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [IsTenantMember]

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)

    def perform_create(self, serializer):
        instance = serializer.save(company=self.request.user.company)
        log_action(self.request, 'create', instance)

    def perform_update(self, serializer):
        # Fix 3 — explicitly pass company to prevent tenant drift
        instance = serializer.save(company=self.request.user.company)
        log_action(self.request, 'update', instance)

    def perform_destroy(self, instance):
        if not IsManagerOrAbove().has_permission(self.request, self):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Manager or above required to delete.")
        log_action(self.request, 'delete', instance)
        instance.delete()


class SupplierViewSet(TenantScopedViewSet):
    queryset           = Supplier.objects.all()
    serializer_class   = SupplierSerializer


class FarmViewSet(TenantScopedViewSet):
    queryset           = Farm.objects.select_related('supplier').all()
    serializer_class   = FarmSerializer

    @action(detail=False, methods=['get'], url_path='eudr-pending')
    def eudr_pending(self, request):
        qs = self.get_queryset().filter(is_eudr_verified=False)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='high-risk')
    def high_risk(self, request):
        qs = self.get_queryset().filter(deforestation_risk_status='high')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class ProductViewSet(TenantScopedViewSet):
    queryset           = Product.objects.all()
    serializer_class   = ProductSerializer


class InventoryViewSet(TenantScopedViewSet):
    queryset           = Inventory.objects.select_related('product').all()
    serializer_class   = InventorySerializer

    @action(detail=False, methods=['get'], url_path='low-stock')
    def low_stock(self, request):
        from django.db.models import F
        qs = self.get_queryset().filter(quantity__lte=F('low_stock_threshold'))
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class PurchaseOrderViewSet(TenantScopedViewSet):
    queryset           = PurchaseOrder.objects.select_related('supplier').all()
    serializer_class   = PurchaseOrderSerializer


class SalesOrderViewSet(TenantScopedViewSet):
    queryset           = SalesOrder.objects.all()
    serializer_class   = SalesOrderSerializer


class FarmGeoJSONImportView(APIView):
    """
    POST /api/v1/farms/import/

    Accepts a SW Maps GeoJSON FeatureCollection and runs the full 4-layer
    validation pipeline. Designed for mobile share-to-URL workflows.

    Auth: Bearer JWT token
    Body: multipart/form-data  — geojson_file (file), supplier_id (int), default_commodity (str, optional)
       OR application/json     — {"type":"FeatureCollection","features":[...]} with supplier_id + default_commodity as query params

    Returns: {total, created, duplicates, blocked, errors, error_detail, blocked_detail}
    """
    permission_classes = [IsTenantMember]
    parser_classes     = [MultiPartParser, JSONParser]

    def post(self, request):
        from apps.suppliers.views import run_farm_geojson_import

        company           = request.user.company
        supplier_id       = request.data.get('supplier_id') or request.query_params.get('supplier_id')
        default_commodity = (request.data.get('default_commodity') or request.query_params.get('default_commodity', '')).strip()

        if not supplier_id:
            return Response({'error': 'supplier_id is required.'}, status=400)

        supplier = Supplier.objects.filter(pk=supplier_id, company=company).first()
        if not supplier:
            return Response({'error': 'Invalid supplier_id.'}, status=400)

        geojson_file = request.FILES.get('geojson_file')
        if geojson_file:
            try:
                data = json.loads(geojson_file.read().decode('utf-8'))
            except Exception as e:
                return Response({'error': f'Could not read file: {e}'}, status=400)
        elif isinstance(request.data, dict) and request.data.get('type') == 'FeatureCollection':
            data = request.data
        else:
            return Response({'error': 'Provide a geojson_file (multipart) or a raw GeoJSON FeatureCollection body.'}, status=400)

        if data.get('type') != 'FeatureCollection':
            return Response({'error': 'Must be a GeoJSON FeatureCollection.'}, status=400)

        features = data.get('features') or []
        if not features:
            return Response({'error': 'FeatureCollection contains no features.'}, status=400)

        result = run_farm_geojson_import(company, supplier, features, default_commodity)
        status_code = 201 if result['created'] > 0 else 200
        return Response(result, status=status_code)
