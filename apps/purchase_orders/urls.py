from django.urls import path
from . import views

app_name = 'purchase_orders'

urlpatterns = [
    path('', views.PurchaseOrderListView.as_view(), name='list'),
    path('<int:pk>/', views.PurchaseOrderDetailView.as_view(), name='detail'),
    path('new/', views.PurchaseOrderCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', views.PurchaseOrderUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.PurchaseOrderDeleteView.as_view(), name='delete'),
    path('<int:pk>/mark-received/', views.PurchaseOrderMarkReceivedView.as_view(), name='mark_received'),
]
