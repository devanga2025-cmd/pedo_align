from django.shortcuts import redirect
from django.urls import reverse

class AutoLoginDashboardRedirectMiddleware:
    """
    Middleware that guarantees:
    Once a user (doctor or patient) has logged in, they are NEVER shown a login page again!
    Any attempt to visit root '/', '/login/', '/patient/login/', or auth routes
    will directly and seamlessly redirect them to their active dashboard.
    """
    AUTH_EXEMPT_PATHS = {
        '/',
        '/login/',
        '/patient/login/',
        '/register/',
        '/patient/register/',
        '/join/',
        '/forgot-password/',
        '/patient/forgot-password/',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        
        # Only check auth pages if the user is authenticated
        if request.user.is_authenticated and (path in self.AUTH_EXEMPT_PATHS or path.rstrip('/') in self.AUTH_EXEMPT_PATHS):
            # If Doctor -> directly open doctor dashboard
            if hasattr(request.user, 'doctor_profile'):
                return redirect('doctor:dashboard')
            
            # If Patient -> directly open patient dashboard
            if hasattr(request.user, 'patient_profile'):
                return redirect('patient:dashboard')
            
            # If staff/superuser -> doctor dashboard
            if request.user.is_staff or request.user.is_superuser:
                return redirect('doctor:dashboard')
            
            # General authenticated user -> patient dashboard
            return redirect('patient:dashboard')

        return self.get_response(request)

