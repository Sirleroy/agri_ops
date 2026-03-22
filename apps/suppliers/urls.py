from django.urls import path
from . import views

app_name = 'suppliers'

urlpatterns = [
    # Suppliers
    path('', views.SupplierListView.as_view(), name='list'),
    path('new/', views.SupplierCreateView.as_view(), name='create'),
    path('<int:pk>/', views.SupplierDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.SupplierUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.SupplierDeleteView.as_view(), name='delete'),

    # Farms
    path('farms/', views.FarmListView.as_view(), name='farm_list'),
    path('farms/new/', views.FarmCreateView.as_view(), name='farm_create'),
    path('farms/<int:pk>/', views.FarmDetailView.as_view(), name='farm_detail'),
    path('farms/<int:pk>/edit/', views.FarmUpdateView.as_view(), name='farm_update'),
    path('farms/<int:pk>/delete/', views.FarmDeleteView.as_view(), name='farm_delete'),

    # Farm certifications
    path('farms/<int:farm_pk>/certifications/add/', views.FarmCertificationCreateView.as_view(), name='farm_cert_create'),
    path('farms/certifications/<int:pk>/delete/', views.FarmCertificationDeleteView.as_view(), name='farm_cert_delete'),
]
