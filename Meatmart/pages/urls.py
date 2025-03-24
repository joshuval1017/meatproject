from django.urls import path
from . import views

app_name = 'pages'

urlpatterns = [
    path('terms/', views.terms_view, name='terms'),
    path('privacy/', views.privacy_view, name='privacy'),
]
