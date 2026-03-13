from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

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
    """
    Base viewset — all querysets auto-filtered to request.user.company.
    Writes are logged to AuditLog.
    Deletes require Manager or above.
    """
    permission_classes = [IsTenantMember]

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)

    def perform_create(self, serializer):
        instance = serializer.save(company=self.request.user.company)
        log_action(self.request, 'create', instance)

    def perform_update(self, serializer):
        instance = serializer.save()
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
        """Farms not yet EUDR verified — useful for compliance dashboards."""
        qs = self.get_queryset().filter(is_eudr_verified=False)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='high-risk')
    def high_risk(self, request):
        """Farms flagged as high deforestation risk."""
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
        """Inventory items at or below their low stock threshold."""
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
