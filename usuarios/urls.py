from django.urls import path
from . import views
from django.conf.urls import handler404
from . import api_views
handler404 = 'usuarios.views.error_404'

urlpatterns = [
   path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('mregister/', views.mregister, name='mregister'),
    path('login/', views.login, name='login'),
    path('mlogin/', views.mlogin, name='mlogin'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('edit_user/', views.edit_user, name='edit_user'),
    path('logout/', views.logout, name='logout'),
    path('deactivate_user/', views.deactivate_user, name='deactivate_user'),
    path('reactivate_user/', views.reactivate_user, name='reactivate_user'),
    path('update_user/', views.update_user, name='update_user'),

    # Rutas para escritorios (admin)
    path('admin/escritorios/', views.admin_escritorios, name='admin_escritorios'),
    path('admin/escritorios/crear/', views.crear_escritorio, name='crear_escritorio'),
    path('admin/escritorios/desactivar/', views.desactivar_escritorio, name='desactivar_escritorio'),
    path('admin/escritorios/reactivar/', views.reactivar_escritorio, name='reactivar_escritorio'),

    # Rutas para escritorios (usuario)
    path('escritorio/vincular/', views.vincular_escritorio, name='vincular_escritorio'),
    path('escritorio/asociar-serie/', views.asociar_por_serie, name='asociar_por_serie'),
    path('escritorio/desasociar/', views.desasociar_escritorio, name='desasociar_escritorio'),
    path('mis-escritorios/', views.mis_escritorios, name='mis_escritorios'),
    path('escritorio/editar/', views.editar_escritorio, name='editar_escritorio'),
     # Nuevas rutas para la API del ESP32
    path('api/timer/register/', api_views.register_timer, name='api_register_timer'),
    path('api/timer/user/<str:username>/', api_views.get_user_timers, name='api_get_user_timers'),
    path('api/timer/user/<str:username>/<str:modo>/', api_views.get_user_timers, name='api_get_user_timers_by_mode'),

    # Ruta para la vista de temporizadores
    path('mis-timers/', views.mis_timers, name='mis_timers'),
    path('mis-timers/<str:modo>/', views.mis_timers, name='mis_timers_by_mode'),
    path('estadisticas/', views.estadisticas, name='estadisticas'),


]