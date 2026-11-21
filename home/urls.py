from django.urls import path

from . import views

app_name = 'home'

urlpatterns = [
    path('', views.index, name='index'),
    path('vps', views.vps, name='vps'),
    path('dedicated', views.dedicated, name='dedicated'),
    path('dedicated/<int:server_id>/notify-me', views.notify_me, name='notify_me'),
    path('colocation', views.colocation, name='colocation'),
    path('mitigation', views.mitigation, name='mitigation'),
    path('about', views.about, name='about'),
    path('contact', views.contact, name='contact'),
]
