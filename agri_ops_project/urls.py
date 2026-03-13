from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.dashboard.urls', namespace='dashboard')),
    path('inventory/', include('apps.inventory.urls', namespace='inventory')),
    path('products/', include('apps.products.urls', namespace='products')),
    path('suppliers/', include('apps.suppliers.urls', namespace='suppliers')),
    path('purchase-orders/', include('apps.purchase_orders.urls', namespace='purchase_orders')),
    path('sales-orders/', include('apps.sales_orders.urls', namespace='sales_orders')),
    path('companies/', include('apps.companies.urls', namespace='companies')),
    path('users/', include('apps.users.urls', namespace='users')),
]
