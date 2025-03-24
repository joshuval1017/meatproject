"""
URL configuration for meatmart project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin_dashboard/', include('admin_dashboard.urls', namespace='admin_dashboard')),  # Custom admin dashboard
    path('django-admin/', admin.site.urls),  # Default Django admin (moved to different URL)
    path('accounts/', include('allauth.urls')),  # Django-allauth URLs (including signup)
    path('profile/', include('accounts.urls')),  # Custom profile URLs
    path('products/', include('products.urls')),  # Product URLs
    path('orders/', include('orders.urls')),  # Orders URLs
    path('cart/', include('cart.urls')),  # Cart URLs
    path('seller/', include('seller.urls')),  # Seller URLs
    path('buyer/', include('buyer.urls')),  # Buyer URLs
    path('delivery/', include('delivery.urls', namespace='delivery')),  # Delivery URLs
    path('pages/', include('pages.urls')),  # Pages URLs
    path('', include('shop.urls')),  # Include shop URLs at root path
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
