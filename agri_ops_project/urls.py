from apps.dashboard.landing import LandingView
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from agri_ops_project.health import health_check
from apps.sales_orders.batch_views import PublicTraceView
from apps.dashboard.access_views import RequestAccessView


# TEMPORARY — Sentry test, remove after confirming errors appear in Sentry
def trigger_sentry_test(request):
    division_by_zero = 1 / 0

urlpatterns = [
    path('', include('ops_dashboard.urls')),
    path('', LandingView.as_view(), name='landing'),
    path('health/', health_check, name='health'),
    path('sentry-test/', trigger_sentry_test),  # TEMPORARY
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.api.urls')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
    path('trace/<uuid:token>/', PublicTraceView.as_view(), name='public_trace'),
    path('request-access/', RequestAccessView.as_view(), name='request_access'),

    # Authentication
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('set-password/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/set_password.html',
             post_reset_login=True,
         ),
         name='password_set'),

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
