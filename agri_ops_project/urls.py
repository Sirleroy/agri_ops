from apps.dashboard.landing import LandingView
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from agri_ops_project.health import health_check
from apps.sales_orders.batch_views import PublicTraceView
from apps.dashboard.access_views import RequestAccessView


def _legal(t):
    return TemplateView.as_view(template_name=f'legal/{t}.html')

legal_urls = ([
    path('terms/',    _legal('terms'),   name='terms'),
    path('privacy/',  _legal('privacy'), name='privacy'),
    path('dpa/',      _legal('dpa'),     name='dpa'),
    path('cookies/',  _legal('cookies'), name='cookies'),
    path('aup/',      _legal('aup'),     name='aup'),
], 'legal')

urlpatterns = [
    path('', include('ops_dashboard.urls')),
    path('', LandingView.as_view(), name='landing'),
    path('health/', health_check, name='health'),
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.api.urls')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
    path('trace/<uuid:token>/', PublicTraceView.as_view(), name='public_trace'),
    path('request-access/', RequestAccessView.as_view(), name='request_access'),
    path('legal/', include(legal_urls)),

    # Authentication
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),

    # Set password — new account welcome email link
    path('set-password/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/set_password.html',
             post_reset_login=True,
             post_reset_login_backend='django.contrib.auth.backends.ModelBackend',
             success_url='/dashboard/',
         ),
         name='password_set'),

    # Password reset — forgot password flow
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.txt',
             subject_template_name='registration/password_reset_subject.txt',
             success_url='/password-reset/done/',
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html',
         ),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/set_password.html',
             post_reset_login=True,
             post_reset_login_backend='django.contrib.auth.backends.ModelBackend',
             success_url='/reset/done/',
         ),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html',
         ),
         name='password_reset_complete'),

    # Application
    path('admin-panel/', include('apps.admin_panel.urls', namespace='admin_panel')),
    path('', include('apps.dashboard.urls', namespace='dashboard')),
    path('inventory/', include('apps.inventory.urls', namespace='inventory')),
    path('products/', include('apps.products.urls', namespace='products')),
    path('suppliers/', include('apps.suppliers.urls', namespace='suppliers')),
    path('purchase-orders/', include('apps.purchase_orders.urls', namespace='purchase_orders')),
    path('sales-orders/', include('apps.sales_orders.urls', namespace='sales_orders')),
    path('companies/', include('apps.companies.urls', namespace='companies')),
    path('users/', include('apps.users.urls', namespace='users')),
    path('audit/', include('apps.audit.urls', namespace='audit')),
]
