from django.shortcuts import redirect
from django.urls import resolve, reverse

class RoleBasedAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Allow access to static and media files
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)

        # Allow access to authentication URLs
        if request.path.startswith('/accounts/'):
            return self.get_response(request)

        # Check if user is authenticated
        if request.user.is_authenticated:
            # Get the current URL's namespace
            current_url = resolve(request.path)
            namespace = current_url.namespace.split(':')[0] if current_url.namespace else None

            # Admin users should only access admin_dashboard
            if request.user.role == 'ADMIN':
                if namespace and namespace != 'admin_dashboard':
                    return redirect('admin_dashboard:dashboard')

            # Seller users should only access seller dashboard
            elif request.user.role == 'SELLER':
                if namespace and namespace != 'seller':
                    return redirect('seller:dashboard')

            # Buyers can access everything except admin and seller areas
            elif request.user.role == 'BUYER':
                if namespace in ['admin_dashboard', 'seller']:
                    return redirect('shop:home')

        return self.get_response(request)
