from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import UserRole


def role_required(allowed_roles):
    """Decorator to check user role"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            try:
                user_role = request.user.userrole.role
                if user_role in allowed_roles:
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, f"Access denied. Your role '{user_role}' does not have permission to access this feature.")
                    # Redirect to appropriate page based on user role
                    if user_role == 'reporting':
                        return redirect('comprehensive_reports')
                    elif user_role == 'attendance':
                        return redirect('attendance_list')
                    elif user_role == 'admin':
                        return redirect('main_security')
                    else:
                        return redirect('main_security')
            except UserRole.DoesNotExist:
                messages.error(request, "No role assigned. Please contact administrator.")
                return redirect('main_security')
        return _wrapped_view
    return decorator


# Specific role decorators
def security_required(view_func):
    """Decorator for security role and above"""
    return role_required(['security', 'attendance', 'admin'])(view_func)


def attendance_required(view_func):
    """Decorator for attendance management role and above"""
    return role_required(['attendance', 'admin'])(view_func)


def reporting_required(view_func):
    """Decorator for reporting role and above"""
    return role_required(['reporting', 'attendance', 'admin'])(view_func)


def admin_required(view_func):
    """Decorator for admin role only"""
    return role_required(['admin'])(view_func) 