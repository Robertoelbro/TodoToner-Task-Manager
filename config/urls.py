from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from accounts.views import register
from tasks import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('registro/', register, name='register'),
    path('', views.task_list, name='task-list'),
    path('tareas/nueva/', views.task_create, name='task-create'),
    path('tareas/<int:pk>/', views.task_detail, name='task-detail'),
    path('tareas/<int:pk>/responsables/', views.task_reassign, name='task-reassign'),
    path('dashboard/', views.dashboard, name='dashboard'),
]

