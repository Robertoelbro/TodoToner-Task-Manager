from django.contrib.auth import views as auth_views
from django.urls import path
from accounts.views import register, users_manage, not_found, user_deletion
from tasks import views
from accounts import views as account_views
from accounts import google_login

urlpatterns = [
    path('primer-ingreso/', account_views.complete_profile, name='complete-profile'),
    path('usuarios/nuevo/', account_views.user_create, name='user-create'),
    path('tareas/<int:parent_pk>/subtareas/nueva/', views.task_create, name='subtask-create'),
    path('tareas/<int:pk>/espectadores/', views.task_audience, name='task-audience'),
    path('perfil/contrasena/', account_views.password_change, name='password-change'),
    path('usuarios/<int:pk>/restablecer-contrasena/', account_views.password_reset_by_management, name='user-password-reset'),
    path('perfil/', account_views.profile, name='profile'),
    path('metas/nueva/', views.monthly_goal_create, name='monthly-goal-create'),
    path('hora-servidor/', views.server_time, name='server-time'),
    path('usuarios/<int:pk>/eliminar/', user_deletion, name='user-delete'),
    path('usuarios/<int:pk>/cancelar-eliminacion/', user_deletion, {'cancel': True}, name='user-delete-cancel'),
    path('usuarios/<int:pk>/eliminar-ahora/', user_deletion, {'immediate': True}, name='user-delete-now'),
    path('usuarios/', users_manage, name='users-manage'),
    path('usuarios/<int:pk>/', users_manage, name='user-edit'),
    path('usuarios/<int:pk>/acceso-correo/', account_views.email_access, name='user-email-access'),
    path('login/', google_login.PlatformLoginView.as_view(), name='login'),
    path('login/google/', google_login.start, name='google-login'),
    path('login/google/callback/', google_login.callback, name='google-callback'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('registro/', register, name='register'),
    path('', views.task_list, name='task-list'),
    path('historial/', views.task_history, name='task-history'),
    path('tareas/<int:pk>/ocultar/', views.task_hide, name='task-hide'),
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
