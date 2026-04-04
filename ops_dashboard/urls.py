from django.urls import path
from . import views

urlpatterns = [
    path('ops-access/9f3k/', views.ops_login, name='ops_login'),
    path('ops-access/9f3k/otp-setup/', views.ops_otp_setup, name='ops_otp_setup'),
    path('ops-access/9f3k/otp-verify/', views.ops_otp_verify, name='ops_otp_verify'),
    path('ops-access/9f3k/logout/', views.ops_logout, name='ops_logout'),
    path('ops/', views.ops_dashboard, name='ops_dashboard'),
    path('ops/tenants/', views.ops_tenants, name='ops_tenants'),
    path('ops/tenants/<int:pk>/', views.ops_tenant_detail, name='ops_tenant_detail'),
    path('ops/security/', views.ops_security, name='ops_security'),
    path('ops/metrics/', views.ops_metrics, name='ops_metrics'),
    path('ops/health/', views.ops_health, name='ops_health'),
]
