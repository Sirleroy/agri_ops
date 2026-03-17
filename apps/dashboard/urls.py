from django.urls import path
from . import views
from .landing import LandingView

app_name = 'dashboard'

urlpatterns = [
    path('', LandingView.as_view(), name='landing'),
    path('dashboard/', views.DashboardView.as_view(), name='index'),
]
