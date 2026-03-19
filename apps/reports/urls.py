from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('',      views.ReportsLandingView.as_view(), name='index'),
    path('eudr/', views.EUDRReportView.as_view(),     name='eudr'),
    path('ops/',  views.OpsReportView.as_view(),      name='ops'),
]
