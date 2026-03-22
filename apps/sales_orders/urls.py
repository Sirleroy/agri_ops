from django.urls import path
from . import views
from . import batch_views

app_name = 'sales_orders'

urlpatterns = [
    # Sales orders
    path('', views.SalesOrderListView.as_view(), name='list'),
    path('new/', views.SalesOrderCreateView.as_view(), name='create'),
    path('<int:pk>/', views.SalesOrderDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.SalesOrderUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.SalesOrderDeleteView.as_view(), name='delete'),

    # Batches
    path('batches/', batch_views.BatchListView.as_view(), name='batch_list'),
    path('batches/new/', batch_views.BatchCreateView.as_view(), name='batch_create'),
    path('batches/<int:pk>/', batch_views.BatchDetailView.as_view(), name='batch_detail'),
    path('batches/<int:pk>/edit/', batch_views.BatchUpdateView.as_view(), name='batch_update'),
    path('batches/<int:pk>/certificate/', batch_views.BatchCertificateView.as_view(), name='batch_certificate'),

    # Phytosanitary certificates
    path('batches/<int:batch_pk>/phytosanitary/add/', batch_views.PhytosanitaryCertCreateView.as_view(), name='phytosanitary_create'),
    path('batches/phytosanitary/<int:pk>/edit/', batch_views.PhytosanitaryCertUpdateView.as_view(), name='phytosanitary_update'),
    path('batches/phytosanitary/<int:pk>/delete/', batch_views.PhytosanitaryCertDeleteView.as_view(), name='phytosanitary_delete'),

    # Quality tests
    path('batches/<int:batch_pk>/quality/add/', batch_views.BatchQualityTestCreateView.as_view(), name='quality_create'),
    path('batches/quality/<int:pk>/edit/', batch_views.BatchQualityTestUpdateView.as_view(), name='quality_update'),
    path('batches/quality/<int:pk>/delete/', batch_views.BatchQualityTestDeleteView.as_view(), name='quality_delete'),
]
