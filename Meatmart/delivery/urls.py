from django.urls import path
from . import views

app_name = 'delivery'

urlpatterns = [
    path('login/', views.delivery_login, name='login'),
    path('register/', views.delivery_register, name='register'),
    path('', views.dashboard, name='dashboard'),
    path('orders/', views.orders, name='orders'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('orders/<int:order_id>/accept/', views.accept_order, name='accept_order'),
    path('orders/<int:order_id>/reject/', views.reject_order, name='reject_order'),
    path('orders/<int:order_id>/update-status/', views.update_delivery_status, name='update_status'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('update-availability/', views.update_availability, name='update_availability'),
    path('history/', views.history, name='history'),
    path('earnings/', views.earnings, name='earnings'),
    path('profile/', views.profile, name='profile'),
    path('settings/', views.settings, name='settings'),
]
