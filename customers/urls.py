from django.urls import path

from . import views

app_name = 'customers'

urlpatterns = [
    path('login', views.LoginView.as_view(), name='login'),
    path('logout', views.LogoutView.as_view(), name='logout'),
    path('signup', views.signup, name='signup'),
    path('account', views.dashboard, name='dashboard'),
    path('account/profile', views.profile, name='profile'),
    path('account/password', views.PasswordChangeView.as_view(), name='password'),
    path('account/services', views.services, name='services'),
    path('account/invoices', views.invoices, name='invoices'),
    path('account/invoices/<int:pk>', views.invoice_detail, name='invoice'),
    path('account/credit', views.credit, name='credit'),
    path('account/support', views.tickets, name='tickets'),
    path('account/support/new', views.ticket_new, name='ticket_new'),
    path('account/support/<int:pk>', views.ticket_detail, name='ticket'),
]
