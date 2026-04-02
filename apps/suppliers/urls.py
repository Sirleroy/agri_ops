from django.urls import path
from . import views

app_name = 'suppliers'

urlpatterns = [
    # Farmers
    path('farmers/', views.FarmerListView.as_view(), name='farmer_list'),
    path('farmers/export/', views.FarmerExportView.as_view(), name='farmer_export'),
    path('farmers/import/', views.FarmerImportView.as_view(), name='farmer_import'),
    path('farmers/import/template/', views.FarmerImportTemplateView.as_view(), name='farmer_import_template'),
    path('farmers/import/errors/', views.FarmerImportErrorsView.as_view(), name='farmer_import_errors'),
    path('farmers/new/', views.FarmerCreateView.as_view(), name='farmer_create'),
    path('farmers/<int:pk>/', views.FarmerDetailView.as_view(), name='farmer_detail'),
    path('farmers/<int:pk>/edit/', views.FarmerUpdateView.as_view(), name='farmer_update'),
    path('farmers/<int:pk>/delete/', views.FarmerDeleteView.as_view(), name='farmer_delete'),

    # Suppliers
    path('', views.SupplierListView.as_view(), name='list'),
    path('new/', views.SupplierCreateView.as_view(), name='create'),
    path('<int:pk>/', views.SupplierDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.SupplierUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.SupplierDeleteView.as_view(), name='delete'),

    # Farms
    path('farms/', views.FarmListView.as_view(), name='farm_list'),
    path('farms/export/', views.FarmExportView.as_view(), name='farm_export'),
    path('farms/new/', views.FarmCreateView.as_view(), name='farm_create'),
    path('farms/<int:pk>/', views.FarmDetailView.as_view(), name='farm_detail'),
    path('farms/<int:pk>/edit/', views.FarmUpdateView.as_view(), name='farm_update'),
    path('farms/<int:pk>/delete/', views.FarmDeleteView.as_view(), name='farm_delete'),

    # Farm certifications
    path('farms/<int:farm_pk>/certifications/add/', views.FarmCertificationCreateView.as_view(), name='farm_cert_create'),
    path('farms/certifications/<int:pk>/delete/', views.FarmCertificationDeleteView.as_view(), name='farm_cert_delete'),
]
