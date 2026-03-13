from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Authentication
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),

    # Application
    path('', include('apps.dashboard.urls', namespace='dashboard')),
    path('inventory/', include('apps.inventory.urls', namespace='inventory')),
    path('products/', include('apps.products.urls', namespace='products')),
    path('suppliers/', include('apps.suppliers.urls', namespace='suppliers')),
    path('purchase-orders/', include('apps.purchase_orders.urls', namespace='purchase_orders')),
    path('sales-orders/', include('apps.sales_orders.urls', namespace='sales_orders')),
    path('companies/', include('apps.companies.urls', namespace='companies')),
    path('users/', include('apps.users.urls', namespace='users')),
]
