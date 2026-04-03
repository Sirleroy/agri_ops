from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

router = DefaultRouter()
router.register('suppliers',       views.SupplierViewSet,      basename='supplier')
router.register('farms',           views.FarmViewSet,          basename='farm')
router.register('products',        views.ProductViewSet,       basename='product')
router.register('inventory',       views.InventoryViewSet,     basename='inventory')
router.register('purchase-orders', views.PurchaseOrderViewSet, basename='purchaseorder')
router.register('sales-orders',    views.SalesOrderViewSet,    basename='salesorder')

urlpatterns = [
    path('token/',         TokenObtainPairView.as_view(),        name='token_obtain'),
    path('token/refresh/', TokenRefreshView.as_view(),           name='token_refresh'),
    path('farms/import/',  views.FarmGeoJSONImportView.as_view(), name='farm_geojson_import'),
    path('',               include(router.urls)),
]
