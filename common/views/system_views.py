"""
System and error handling views.
"""
from django.shortcuts import render
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse


# Error handling views migrated from legacy_views.py

def custom_bad_request(request, exception):
    return render(request, "errors/400.html", {"error": str(exception)}, status=400)


def custom_permission_denied(request, exception):
    return render(request, "errors/403.html", {"error": str(exception)}, status=403)


def custom_page_not_found(request, exception):
    return render(request, "errors/404.html", {"path": request.path}, status=404)


def custom_server_error(request):
    return render(request, "errors/500.html", status=500)


def health_check(request):
    """Basic health check endpoint."""
    return render(request, "health_check.html", {"status": "healthy"})


def custom_login(request):
    """Custom login view with role-based redirects."""
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {username}!")
                
                # Role-based redirect logic
                if hasattr(user, 'user_roles') and user.user_roles.exists():
                    role = user.user_roles.first().role
                    if role == 'admin':
                        return redirect('admin:index')
                    elif role == 'reporting':
                        return redirect('reports_dashboard')
                    elif role == 'attendance':
                        return redirect('attendance_list')
                    else:  # security role or default
                        return redirect('main_security')
                else:
                    # Default redirect for users without explicit roles
                    return redirect('main_security')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    
    return render(request, "registration/login.html", {"form": form})


def redirect_based_on_role(user):
    """Redirect user based on their role."""
    if hasattr(user, 'user_roles') and user.user_roles.exists():
        role = user.user_roles.first().role
        if role == 'admin':
            return 'admin:index'
        elif role == 'reporting':
            return 'reports_dashboard'
        elif role == 'attendance':
            return 'attendance_list'
        else:  # security role or default
            return 'main_security'
    else:
        # Default redirect for users without explicit roles
        return 'main_security'