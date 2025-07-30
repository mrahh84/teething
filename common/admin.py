from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserRole, Employee, Event, EventType, Location, Card, AttendanceRecord


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


# Register models
admin.site.register(Employee)
admin.site.register(Event)
admin.site.register(EventType)
admin.site.register(Location)
admin.site.register(Card)
admin.site.register(AttendanceRecord)
admin.site.register(UserRole)

# Register custom User admin
from django.contrib.auth.models import User
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
