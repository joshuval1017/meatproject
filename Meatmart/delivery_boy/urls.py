from django.urls import path
from . import views

app_name = 'delivery_boy'

urlpatterns = [
    path('orders/', views.my_orders, name='my_orders'),
    path('orders/<int:order_id>/reject/', views.reject_order, name='reject_order'),
]
