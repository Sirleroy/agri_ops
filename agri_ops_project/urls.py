from apps.dashboard.landing import LandingView
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from agri_ops_project.health import health_check

urlpatterns = [
    path('', LandingView.as_view(), name='landing'),
    path('health/', health_check, name='health'),
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.api.urls')),
    path('reports/', include('apps.reports.urls', namespace='reports')),

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
