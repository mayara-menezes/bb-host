from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('vps/checkout', views.vps_checkout, name='vps_checkout'),
    path('vps/review', views.vps_review, name='vps_review'),
    path('account/vps/<int:pk>', views.vps_detail, name='vps_detail'),
    path('dedicated/<slug:slug>/configure', views.dedicated_configure, name='dedicated_configure'),
    path('account/dedicated/<int:pk>', views.dedicated_detail, name='dedicated_detail'),
    path('colocation/start', views.colocation_start, name='colocation_start'),
    path('account/colocation/new', views.colocation_new, name='colocation_new'),
    path('account/colocation/<int:pk>', views.colocation_detail, name='colocation_detail'),
    path('mitigation/quote', views.mitigation_quote, name='mitigation_quote'),
]
