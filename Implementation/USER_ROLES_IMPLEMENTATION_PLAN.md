# User Roles and Security Implementation Plan

## Overview

This plan implements a comprehensive Role-Based Access Control (RBAC) system for the attendance application, ensuring proper security and access control for different user types.

## Current State Analysis

### Existing Authentication
- ✅ Django's built-in `User` model
- ✅ `@login_required` decorators on all views
- ✅ Session-based authentication
- ✅ Login/logout functionality
- ❌ No role-based access control
- ❌ No permission-based restrictions

### Current Access Patterns
- All authenticated users have full access to all features
- No differentiation between security staff, attendance managers, and administrators
- Clock in/out functions accessible to all users
- Reports accessible to all users

## Proposed Role Structure

### 1. **Security Role** (Limited Access)
**Purpose**: Security personnel who only need to clock employees in/out

**Access Rights**:
- ✅ Clock in/out functions only
- ✅ View employee status (clocked in/out)
- ✅ View employee list with status
- ❌ No attendance record management
- ❌ No reports access
- ❌ No employee management
- ❌ No system administration

**URLs Accessible**:
- `/common/main_security/` - Main clock dashboard
- `/common/main_security/flip_clocked_in_status/<id>/` - Clock in/out action
- `/common/employee_events/<id>/` - View employee events (read-only)

### 2. **Attendance Management Role** (Moderate Access)
**Purpose**: Staff responsible for managing attendance records and data entry

**Access Rights**:
- ✅ All attendance record management
- ✅ Progressive entry functionality
- ✅ Historical entry functionality
- ✅ Attendance analytics and reports
- ✅ Employee attendance history
- ❌ No clock in/out functions
- ❌ No employee management
- ❌ No system administration

**URLs Accessible**:
- `/common/attendance/` - Attendance list
- `/common/attendance/analytics/` - Analytics
- `/common/attendance/progressive_entry/` - Progressive entry
- `/common/attendance/historical_progressive_entry/` - Historical entry
- `/common/reports/` - All reports
- `/common/reports/comprehensive/` - Comprehensive reports
- `/common/reports/employee_history/` - Employee history
- `/common/reports/period_summary/` - Period summary

### 3. **Reporting Role** (Read-Only Access)
**Purpose**: Users who need to view reports and analytics but not modify data

**Access Rights**:
- ✅ View all reports and analytics
- ✅ Export data (CSV downloads)
- ✅ View attendance records (read-only)
- ❌ No data modification
- ❌ No clock in/out functions
- ❌ No employee management
- ❌ No system administration

**URLs Accessible**:
- `/common/attendance/` - Attendance list (read-only)
- `/common/attendance/analytics/` - Analytics
- `/common/reports/` - All reports
- `/common/reports/comprehensive/` - Comprehensive reports
- `/common/reports/employee_history/` - Employee history
- `/common/reports/period_summary/` - Period summary

### 4. **Admin Role** (Full Access)
**Purpose**: System administrators with unrestricted access

**Access Rights**:
- ✅ Full system access
- ✅ All functions and features
- ✅ Employee management
- ✅ System administration
- ✅ Database management
- ✅ User management

**URLs Accessible**:
- All URLs in the system
- Django admin interface (`/admin/`)

## Implementation Plan

### Phase 1: Core Role System Setup

#### 1.1 Create Role Model
```python
# common/models.py
class UserRole(models.Model):
    """User roles for access control"""
    ROLE_CHOICES = [
        ('security', 'Security'),
        ('attendance', 'Attendance Management'),
        ('reporting', 'Reporting'),
        ('admin', 'Administrator'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Role"
        verbose_name_plural = "User Roles"
```

#### 1.2 Create Permission Decorators
```python
# common/decorators.py
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

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
                    return redirect('main_security')
            except UserRole.DoesNotExist:
                messages.error(request, "No role assigned. Please contact administrator.")
                return redirect('main_security')
        return _wrapped_view
    return decorator

# Specific role decorators
def security_required(view_func):
    return role_required(['security', 'attendance', 'admin'])(view_func)

def attendance_required(view_func):
    return role_required(['attendance', 'admin'])(view_func)

def reporting_required(view_func):
    return role_required(['reporting', 'attendance', 'admin'])(view_func)

def admin_required(view_func):
    return role_required(['admin'])(view_func)
```

#### 1.3 Update User Model Integration
```python
# common/models.py
from django.contrib.auth.models import User

# Add method to User model
def User.get_role(self):
    """Get user's role"""
    try:
        return self.userrole.role
    except UserRole.DoesNotExist:
        return None

def User.has_role(self, role):
    """Check if user has specific role"""
    return self.get_role() == role

def User.has_any_role(self, roles):
    """Check if user has any of the specified roles"""
    user_role = self.get_role()
    return user_role in roles if user_role else False
```

### Phase 2: View Protection Implementation

#### 2.1 Clock In/Out Views (Security Only)
```python
# common/views.py
@security_required
def main_security(request):
    """Main security dashboard - Security role only"""
    # Existing implementation

@security_required
def main_security_clocked_in_status_flip(request, id):
    """Clock in/out action - Security role only"""
    # Existing implementation

@security_required
def employee_events(request, id):
    """Employee events view - Security role only (read-only)"""
    # Existing implementation
```

#### 2.2 Attendance Management Views
```python
# common/views.py
@attendance_required
def attendance_list(request):
    """Attendance list - Attendance Management role only"""
    # Existing implementation

@attendance_required
def progressive_entry(request):
    """Progressive entry - Attendance Management role only"""
    # Existing implementation

@attendance_required
def historical_progressive_entry(request):
    """Historical entry - Attendance Management role only"""
    # Existing implementation

@attendance_required
def attendance_edit(request, record_id):
    """Edit attendance record - Attendance Management role only"""
    # Existing implementation

@attendance_required
def attendance_delete(request, record_id):
    """Delete attendance record - Attendance Management role only"""
    # Existing implementation
```

#### 2.3 Reporting Views
```python
# common/views.py
@reporting_required
def reports_dashboard(request):
    """Reports dashboard - Reporting role and above"""
    # Existing implementation

@reporting_required
def comprehensive_reports(request):
    """Comprehensive reports - Reporting role and above"""
    # Existing implementation

@reporting_required
def attendance_analytics(request):
    """Attendance analytics - Reporting role and above"""
    # Existing implementation
```

#### 2.4 Admin Views
```python
# common/views.py
@admin_required
def performance_dashboard(request):
    """Performance dashboard - Admin only"""
    # Existing implementation

# API views with admin protection
class SingleEventView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly, AdminPermission]
    # Existing implementation
```

### Phase 3: Template and UI Updates

#### 3.1 Navigation Menu Updates
```html
<!-- common/templates/base.html -->
<nav>
    {% if user.is_authenticated %}
        {% if user.has_any_role|in_list:"security,attendance,admin" %}
            <a href="{% url 'main_security' %}">Clock In/Out</a>
        {% endif %}
        
        {% if user.has_any_role|in_list:"attendance,admin" %}
            <a href="{% url 'attendance_list' %}">Attendance</a>
            <a href="{% url 'progressive_entry' %}">Progressive Entry</a>
        {% endif %}
        
        {% if user.has_any_role|in_list:"reporting,attendance,admin" %}
            <a href="{% url 'reports_dashboard' %}">Reports</a>
        {% endif %}
        
        {% if user.has_role|in_list:"admin" %}
            <a href="{% url 'admin:index' %}">Admin</a>
        {% endif %}
    {% endif %}
</nav>
```

#### 3.2 Role-Based Content Display
```html
<!-- common/templates/main_security.html -->
{% if user.has_any_role|in_list:"attendance,admin" %}
    <div class="admin-actions">
        <a href="{% url 'attendance_list' %}" class="btn">Manage Attendance</a>
        <a href="{% url 'reports_dashboard' %}" class="btn">View Reports</a>
    </div>
{% endif %}
```

### Phase 4: Permission Classes for API

#### 4.1 Custom Permission Classes
```python
# common/permissions.py
from rest_framework import permissions

class SecurityPermission(permissions.BasePermission):
    """Allow access to security role and above"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.has_any_role(['security', 'attendance', 'admin'])

class AttendancePermission(permissions.BasePermission):
    """Allow access to attendance role and above"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.has_any_role(['attendance', 'admin'])

class ReportingPermission(permissions.BasePermission):
    """Allow access to reporting role and above"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.has_any_role(['reporting', 'attendance', 'admin'])

class AdminPermission(permissions.BasePermission):
    """Allow access to admin role only"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.has_role('admin')
```

#### 4.2 Update API Views
```python
# common/views.py
from .permissions import SecurityPermission, AttendancePermission, ReportingPermission, AdminPermission

class SingleEventView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [SecurityPermission]  # Security can view events
    # Existing implementation

class SingleEmployeeView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [AdminPermission]  # Only admin can manage employees
    # Existing implementation
```

### Phase 5: User Management Interface

#### 5.1 Admin Interface for Role Management
```python
# common/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserRole

class UserRoleInline(admin.StackedInline):
    model = UserRole
    can_delete = False
    verbose_name_plural = 'User Role'

class CustomUserAdmin(UserAdmin):
    inlines = (UserRoleInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff')
    list_filter = ('userrole__role', 'is_staff', 'is_superuser')
    
    def get_role(self, obj):
        return obj.get_role()
    get_role.short_description = 'Role'

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
```

#### 5.2 Role Assignment Management
```python
# common/management/commands/assign_role.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from common.models import UserRole

class Command(BaseCommand):
    help = 'Assign role to user'
    
    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
        parser.add_argument('role', type=str, choices=['security', 'attendance', 'reporting', 'admin'])
    
    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options['username'])
            role, created = UserRole.objects.get_or_create(user=user)
            role.role = options['role']
            role.save()
            
            if created:
                self.stdout.write(f"Created role '{options['role']}' for user '{options['username']}'")
            else:
                self.stdout.write(f"Updated role to '{options['role']}' for user '{options['username']}'")
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User '{options['username']}' does not exist"))
```

### Phase 6: Testing and Validation

#### 6.1 Unit Tests
```python
# common/tests.py
class UserRoleTestCase(TestCase):
    def setUp(self):
        # Create test users with different roles
        self.security_user = User.objects.create_user('security', 'security@test.com', 'password')
        self.attendance_user = User.objects.create_user('attendance', 'attendance@test.com', 'password')
        self.reporting_user = User.objects.create_user('reporting', 'reporting@test.com', 'password')
        self.admin_user = User.objects.create_user('admin', 'admin@test.com', 'password')
        
        # Assign roles
        UserRole.objects.create(user=self.security_user, role='security')
        UserRole.objects.create(user=self.attendance_user, role='attendance')
        UserRole.objects.create(user=self.reporting_user, role='reporting')
        UserRole.objects.create(user=self.admin_user, role='admin')
    
    def test_security_access(self):
        """Test security role access"""
        client = Client()
        client.login(username='security', password='password')
        
        # Should access clock functions
        response = client.get(reverse('main_security'))
        self.assertEqual(response.status_code, 200)
        
        # Should not access attendance management
        response = client.get(reverse('attendance_list'))
        self.assertEqual(response.status_code, 302)  # Redirected
    
    def test_attendance_access(self):
        """Test attendance management role access"""
        client = Client()
        client.login(username='attendance', password='password')
        
        # Should access attendance functions
        response = client.get(reverse('attendance_list'))
        self.assertEqual(response.status_code, 200)
        
        # Should access clock functions
        response = client.get(reverse('main_security'))
        self.assertEqual(response.status_code, 200)
```

#### 6.2 Integration Tests
```python
# common/tests.py
class RoleIntegrationTestCase(TestCase):
    def test_role_based_navigation(self):
        """Test that navigation shows correct items based on role"""
        # Test for each role type
        pass
    
    def test_api_permissions(self):
        """Test API endpoint permissions"""
        # Test API access for different roles
        pass
```

### Phase 7: Migration and Deployment

#### 7.1 Database Migration
```python
# common/migrations/XXXX_create_user_roles.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('common', 'previous_migration'),
    ]
    
    operations = [
        migrations.CreateModel(
            name='UserRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('security', 'Security'), ('attendance', 'Attendance Management'), ('reporting', 'Reporting'), ('admin', 'Administrator')], max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='auth.user')),
            ],
            options={
                'verbose_name': 'User Role',
                'verbose_name_plural': 'User Roles',
            },
        ),
    ]
```

#### 7.2 Default Role Assignment
```python
# common/migrations/XXXX_assign_default_roles.py
from django.db import migrations

def assign_default_roles(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserRole = apps.get_model('common', 'UserRole')
    
    # Assign admin role to superusers
    for user in User.objects.filter(is_superuser=True):
        UserRole.objects.get_or_create(user=user, defaults={'role': 'admin'})
    
    # Assign security role to regular users (default)
    for user in User.objects.filter(is_superuser=False):
        UserRole.objects.get_or_create(user=user, defaults={'role': 'security'})

class Migration(migrations.Migration):
    dependencies = [
        ('common', 'XXXX_create_user_roles'),
    ]
    
    operations = [
        migrations.RunPython(assign_default_roles),
    ]
```

## Implementation Timeline

### Week 1: Core Infrastructure
- [ ] Create UserRole model
- [ ] Implement role decorators
- [ ] Create permission classes
- [ ] Update User model integration

### Week 2: View Protection
- [ ] Apply role decorators to all views
- [ ] Update API views with permissions
- [ ] Test access control

### Week 3: UI Updates
- [ ] Update navigation menus
- [ ] Implement role-based content display
- [ ] Update templates for role awareness

### Week 4: Testing and Deployment
- [ ] Write comprehensive tests
- [ ] Create migration scripts
- [ ] Deploy and validate

## Security Considerations

### 1. Role Validation
- All role checks must be server-side
- Client-side role hiding is for UX only
- API endpoints must validate roles

### 2. Default Security
- New users default to 'security' role (most restrictive)
- Superusers get 'admin' role automatically
- Role changes require admin privileges

### 3. Audit Trail
- Log role changes
- Track access attempts
- Monitor permission violations

### 4. Session Management
- Clear sessions on role change
- Implement session timeout
- Secure session storage

## Benefits

### 1. Security
- ✅ Restricted access to sensitive functions
- ✅ Clock in/out limited to security staff
- ✅ Attendance data protected from unauthorized access
- ✅ Reports access controlled

### 2. Operational Efficiency
- ✅ Clear role separation
- ✅ Reduced training complexity
- ✅ Focused interfaces per role
- ✅ Reduced error potential

### 3. Compliance
- ✅ Audit trail for access
- ✅ Role-based access control
- ✅ Separation of duties
- ✅ Data protection

### 4. User Experience
- ✅ Simplified interfaces per role
- ✅ Relevant navigation items
- ✅ Clear access feedback
- ✅ Role-appropriate features

## Risk Mitigation

### 1. Backward Compatibility
- Existing users get default 'security' role
- Gradual migration path
- Fallback mechanisms

### 2. Error Handling
- Graceful permission denial
- Clear error messages
- Redirect to appropriate pages

### 3. Testing Strategy
- Comprehensive role testing
- Edge case coverage
- Integration testing
- User acceptance testing

This implementation plan provides a robust, secure, and scalable role-based access control system that meets the specific requirements for the attendance management system. 