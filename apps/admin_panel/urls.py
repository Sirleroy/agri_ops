from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('', views.admin_overview, name='overview'),
    path('users/', views.admin_users, name='users'),
    path('users/<int:user_id>/role/', views.admin_change_role, name='change_role'),
    path('users/<int:user_id>/deactivate/', views.admin_deactivate_user, name='deactivate_user'),
    path('users/<int:user_id>/edit/', views.admin_edit_user, name='edit_user'),
    path('users/invite/', views.admin_invite_user, name='invite_user'),
    path('company/', views.admin_company_settings, name='company_settings'),
    path('audit/', views.admin_audit_log, name='audit_log'),
    path('roles/', views.admin_roles, name='roles'),
]
