from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.InventoryListView.as_view(), name='list'),
    path('<int:pk>/', views.InventoryDetailView.as_view(), name='detail'),
    path('new/', views.InventoryCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', views.InventoryUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.InventoryDeleteView.as_view(), name='delete'),
    path('<int:pk>/adjust/', views.InventoryAdjustView.as_view(), name='adjust'),
]
