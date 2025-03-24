from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Profile URLs
    path('profile/', views.profile_view, name='profile'),
    path('address/add/', views.add_address, name='add_address'),
   
]
