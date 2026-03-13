from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('', views.UserListView.as_view(), name='list'),
    path('<int:pk>/', views.UserDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.UserUpdateView.as_view(), name='update'),
    path('<int:pk>/role/', views.UserSystemRoleUpdateView.as_view(), name='role'),
    path('<int:pk>/delete/', views.UserDeleteView.as_view(), name='delete'),
]
