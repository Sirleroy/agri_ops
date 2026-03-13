from django.urls import path
from . import views

app_name = 'sales_orders'

urlpatterns = [
    path('', views.SalesOrderListView.as_view(), name='list'),
    path('<int:pk>/', views.SalesOrderDetailView.as_view(), name='detail'),
    path('new/', views.SalesOrderCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', views.SalesOrderUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.SalesOrderDeleteView.as_view(), name='delete'),
]
