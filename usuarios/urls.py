from django.urls import path
from . import views
from django.conf.urls import handler404
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
    path('user_dashboard/', views.user_dashboard, name='user_dashboard'),
]