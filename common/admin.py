from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    UserRole, Employee, Event, EventType, Location, Card, AttendanceRecord,
    Department, AnalyticsCache, ReportConfiguration, EmployeeAnalytics, 
    DepartmentAnalytics, SystemPerformance, TaskAssignment, LocationMovement, LocationAnalytics
)


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


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code', 'description')
    ordering = ('name',)


@admin.register(AnalyticsCache)
class AnalyticsCacheAdmin(admin.ModelAdmin):
    list_display = ('cache_key', 'cache_type', 'created_at', 'expires_at', 'is_expired')
    list_filter = ('cache_type', 'created_at', 'expires_at')
    search_fields = ('cache_key',)
    readonly_fields = ('created_at',)
    
    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'


@admin.register(ReportConfiguration)
class ReportConfigurationAdmin(admin.ModelAdmin):
    list_display = ('user', 'report_type', 'created_at', 'updated_at')
    list_filter = ('report_type', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(EmployeeAnalytics)
class EmployeeAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'total_events', 'total_hours_worked', 'attendance_score', 'is_anomaly')
    list_filter = ('date', 'is_anomaly', 'is_late_arrival', 'is_early_departure')
    search_fields = ('employee__given_name', 'employee__surname')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'


@admin.register(DepartmentAnalytics)
class DepartmentAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('department', 'date', 'total_employees', 'present_employees', 'average_attendance_rate')
    list_filter = ('date', 'department')
    search_fields = ('department__name',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'


@admin.register(SystemPerformance)
class SystemPerformanceAdmin(admin.ModelAdmin):
    list_display = ('date', 'total_events_processed', 'active_users', 'api_requests', 'average_response_time')
    list_filter = ('date',)
    readonly_fields = ('timestamp',)
    date_hierarchy = 'date'


@admin.register(TaskAssignment)
class TaskAssignmentAdmin(admin.ModelAdmin):
    list_display = ('employee', 'location', 'task_type', 'assigned_date', 'is_completed', 'created_by')
    list_filter = ('assigned_date', 'is_completed', 'location', 'task_type', 'created_by')
    search_fields = ('employee__given_name', 'employee__surname', 'location__name', 'task_type')
    date_hierarchy = 'assigned_date'
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_completed',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('employee', 'location', 'created_by')


@admin.register(LocationMovement)
class LocationMovementAdmin(admin.ModelAdmin):
    list_display = ('employee', 'from_location', 'to_location', 'movement_type', 'timestamp', 'created_by')
    list_filter = ('movement_type', 'timestamp', 'created_by')
    search_fields = ('employee__given_name', 'employee__surname', 'from_location__name', 'to_location__name')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)


@admin.register(LocationAnalytics)
class LocationAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('location', 'date', 'current_occupancy', 'utilization_rate', 'total_movements')
    list_filter = ('date', 'location')
    search_fields = ('location__name',)
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at')


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
