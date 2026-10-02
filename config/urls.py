from django.contrib.auth import views as auth_views
from django.urls import path
from accounts.views import register, users_manage, not_found, user_deletion
from tasks import views

urlpatterns = [
    path('hora-servidor/', views.server_time, name='server-time'),
    path('usuarios/<int:pk>/eliminar/', user_deletion, name='user-delete'),
    path('usuarios/<int:pk>/cancelar-eliminacion/', user_deletion, {'cancel': True}, name='user-delete-cancel'),
    path('usuarios/', users_manage, name='users-manage'),
    path('usuarios/<int:pk>/', users_manage, name='user-edit'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('registro/', register, name='register'),
    path('', views.task_list, name='task-list'),
    path('historial/', views.task_history, name='task-history'),
    path('tareas/<int:pk>/ocultar/', views.task_hide, name='task-hide'),
    path('tareas/<int:pk>/eliminar/', views.task_delete, name='task-delete'),
    path('tareas/nueva/', views.task_create, name='task-create'),
    path('tareas/<int:pk>/', views.task_detail, name='task-detail'),
    path('tareas/<int:pk>/responsables/', views.task_reassign, name='task-reassign'),
    path('tareas/<int:pk>/seguimiento/', views.task_tracking, name='task-tracking'),
    path('alertas/', views.task_alerts, name='task-alerts'),
    path('tv/', views.tv_dashboard, name='tv-dashboard'),
    path('gantt/', views.gantt_view, name='gantt'),
    path('dashboard/', views.dashboard, name='dashboard'),
]


handler404 = not_found
