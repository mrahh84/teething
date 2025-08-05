from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connections
from django.http import HttpResponse, HttpResponseBadRequest, StreamingHttpResponse, JsonResponse
from rest_framework.response import Response
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone as django_timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.db.models import Q, Count, Prefetch, Avg
from datetime import datetime, timedelta, date
import datetime as dt
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
import json
import traceback
import csv
import re
from typing import Optional

from .models import (
    Employee, Event, EventType, Location, AttendanceRecord, Card, Department,
    AnalyticsCache, ReportConfiguration, EmployeeAnalytics, DepartmentAnalytics, SystemPerformance,
    TaskAssignment, LocationMovement, LocationAnalytics
)
from .forms import (
    AttendanceRecordForm, BulkHistoricalUpdateForm, ProgressiveEntryForm, 
    HistoricalProgressiveEntryForm, AttendanceFilterForm,
    TaskAssignmentForm, BulkTaskAssignmentForm, LocationAssignmentFilterForm
)
from .serializers import (
    EmployeeSerializer,
    EventSerializer,
    LocationSerializer,
    SingleEventSerializer,
    DepartmentSerializer,
    AnalyticsCacheSerializer,
    ReportConfigurationSerializer,
    EmployeeAnalyticsSerializer,
    DepartmentAnalyticsSerializer,
    SystemPerformanceSerializer,
)
from .utils import performance_monitor, query_count_monitor
from .decorators import security_required, attendance_required, reporting_required, admin_required
from .permissions import SecurityPermission, AttendancePermission, ReportingPermission, AdminPermission

# --- API Views ---
# Apply authentication and permissions to all API views


class SingleEventView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Event.
    Requires authentication for creating, updating or deleting.
    Uses PrimaryKeyRelatedFields for related objects during updates.
    """

    authentication_classes = [SessionAuthentication]  # Or TokenAuthentication, etc.
    permission_classes = [SecurityPermission]  # Security can view events
    serializer_class = SingleEventSerializer
    queryset = Event.objects.all()
    lookup_field = "id"

    # Optional: Set created_by automatically on create/update
    # def perform_create(self, serializer):
    #     serializer.save(created_by=self.request.user)

    # def perform_update(self, serializer):
    #     serializer.save(created_by=self.request.user) # Or maybe don't update created_by


class SingleLocationView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Location.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [SecurityPermission]  # Security can view locations
    serializer_class = LocationSerializer
    queryset = Location.objects.all()
    lookup_field = "id"


class SingleEmployeeView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Employee.
    Requires authentication for creating, updating or deleting.
    Uses EmployeeSerializer which provides detailed info for retrieve
    and accepts IDs for related fields during updates.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AdminPermission]  # Only admin can manage employees
    serializer_class = EmployeeSerializer
    queryset = Employee.objects.all()
    lookup_field = "id"


class ListEventsView(generics.ListAPIView):
    """
    API endpoint for listing all Events.
    Requires authentication for creating, updating or deleting.
    Shows nested details of related objects.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [SecurityPermission]  # Security can view events
    serializer_class = EventSerializer  # Use the detailed serializer for listing
    queryset = (
        Event.objects.all()
        .select_related(  # Optimize query
            "event_type", "employee", "location", "created_by"
        )
        .order_by("-timestamp")
    )


class ListDepartmentsView(generics.ListAPIView):
    """
    API endpoint for listing all Departments.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AdminPermission]  # Only admin can view departments
    serializer_class = DepartmentSerializer
    queryset = Department.objects.filter(is_active=True)


class SingleDepartmentView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Department.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AdminPermission]  # Only admin can manage departments
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()
    lookup_field = "id"


class ListAnalyticsCacheView(generics.ListAPIView):
    """
    API endpoint for listing AnalyticsCache entries.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can view analytics cache
    serializer_class = AnalyticsCacheSerializer
    queryset = AnalyticsCache.objects.all()


class SingleAnalyticsCacheView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single AnalyticsCache entry.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can manage analytics cache
    serializer_class = AnalyticsCacheSerializer
    queryset = AnalyticsCache.objects.all()
    lookup_field = "id"


class ListReportConfigurationsView(generics.ListAPIView):
    """
    API endpoint for listing ReportConfiguration entries.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can view report configurations
    serializer_class = ReportConfigurationSerializer
    queryset = ReportConfiguration.objects.all()

    def get_queryset(self):
        """Filter configurations by current user."""
        return ReportConfiguration.objects.filter(user=self.request.user)


class SingleReportConfigurationView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single ReportConfiguration entry.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can manage report configurations
    serializer_class = ReportConfigurationSerializer
    queryset = ReportConfiguration.objects.all()
    lookup_field = "id"

    def get_queryset(self):
        """Filter configurations by current user."""
        return ReportConfiguration.objects.filter(user=self.request.user)


class ListEmployeeAnalyticsView(generics.ListAPIView):
    """
    API endpoint for listing EmployeeAnalytics entries.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can view employee analytics
    serializer_class = EmployeeAnalyticsSerializer
    queryset = EmployeeAnalytics.objects.all()

    def get_queryset(self):
        """Allow filtering by employee, date range, and anomaly status."""
        queryset = EmployeeAnalytics.objects.all()
        
        # Filter by employee
        employee_id = self.request.query_params.get('employee_id')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        # Filter by anomaly status
        is_anomaly = self.request.query_params.get('is_anomaly')
        if is_anomaly is not None:
            queryset = queryset.filter(is_anomaly=is_anomaly.lower() == 'true')
        
        return queryset.order_by('-date', 'employee__surname')


class SingleEmployeeAnalyticsView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single EmployeeAnalytics entry.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can manage employee analytics
    serializer_class = EmployeeAnalyticsSerializer
    queryset = EmployeeAnalytics.objects.all()
    lookup_field = "id"


class ListDepartmentAnalyticsView(generics.ListAPIView):
    """
    API endpoint for listing DepartmentAnalytics entries.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can view department analytics
    serializer_class = DepartmentAnalyticsSerializer
    queryset = DepartmentAnalytics.objects.all()

    def get_queryset(self):
        """Allow filtering by department and date range."""
        queryset = DepartmentAnalytics.objects.all()
        
        # Filter by department
        department_id = self.request.query_params.get('department_id')
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        return queryset.order_by('-date', 'department__name')


class SingleDepartmentAnalyticsView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single DepartmentAnalytics entry.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting role can manage department analytics
    serializer_class = DepartmentAnalyticsSerializer
    queryset = DepartmentAnalytics.objects.all()
    lookup_field = "id"


class ListSystemPerformanceView(generics.ListAPIView):
    """
    API endpoint for listing SystemPerformance entries.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AdminPermission]  # Only admin can view system performance
    serializer_class = SystemPerformanceSerializer
    queryset = SystemPerformance.objects.all()

    def get_queryset(self):
        """Allow filtering by date range."""
        queryset = SystemPerformance.objects.all()
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        return queryset.order_by('-date')


class SingleSystemPerformanceView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single SystemPerformance entry.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AdminPermission]  # Only admin can manage system performance
    serializer_class = SystemPerformanceSerializer
    queryset = SystemPerformance.objects.all()
    lookup_field = "id"


# --- Attendance Views ---

@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def attendance_analytics(request):
    """
    Comprehensive attendance analytics view with filtering and statistics.
    """
    # Get filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    department_filter = request.GET.get('department', 'Digitization Tech')  # Default to Digitization Tech
    
    # Default to last 30 days if no dates provided
    if not start_date:
        start_date = (django_timezone.now() - timedelta(days=30)).date().isoformat()
    if not end_date:
        end_date = django_timezone.now().date().isoformat()
    
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        start_date = (django_timezone.now() - timedelta(days=30)).date()
        end_date = django_timezone.now().date()
    
    # Get all employees
    employees = Employee.objects.filter(is_active=True).order_by('surname', 'given_name')
    
    # Apply department filter
    if department_filter:
        employees = filter_employees_by_department(employees, department_filter)
    
    # Get attendance records for the date range
    records = AttendanceRecord.objects.filter(
        date__gte=start_date,
        date__lte=end_date,
        employee__in=employees
    ).select_related('employee')
    
    # Calculate statistics
    total_records = records.count()
    total_employees = len(employees)  # Use len() since employees is now a list
    
    # Count problematic records (excluding absences - based on Garbage logic)
    problematic_records = sum(1 for record in records if record.is_problematic_day())
    
    # Calculate attendance percentage
    if total_records > 0:
        attendance_percentage = ((total_records - problematic_records) / total_records) * 100
    else:
        attendance_percentage = 0
    
    # Get top problematic employees
    employee_issues = {}
    for record in records:
        if record.is_problematic_day():
            emp_name = f"{record.employee.given_name} {record.employee.surname}"
            employee_issues[emp_name] = employee_issues.get(emp_name, 0) + record.total_issues
    
    top_problematic = sorted(employee_issues.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Get period summary statistics (instead of daily breakdown)
    period_summary = {
        'total_records': total_records,
        'problematic_records': problematic_records,
        'attendance_percentage': round(attendance_percentage, 2),
        'avg_records_per_day': round(total_records / max(1, (end_date - start_date).days + 1), 2),
        'avg_problematic_per_day': round(problematic_records / max(1, (end_date - start_date).days + 1), 2),
        'period_days': (end_date - start_date).days + 1,
    }
    
    # Get available departments for filter
    available_departments = get_available_departments()
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'department_filter': department_filter,
        'available_departments': available_departments,
        'total_records': total_records,
        'total_employees': total_employees,
        'problematic_records': problematic_records,
        'attendance_percentage': round(attendance_percentage, 2),
        'top_problematic': top_problematic,
        'period_summary': period_summary,
        'employees': employees,
    }
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return just the analytics content for AJAX requests
        return render(request, 'attendance/analytics_content.html', context)
    
    return render(request, 'attendance/analytics.html', context)


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def comprehensive_reports(request):
    """
    Comprehensive reports page with tabs for different report types.
    """
    try:
        import marimo
        marimo_available = True
    except ImportError:
        marimo_available = False

    active_tab = request.GET.get('tab', 'comprehensive_attendance')
    
    start_date = request.GET.get('start_date', django_timezone.now().date().replace(day=1).isoformat())
    end_date = request.GET.get('end_date', django_timezone.now().date().isoformat())
    department_filter = request.GET.get('department', 'Digitization Tech')  # Default to Digitization Tech
    
    employee_id = request.GET.get("employee_id")
    period = request.GET.get("period", "day")
    start_time = request.GET.get("start_time", "09:00")
    end_time = request.GET.get("end_time", "17:00")
    
    employees = Employee.objects.all().order_by("surname", "given_name")
    
    if not employee_id and employees.exists():
        employee_id = employees.first().id

    # Get available departments for filter
    available_departments = get_available_departments()

    context = {
        "user": request.user,
        "marimo_available": marimo_available,
        "active_tab": active_tab,
        "start_date": start_date,
        "end_date": end_date,
        "department_filter": department_filter,
        "available_departments": available_departments,
        "employees": employees,
        "selected_employee_id": employee_id,
        "selected_period": period,
        "start_time": start_time,
        "end_time": end_time,
        "timestamp": int(django_timezone.now().timestamp()),
    }
    
    return render(request, "reports/comprehensive_reports.html", context)


@attendance_required  # Attendance management role and above
@extend_schema(exclude=True)
def progressive_entry(request):
    """Progressive attendance entry - optimized with bulk prefetch"""
    today = django_timezone.localtime(django_timezone.now()).date()
    
    # Get request parameters for filtering
    start_letter = request.GET.get("start_letter", "")
    search_query = request.GET.get("search", "")
    department_filter = request.GET.get('department', 'Digitization Tech')
    
    if request.method == 'POST':
        # Handle AJAX save requests (existing code)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Handle batch updates
            if request.POST.get('batch_update') == 'true':
                completions = {}
                
                # Parse all POST data to find changes
                for key, value in request.POST.items():
                    if key.startswith('changes[') and value:  # Only process non-empty values
                        try:
                            # Parse key format: changes[employee_id][field_name]
                            # Remove 'changes[' prefix and split by ']['
                            key_part = key[8:]  # Remove 'changes[' prefix
                            if key_part.endswith(']'):
                                key_part = key_part[:-1]  # Remove trailing ']'
                            
                            # Split by '][' to get employee_id and field_name
                            parts = key_part.split('][')
                            if len(parts) == 2:
                                employee_id = parts[0]
                                field_name = parts[1]
                                
                                if employee_id and field_name:
                                    employee = Employee.objects.get(id=employee_id)
                                    record, created = AttendanceRecord.objects.get_or_create(
                                        employee=employee,
                                        date=today,
                                        defaults={'created_by': request.user}
                                    )
                                    
                                    # Convert lunch_time string to time object
                                    if field_name == 'lunch_time' and value:
                                        try:
                                            value = datetime.strptime(value, "%H:%M").time()
                                        except Exception:
                                            value = None
                                    
                                    # Update the specific field
                                    if hasattr(record, field_name):
                                        setattr(record, field_name, value)
                                        record.last_updated_by = request.user
                                        record.save()
                                        
                                        completions[employee_id] = record.completion_percentage
                        except (Employee.DoesNotExist, ValueError) as e:
                            return JsonResponse({'success': False, 'error': f'Error processing batch update: {str(e)}'})
                return JsonResponse({
                    'success': True,
                    'completions': completions,
                    'message': f'Batch update completed for {len(completions)} records'
                })
            
            # Handle single field updates (existing code)
            employee_id = request.POST.get('employee_id')
            field_name = request.POST.get('field_name')
            field_value = request.POST.get('field_value')
            
            try:
                employee = Employee.objects.get(id=employee_id)
                record, created = AttendanceRecord.objects.get_or_create(
                    employee=employee,
                    date=today,
                    defaults={'created_by': request.user}
                )
                
                # Convert lunch_time string to time object
                if field_name == 'lunch_time' and field_value:
                    try:
                        field_value = datetime.strptime(field_value, "%H:%M").time()
                    except Exception:
                        field_value = None
                
                # Update the specific field
                if hasattr(record, field_name):
                    setattr(record, field_name, field_value)
                    record.last_updated_by = request.user
                    record.save()
                    
                    return JsonResponse({
                        'success': True,
                        'status': record.status,
                        'completion': record.completion_percentage,
                        'message': f'{field_name} updated successfully'
                    })
                else:
                    return JsonResponse({'success': False, 'error': 'Invalid field'})
                    
            except Employee.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Employee not found'})
        
        # Handle regular form submission
        form = ProgressiveEntryForm(request.POST)
        if form.is_valid():
            employee = form.cleaned_data['employee']
            record, created = AttendanceRecord.objects.get_or_create(
                employee=employee,
                date=today,
                defaults={'created_by': request.user}
            )
            
            # Update fields that were provided
            for field_name in ['standup_attendance', 'left_lunch_on_time', 
                             'returned_on_time_after_lunch', 'returned_after_lunch', 'lunch_time', 'notes']:
                if form.cleaned_data.get(field_name):
                    setattr(record, field_name, form.cleaned_data[field_name])
            
            record.last_updated_by = request.user
            record.save()
            
            messages.success(request, f'Attendance data saved for {employee} ({record.status})')
            return redirect('progressive_entry')
    else:
        form = ProgressiveEntryForm()
    
    # Get employees who were actually present (had clock-in events) today
    from datetime import time
    # Convert today to UTC for proper timezone handling
    start_of_day_local = django_timezone.make_aware(datetime.combine(today, time.min))
    end_of_day_local = django_timezone.make_aware(datetime.combine(today, time.max))
    
    # Convert to UTC for database query
    start_of_day_utc = start_of_day_local.astimezone(dt.timezone.utc)
    end_of_day_utc = end_of_day_local.astimezone(dt.timezone.utc)
    
    # Get employees who clocked in today (using UTC timestamps)
    present_employees = Event.objects.filter(
        event_type__name='Clock In',
        timestamp__gte=start_of_day_utc,
        timestamp__lte=end_of_day_utc
    ).values_list('employee', flat=True).distinct()
    
    # Get the actual employee objects for present employees
    employees = Employee.objects.filter(
        id__in=present_employees,
        is_active=True
    ).select_related('card_number').order_by('surname', 'given_name')
    
    # Apply department filter
    if department_filter and department_filter != 'All Departments':
        employees = filter_employees_by_department(employees, department_filter)
    
    # Apply letter filter
    if start_letter and start_letter != 'all' and len(start_letter) == 1:
        employees = employees.filter(surname__istartswith=start_letter)
    
    # Apply search filter
    if search_query:
        employees = employees.filter(
            Q(given_name__icontains=search_query)
            | Q(surname__icontains=search_query)
            | Q(card_number__designation__icontains=search_query)
        )
    
    # BULK PREFETCH: Get all today's records in one query
    today_records = AttendanceRecord.objects.filter(
        date=today,
        employee__in=employees
    ).select_related('employee', 'employee__card_number')
    
    # Create lookup dictionary for O(1) access
    records_by_employee = {record.employee_id: record for record in today_records}
    
    # Create employee attendance list with O(1) lookups
    employee_attendance = []
    for employee in employees:
        record = records_by_employee.get(employee.id)
        
        employee_attendance.append({
            'employee': employee,
            'record': record,
            'is_clocked_in': True,  # All employees shown are present
            'arrival_time': record.arrival_time if record else None,
            'departure_time': record.departure_time if record else None,
        })
    
    # Get available departments for filter
    available_departments = get_available_departments()
    
    context = {
        'today': today,
        'today_records': today_records,
        'employee_attendance': employee_attendance,
        'employees': employees,
        'form': form,
        'start_letter': start_letter,
        'search_query': search_query,
        'department_filter': department_filter,
        'available_departments': available_departments,
    }
    
    return render(request, 'attendance/progressive_entry.html', context)


@attendance_required  # Attendance management role and above
@extend_schema(exclude=True)
def attendance_list(request):
    """
    List view of attendance records with filtering and search.
    """
    # Get filter parameters
    date_filter = request.GET.get('date')
    employee_filter = request.GET.get('employee')
    status_filter = request.GET.get('status')
    department_filter = request.GET.get('department', 'Digitization Tech')  # Default to Digitization Tech
    
    # Default to today if no date specified
    if not date_filter:
        date_filter = django_timezone.localtime(django_timezone.now()).date().isoformat()
    
    try:
        target_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
    except ValueError:
        target_date = django_timezone.localtime(django_timezone.now()).date()
    
    # Get all active employees with optimized prefetch
    all_employees = Employee.objects.filter(is_active=True).select_related('card_number').order_by('surname', 'given_name')
    
    # Apply department filter to employees
    if department_filter:
        all_employees = filter_employees_by_department(all_employees, department_filter)
    
    # Get attendance records for the target date with optimized prefetch
    records = AttendanceRecord.objects.filter(date=target_date).select_related('employee', 'employee__card_number')
    
    # Apply department filter to records using the same logic
    if department_filter:
        # Filter records by department using the same logic as employees
        filtered_records = []
        for record in records:
            if record.employee.card_number:
                emp_dept = get_department_from_designation(record.employee.card_number.designation)
                if emp_dept == department_filter:
                    filtered_records.append(record)
        records = filtered_records
    
    # Filter by employee if specified
    if employee_filter:
        records = records.filter(employee_id=employee_filter)
    
    # Filter by status if specified
    if status_filter:
        records = records.filter(status=status_filter)
    
    # Identify absent employees (those who didn't clock in) - OPTIMIZED
    from datetime import time
    # Convert local date to UTC for proper timezone handling
    start_of_day_local = django_timezone.make_aware(datetime.combine(target_date, time.min))
    end_of_day_local = django_timezone.make_aware(datetime.combine(target_date, time.max))
    
    # Convert to UTC for database query
    start_of_day = start_of_day_local.astimezone(dt.timezone.utc)
    end_of_day = end_of_day_local.astimezone(dt.timezone.utc)
    
    # Single optimized query to get all clocked-in employee IDs
    clocked_in_employees = set(
        Event.objects.filter(
            event_type__name='Clock In',
            timestamp__gte=start_of_day,
            timestamp__lte=end_of_day
        ).values_list('employee_id', flat=True)
    )
    
    absentees = [emp for emp in all_employees if emp.id not in clocked_in_employees]
    
    # Filter by employee if specified
    if employee_filter:
        absentees = [emp for emp in absentees if str(emp.id) == employee_filter]
    
    # Build a list of display records: attendance records + absentees + clocked-in with no record
    # Filter out attendance records for absent employees to avoid duplicates
    absentee_ids = {emp.id for emp in absentees}
    filtered_records = [r for r in records if r.employee.id not in absentee_ids]
    display_records = list(filtered_records)
    
    # Add absent employees as dummy records
    for employee in absentees:
        # Create a dummy record-like object for template
        dummy_record = type('DummyRecord', (), {
            'employee': employee,
            'date': target_date,
            'arrival_time': None,
            'departure_time': None,
            'is_absent': True,
            'is_problematic_day': lambda: False,
            'total_issues': 0,
            'status': 'ABSENT',
        })()
        display_records.append(dummy_record)
    
    # Add employees who clocked in but don't have attendance records
    clocked_in_no_record = []
    for employee in all_employees:
        if (employee.id in clocked_in_employees and 
            not any(r.employee.id == employee.id for r in display_records)):
            # Create a dummy record for clocked-in employee without attendance record
            dummy_record = type('DummyRecord', (), {
                'employee': employee,
                'date': target_date,
                'arrival_time': None,  # Will be calculated by property
                'departure_time': None,  # Will be calculated by property
                'is_absent': False,
                'is_problematic_day': lambda: False,
                'total_issues': 0,
                'status': 'DRAFT',
            })()
            display_records.append(dummy_record)
    
    # Sort display records
    display_records.sort(key=lambda x: (x.employee.surname, x.employee.given_name))
    
    # Pagination
    paginator = Paginator(display_records, 25)  # Show 25 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get available departments for filter
    available_departments = get_available_departments()
    
    context = {
        'date_filter': target_date,
        'employee_filter': employee_filter,
        'status_filter': status_filter,
        'department_filter': department_filter,
        'available_departments': available_departments,
        'page_obj': page_obj,
        'employees': all_employees,
        'total_records': len(display_records),
        'absent_count': len(absentees),
        'present_count': len(display_records) - len(absentees),
    }
    
    return render(request, 'attendance/list.html', context)


@attendance_required  # Attendance management role and above
@extend_schema(exclude=True)
def historical_progressive_entry(request):
    """
    Historical progressive entry for past dates.
    """
    from .forms import HistoricalProgressiveEntryForm
    
    if request.method == 'POST':
        form = HistoricalProgressiveEntryForm(request.POST)
        if form.is_valid():
            # Redirect to results page with search parameters
            date_from = form.cleaned_data['date_from']
            date_to = form.cleaned_data['date_to']
            department = form.cleaned_data['department']
            
            # Build redirect URL
            redirect_url = reverse('historical_progressive_results')
            params = {
                'date_from': date_from.isoformat(),
                'date_to': date_to.isoformat(),
                'department': department,
            }
            
            return redirect(f"{redirect_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}")
    else:
        # Handle GET parameters for quick actions
        date_from_param = request.GET.get('date_from')
        date_to_param = request.GET.get('date_to')
        
        if date_from_param and date_to_param:
            # Handle relative date parameters (e.g., -7, -14, -30)
            try:
                if date_from_param.startswith('-') and date_to_param.startswith('-'):
                    days_from = int(date_from_param)
                    days_to = int(date_to_param)
                    today = django_timezone.localtime(django_timezone.now()).date()
                    date_from = today + timedelta(days=days_from)
                    date_to = today + timedelta(days=days_to)
                else:
                    date_from = datetime.strptime(date_from_param, '%Y-%m-%d').date()
                    date_to = datetime.strptime(date_to_param, '%Y-%m-%d').date()
                
                # Redirect to results page
                redirect_url = reverse('historical_progressive_results')
                params = {
                    'date_from': date_from.isoformat(),
                    'date_to': date_to.isoformat(),
                }
                department = request.GET.get('department', 'Digitization Tech')
                params['department'] = department
                
                return redirect(f"{redirect_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}")
            except (ValueError, TypeError):
                pass
        
        # Initialize form with default values
        form = HistoricalProgressiveEntryForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'attendance/historical_progressive_entry.html', context)


@attendance_required  # Attendance management role and above
@extend_schema(exclude=True)
def historical_progressive_results(request):
    """
    Results page for historical progressive entry.
    """
    from django.core.paginator import Paginator
    
    # Handle POST requests for saving historical records
    if request.method == 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Handle AJAX save requests
            employee_id = request.POST.get('employee_id')
            field_name = request.POST.get('field_name')
            field_value = request.POST.get('field_value')
            record_date = request.POST.get('record_date')
            record_id = request.POST.get('record_id')
            
            try:
                # Handle both new records (employee_id + record_date) and existing records (record_id)
                if record_id and record_id != 'new':
                    # Updating existing record
                    record = AttendanceRecord.objects.get(id=record_id)
                    employee = record.employee
                    record_date = record.date
                elif employee_id and record_date:
                    # Creating new record
                    if isinstance(employee_id, str):
                        employee_id = int(employee_id)
                    employee = Employee.objects.get(id=employee_id, is_active=True)
                    record_date = datetime.strptime(record_date, '%Y-%m-%d').date()
                else:
                    return JsonResponse({'success': False, 'error': 'Missing required parameters'})
                
                # Check if record exists (only for new records)
                if record_id and record_id != 'new':
                    # We already have the record from above
                    created = False
                else:
                    # Check if record exists for new records
                    try:
                        record = AttendanceRecord.objects.get(employee=employee, date=record_date)
                        created = False
                    except AttendanceRecord.DoesNotExist:
                        # Create new record for missing employee
                        record = AttendanceRecord.objects.create(
                            employee=employee,
                            date=record_date,
                            created_by=request.user,
                            status='DRAFT'
                        )
                        created = True
                
                # Convert lunch_time string to time object
                if field_name == 'lunch_time' and field_value:
                    try:
                        field_value = datetime.strptime(field_value, "%H:%M").time()
                    except Exception:
                        field_value = None
                
                # Update the specific field
                if hasattr(record, field_name):
                    setattr(record, field_name, field_value)
                    record.last_updated_by = request.user
                    record.save()
                    
                    response_data = {
                        'success': True,
                        'status': record.status,
                        'completion': record.completion_percentage,
                        'message': f'{field_name} updated successfully'
                    }
                    
                    # If this was a new record, include the record ID
                    if created:
                        response_data['record_id'] = record.id
                    
                    return JsonResponse(response_data)
                else:
                    return JsonResponse({'success': False, 'error': 'Invalid field'})
                    
            except (Employee.DoesNotExist, ValueError) as e:
                return JsonResponse({'success': False, 'error': f'Error: {str(e)}'})
    
    # Get search parameters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    department_filter = request.GET.get('department', 'Digitization Tech')  # Default to Digitization Tech
    days_per_page = int(request.GET.get('days_per_page', 7))
    page_number = request.GET.get('page', 1)
    
    if not date_from or not date_to:
        return redirect('historical_progressive_entry')
    
    try:
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        page_number = int(page_number)
    except (ValueError, TypeError):
        return redirect('historical_progressive_entry')
    
    # Get employees by department filter
    all_employees = Employee.objects.filter(is_active=True)
    if department_filter and department_filter != 'All Departments':
        filtered_employees = filter_employees_by_department(all_employees, department_filter)
    else:
        filtered_employees = all_employees
    
    # Get all dates in the range
    date_range = []
    current_date = date_from
    while current_date <= date_to:
        date_range.append(current_date)
        current_date += timedelta(days=1)
    
    # Paginate the dates
    date_paginator = Paginator(date_range, days_per_page)
    date_page = date_paginator.get_page(page_number)
    
    # Get records for the current page of dates
    records_by_date = {}
    for date_key in date_page:
        # Get employees who were actually present (had clock-in events) on this date
        from common.models import Event
        present_employees = Event.objects.filter(
            timestamp__date=date_key,
            event_type__name='Clock In'
        ).values_list('employee', flat=True).distinct()
        
        # Filter by department if specified
        if department_filter and department_filter != 'All Departments':
            present_employees = present_employees.filter(employee__in=filtered_employees)
        
        # Get the actual employee objects for present employees
        present_employee_objects = Employee.objects.filter(
            id__in=present_employees,
            is_active=True
        ).order_by('surname', 'given_name')
        
        # Get existing attendance records for present employees on this date
        existing_records = AttendanceRecord.objects.filter(
            date=date_key,
            employee__in=present_employee_objects
        ).select_related('employee').order_by('employee__surname', 'employee__given_name')
        
        # Create a list of present employees with their records (or create new records if needed)
        employee_records = []
        for emp in present_employee_objects:
            # Find existing record for this employee on this date
            existing_record = existing_records.filter(employee=emp).first()
            
            # Get clock in/out events for this employee on this date
            clock_events = Event.objects.filter(
                employee=emp,
                timestamp__date=date_key,
                event_type__name__in=['Clock In', 'Clock Out']
            ).select_related('event_type').order_by('timestamp')
            
            # Extract clock in/out times
            clock_in_time = None
            clock_out_time = None
            for event in clock_events:
                if event.event_type.name == 'Clock In':
                    clock_in_time = event.timestamp
                elif event.event_type.name == 'Clock Out':
                    clock_out_time = event.timestamp
            
            if existing_record:
                # Add clock times to existing record
                existing_record.clock_in_time = clock_in_time
                existing_record.clock_out_time = clock_out_time
                employee_records.append(existing_record)
            else:
                # Create a dummy record object for present employees without attendance records
                # This allows the template to show present employees and create records on demand
                dummy_record = type('DummyRecord', (), {
                    'id': None,
                    'employee': emp,
                    'date': date_key,
                    'lunch_time': None,
                    'left_lunch_on_time': None,
                    'returned_on_time_after_lunch': None,
                    'returned_after_lunch': None,
                    'standup_attendance': None,
                    'status': 'DRAFT',
                    'completion_percentage': 0,
                    'last_updated_by': None,
                    'updated_at': None,
                    'notes': '',
                    'clock_in_time': clock_in_time,
                    'clock_out_time': clock_out_time,
                })()
                employee_records.append(dummy_record)
        
        if employee_records:
            records_by_date[date_key] = employee_records
    
    # Calculate statistics
    total_days = len(date_range)
    total_records = sum(len(records) for records in records_by_date.values())
    
    # Get available departments for filter
    available_departments = get_available_departments()
    
    context = {
        'date_from': date_from,
        'date_to': date_to,
        'department_filter': department_filter,
        'available_departments': available_departments,
        'date_page': date_page,
        'records_by_date': records_by_date,
        'total_days': total_days,
        'total_records': total_records,
        'days_per_page': days_per_page,
    }
    
    return render(request, 'attendance/historical_progressive_results.html', context)


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def attendance_export_csv(request):
    """
    Export attendance records to CSV.
    """
    # Get filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    employee_filter = request.GET.get('employee')
    
    # Default to last 30 days if no dates provided
    if not start_date:
        start_date = (django_timezone.now() - timedelta(days=30)).date().isoformat()
    if not end_date:
        end_date = django_timezone.now().date().isoformat()
    
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        start_date = (django_timezone.now() - timedelta(days=30)).date()
        end_date = django_timezone.now().date()
    
    # Get attendance records
    records = AttendanceRecord.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).select_related('employee')
    
    # Filter by employee if specified
    if employee_filter:
        records = records.filter(employee_id=employee_filter)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_export_{start_date}_{end_date}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Employee Name',
        'Date',
        'Arrival Time',
        'Departure Time',
        'Worked Hours',
        'Standup Attendance',
        'Left Lunch On Time',
        'Returned On Time After Lunch',
        'Returned After Lunch',
        'Total Issues',
        'Status',
        'Notes'
    ])
    
    for record in records:
        writer.writerow([
            f"{record.employee.given_name} {record.employee.surname}",
            record.date,
            record.arrival_time.strftime('%H:%M') if record.arrival_time else '',
            record.departure_time.strftime('%H:%M') if record.departure_time else '',
            f"{record.worked_hours:.2f}" if record.worked_hours else '',
            record.standup_attendance or '',
            record.left_lunch_on_time or '',
            record.returned_on_time_after_lunch or '',
            record.returned_after_lunch or '',
            record.total_issues,
            record.status,
            record.notes or ''
        ])
    
    return response


# --- Template Views ---
# Apply login_required decorator


@security_required  # Security role and above
@extend_schema(exclude=True)
# NOTE: Keep exclude if you don't want this in API docs
# Link: https://drf-spectacular.readthedocs.io/en/latest/drf_spectacular.html#drf_spectacular.utils.extend_schema
def main_security(request):
    """
    Displays the main security dashboard, listing all employees
    and their current clock-in/out status. Requires login.
    Optimized with caching for better performance.
    """
    # Get request parameters for sorting and filtering
    search_query = request.GET.get("search", "")
    status_filter = request.GET.get("status", "all")
    sort_by = request.GET.get("sort", "surname")
    sort_direction = request.GET.get("direction", "asc")
    page_number = request.GET.get("page", "1")
    server_items_per_page = request.GET.get("items", "100")
    start_letter = request.GET.get("letter", "")

    try:
        server_items_per_page = int(server_items_per_page)
        if server_items_per_page not in [25, 50, 100, 200]:
            server_items_per_page = 100
    except ValueError:
        server_items_per_page = 100
    
    # Try to get cached data first
    try:
        from common.cache_utils import (
            get_main_security_cache_key, 
            get_cached_main_security_data,
            cache_main_security_data,
            bulk_cache_employee_statuses
        )
        
        cache_key = get_main_security_cache_key(
            int(page_number), sort_by, sort_direction, status_filter, search_query, start_letter
        )
        cached_data = get_cached_main_security_data(cache_key)
        
        if cached_data:
            return render(request, "main_security.html", cached_data)
    except ImportError:
        pass  # Fall back to non-cached version
        
    # Start with all employees, using optimized queries
    employees_query = Employee.objects.select_related("card_number").all()

    # Count stats for the dashboard before applying filters
    total_employees = employees_query.count()

    # Apply search if provided
    if search_query:
        employees_query = employees_query.filter(
            Q(given_name__icontains=search_query)
            | Q(surname__icontains=search_query)
            | Q(card_number__designation__icontains=search_query)
        )

    # Prefetch related events with only the latest clock in/out events to improve performance
    # This optimizes the is_clocked_in calculation
    one_month_ago = django_timezone.now() - timedelta(days=30)
    latest_events = (
        Event.objects.filter(
            timestamp__gte=one_month_ago, event_type__name__in=["Clock In", "Clock Out"]
        )
        .select_related("event_type")
        .order_by("-timestamp")
    )

    employees_query = employees_query.prefetch_related(
        Prefetch("employee_events", queryset=latest_events, to_attr="recent_events")
    )

    # Apply sorting
    if sort_by in ["given_name", "surname"]:
        order_by = sort_by
        if sort_direction == "desc":
            order_by = f"-{order_by}"
        employees_query = employees_query.order_by(order_by)

    # Get the employee list - we need to materialize the queryset here
    # because we need to apply status filtering and card sorting in Python
    all_employees = list(employees_query)
    
    # Bulk cache employee statuses to improve performance
    try:
        employee_ids = [emp.id for emp in all_employees]
        bulk_cache_employee_statuses(employee_ids)
    except (ImportError, NameError):
        pass  # Ignore if caching not available

    # Apply status filtering in Python since it's a calculated property
    if status_filter == "in":
        all_employees = [
            employee for employee in all_employees if employee.is_clocked_in()
        ]
    elif status_filter == "out":
        all_employees = [
            employee for employee in all_employees if not employee.is_clocked_in()
        ]

    # Sort by card number if requested (also needs to be done in Python)
    if sort_by == "card":
        reverse = sort_direction == "desc"
        all_employees.sort(
            key=lambda emp: emp.card_number.designation if emp.card_number else "",
            reverse=reverse,
        )
    
    # Apply letter filter if provided (after all other filtering)
    if start_letter and start_letter != 'all' and len(start_letter) == 1:
        all_employees = [
            employee for employee in all_employees 
            if employee.surname.upper().startswith(start_letter.upper())
        ]

    # Server-side pagination
    paginator = Paginator(all_employees, server_items_per_page)
    try:
        employees = paginator.page(page_number)
    except:
        employees = paginator.page(1)

    # Calculate summary statistics
    clocked_in_count = sum(1 for emp in all_employees if emp.is_clocked_in())
    clocked_out_count = len(all_employees) - clocked_in_count

    context = {
        "employees": employees,
        "user": request.user,
        "search_query": search_query,
        "status_filter": status_filter,
        "sort_by": sort_by,
        "sort_direction": sort_direction,
        "total_employees": len(all_employees),  # Use filtered count
        "clocked_in_count": clocked_in_count,
        "clocked_out_count": clocked_out_count,
        "start_letter": start_letter,
        "current_page": int(page_number),
        "total_pages": paginator.num_pages,
        "items_per_page": server_items_per_page,
    }
    
    # Cache the result for future requests
    try:
        cache_main_security_data(cache_key, context)
    except (ImportError, NameError):
        pass  # Ignore if caching not available
    
    return render(request, "main_security.html", context)


@security_required  # Security role and above
@extend_schema(exclude=True)
def main_security_clocked_in_status_flip(request, id):
    """
    Handles the clock-in/clock-out action for an employee from the main security view.
    Creates a new 'Clock In' or 'Clock Out' event. Requires login.
    Includes a basic debounce mechanism.
    Optimized with caching for better performance.
    """
    # Check if we need to clear cache (for testing purposes)
    if request.GET.get('clear_cache') == 'true':
        try:
            from django.core.cache import cache
            cache.delete(f"employee_status_{id}")
            cache.delete(f"employee_last_event_{id}")
            messages.info(request, "Employee cache cleared for testing.")
        except Exception:
            pass
    
    employee = get_object_or_404(Employee, id=id)

    # Determine the *opposite* action to take
    currently_clocked_in = employee.is_clocked_in()
    target_event_type_name = "Clock Out" if currently_clocked_in else "Clock In"

    # Basic Debounce: Prevent accidental double-clicks/rapid toggling
    # Check the time of the *very last* clock event for this user
    last_event_time = employee.last_clockinout_time
    debounce_seconds = 2  # Reduced from 5 to 2 seconds for better UX
    
    # More robust debounce check - also check recent events directly from database
    recent_events = Event.objects.filter(
        employee=employee,
        event_type__name__in=['Clock In', 'Clock Out']
    ).order_by('-timestamp')[:1]
    
    if recent_events.exists():
        most_recent_event = recent_events.first()
        # Simplified timezone handling - Django handles timezone conversion automatically
        current_time = django_timezone.now()
        event_time = most_recent_event.timestamp
        
        # Simple time difference calculation
        time_since_last_event = (current_time - event_time).total_seconds()
        
        # Safety check: if event is in the future or more than 1 hour ago, skip debounce
        if time_since_last_event < -3600 or time_since_last_event > 3600:
            # Skip debounce for invalid timestamps
            pass
        elif time_since_last_event < debounce_seconds:
            messages.warning(
                request, f"Please wait {debounce_seconds} seconds before clocking again."
            )
            print(
                f"Clock action for {employee} blocked by debounce ({debounce_seconds}s) - last event was {time_since_last_event:.1f}s ago"
            )  # Log for debugging
            return redirect("main_security")  # Redirect without making changes

    try:
        # Try to get cached event types and locations first for better performance
        try:
            from common.cache_utils import get_cached_event_types, get_cached_locations
            event_types = get_cached_event_types()
            locations = get_cached_locations()
            
            event_type = event_types.get(target_event_type_name)
            location = locations.get("Main Security")
            

            
            if not event_type:
                raise EventType.DoesNotExist(f"Event type '{target_event_type_name}' not found in cache")
            if not location:
                raise Location.DoesNotExist("Location 'Main Security' not found in cache")
                
        except ImportError:
            # Fall back to database queries if caching not available
            event_type = EventType.objects.get(name=target_event_type_name)
            location = Location.objects.get(name="Main Security")
            
    except (EventType.DoesNotExist, Location.DoesNotExist) as e:
        # Handle case where required EventType or Location is missing
        print(f"Error: Required EventType or Location missing: {e}")  # Log error
        messages.error(request, "System configuration error. Cannot process request.")
        return HttpResponseBadRequest(
            "System configuration error."
        )  # Or redirect with message

    # Create the new clock event with local timezone timestamp
    event = Event.objects.create(
        employee=employee,
        event_type=event_type,
        location=location,
        created_by=request.user,  # Record which logged-in user performed the action
        timestamp=django_timezone.localtime(django_timezone.now())  # Use local timezone instead of UTC
    )

    # Clear relevant caches to ensure real-time updates
    try:
        from django.core.cache import cache
        # Clear employee-specific caches
        cache.delete(f"employee_status_{employee.id}")
        cache.delete(f"employee_last_event_{employee.id}")
        
        # Clear main security page caches
        cache.delete_pattern("main_security_*")
        cache.delete_pattern("employee_status_*")
        
        # Clear template caches
        from django.core.cache import cache as template_cache
        template_cache.delete_pattern("main_security_*")
    except Exception:
        pass  # Ignore cache clearing errors

    # Optional: Add a success message with time and date
    # event_time = event.timestamp.strftime("%H:%M:%S on %d %b %Y")
    event_time = str(event)
    messages.success(request, event_time)
    # messages.success(request, f"{employee} successfully {event_type} at {event_time}.")

    # Preserve the filter parameters when redirecting
    query_params = request.GET.copy()
    redirect_url = "main_security"

    if query_params:
        query_string = query_params.urlencode()
        return redirect(f"{redirect_url}?{query_string}")
    else:
        return redirect(redirect_url)


@security_required  # Security role and above (read-only)
@extend_schema(exclude=True)
def employee_events(request, id):
    """
    Displays a detailed list of all events for a specific employee.
    Requires login.
    """
    employee = get_object_or_404(Employee.objects.select_related("card_number"), id=id)

    # Get filter parameters
    date_filter = request.GET.get("date", "")
    event_type_filter = request.GET.get("event_type", "")

    # Get all events for this employee
    employee_events_query = employee.employee_events.select_related(
        "event_type", "location", "created_by"
    )

    # Apply date filter if provided
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            employee_events_query = employee_events_query.filter(
                timestamp__date=filter_date
            )
        except ValueError:
            # Invalid date format - ignore the filter
            pass

    # Apply event type filter if provided
    if event_type_filter:
        employee_events_query = employee_events_query.filter(
            event_type__name=event_type_filter
        )

    # Order by timestamp
    employee_events = employee_events_query.order_by("-timestamp")

    # Get all event types for the filter dropdown
    event_types = EventType.objects.values_list("name", flat=True).distinct()

    # Get all locations for the location dropdown in the edit form
    locations = Location.objects.all()

    # Get some statistics for the employee
    today = django_timezone.now().date()
    week_ago = today - timedelta(days=7)

    today_events_count = Event.objects.filter(
        employee=employee, timestamp__date=today
    ).count()

    week_events_count = Event.objects.filter(
        employee=employee, timestamp__date__gte=week_ago
    ).count()

    context = {
        "employee": employee,
        "employee_events": employee_events,
        "user": request.user,
        "date_filter": date_filter,
        "event_type_filter": event_type_filter,
        "event_types": event_types,
        "locations": locations,
        "today_events_count": today_events_count,
        "week_events_count": week_events_count,
    }
    return render(request, "employee_rollup.html", context)


@security_required  # Security role and above
@extend_schema(exclude=True)
def update_event(request, employee_id):
    """
    Handle updating an event from the frontend.
    """
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("employee_events", id=employee_id)

    employee = get_object_or_404(Employee, id=employee_id)
    event_id = request.POST.get("event_id")

    if not event_id:
        messages.error(request, "No event specified.")
        return redirect("employee_events", id=employee_id)

    try:
        event = Event.objects.get(id=event_id, employee=employee)
    except Event.DoesNotExist:
        messages.error(request, "Event not found.")
        return redirect("employee_events", id=employee_id)

    # Get form data
    event_type_name = request.POST.get("event_type")
    location_id = request.POST.get("location")
    date_str = request.POST.get("date")
    time_str = request.POST.get("time")

    # Validate data
    if not all([event_type_name, location_id, date_str, time_str]):
        messages.error(request, "All fields are required.")
        return redirect("employee_events", id=employee_id)

    try:
        # Get event type and location
        event_type = EventType.objects.get(name=event_type_name)
        location = Location.objects.get(id=location_id)

        # Parse date and time
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        time_obj = datetime.strptime(time_str, "%H:%M:%S").time()
        timestamp = django_timezone.make_aware(datetime.combine(date_obj, time_obj))

        # Update event
        event.event_type = event_type
        event.location = location
        event.timestamp = timestamp
        event.save()

        messages.success(request, f"Event successfully updated.")
    except (EventType.DoesNotExist, Location.DoesNotExist, ValueError) as e:
        messages.error(request, f"Error updating event: {str(e)}")

    return redirect("employee_events", id=employee_id)


@security_required  # Security role and above
@extend_schema(exclude=True)
def delete_event(request, employee_id):
    """
    Handle deleting an event from the frontend.
    """
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("employee_events", id=employee_id)

    employee = get_object_or_404(Employee, id=employee_id)
    event_id = request.POST.get("event_id")

    if not event_id:
        messages.error(request, "No event specified.")
        return redirect("employee_events", id=employee_id)

    try:
        event = Event.objects.get(id=event_id, employee=employee)
        event_type_name = event.event_type.name
        event.delete()
        messages.success(request, f"'{event_type_name}' event successfully deleted.")
    except Event.DoesNotExist:
        messages.error(request, "Event not found.")

    return redirect("employee_events", id=employee_id)


# --- Reports Views ---
@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def reports_dashboard(request):
    """
    Reports dashboard - Redirect to comprehensive reports.
    This page is now redundant with the comprehensive reports page.
    """
    return redirect('comprehensive_reports')


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def daily_dashboard_report(request):
    """
    Display the daily attendance dashboard using Marimo.
    """
    # Get today's date in local timezone
    today_local = django_timezone.localtime().date()

    # Get filter parameters
    date_str = request.GET.get("date", today_local.isoformat())

    try:
        # Try to convert string to date to validate format
        selected_date = datetime.fromisoformat(date_str).date()
    except ValueError:
        # If invalid date, default to today's local date
        selected_date = today_local
        date_str = selected_date.isoformat()

    context = {
        "user": request.user,
        "selected_date": date_str,
        "report_url": f"{reverse('generate_marimo_report', args=['daily_dashboard'])}?date={date_str}",
        "report_title": "Daily Attendance Dashboard",
        "report_description": "Real-time attendance status showing currently clocked-in and not-clocked-in employees.",
    }
    return render(request, "reports/marimo_report.html", context)


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def employee_history_report(request):
    """
    Display the employee attendance history report using Marimo.
    """
    # Get filter parameters
    employee_id = request.GET.get("employee_id")
    start_date = request.GET.get(
        "start_date", django_timezone.now().date().replace(day=1).isoformat()
    )
    end_date = request.GET.get("end_date", django_timezone.now().date().isoformat())

    # Get all employees for the dropdown
    employees = Employee.objects.all().order_by("surname", "given_name")

    # If no employee selected, default to first one
    if not employee_id and employees.exists():
        employee_id = employees.first().id

    context = {
        "user": request.user,
        "employees": employees,
        "selected_employee_id": employee_id,
        "start_date": start_date,
        "end_date": end_date,
        "report_url": f"{reverse('generate_marimo_report', args=['employee_history'])}?employee_id={employee_id}&start={start_date}&end={end_date}",
        "report_title": "Employee Attendance History",
        "report_description": "Detailed attendance history for individual employees with hours calculation.",
    }
    return render(request, "reports/employee_history_report.html", context)


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def period_summary_report(request):
    """
    Display the attendance summary by period (daily, weekly, monthly) using Marimo.
    """
    # Get filter parameters
    period = request.GET.get("period", "day")
    start_date = request.GET.get("start_date", django_timezone.now().date().isoformat())
    start_time = request.GET.get("start_time", "09:00")
    end_time = request.GET.get("end_time", "17:00")

    context = {
        "user": request.user,
        "selected_period": period,
        "start_date": start_date,
        "start_time": start_time,
        "end_time": end_time,
        "report_url": f"{reverse('generate_marimo_report', args=['period_summary'])}?period={period}&start={start_date}&start_time={start_time}&end_time={end_time}",
        "report_title": "Attendance Summary by Period",
        "report_description": "Aggregated attendance statistics showing hours worked, late arrivals, and early departures.",
    }
    return render(request, "reports/period_summary_report.html", context)





@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
@xframe_options_sameorigin
def generate_marimo_report(request, report_type):
    """
    Generate and serve a Marimo report for the specified report type.
    """
    try:
        # Import marimo to check if it's installed
        import marimo as mo

        # We'll use our custom Marimo notebooks for reports
        print(
            f"Marimo is installed (version {mo.__version__}), creating {report_type} report"
        )

        # Get filter parameters
        start_date_str = request.GET.get(
            "start", django_timezone.now().date().replace(day=1).isoformat()
        )
        end_date_str = request.GET.get("end", django_timezone.now().date().isoformat())

        # Convert string dates to datetime objects
        try:
            start_date = datetime.fromisoformat(start_date_str).date()
            end_date = datetime.fromisoformat(end_date_str).date()

            # Add one day to end_date to include the entire end day
            end_date_with_day = end_date + timedelta(days=1)
        except ValueError as e:
            return HttpResponse(f"Invalid date format: {str(e)}", status=400)

        # Add logging to debug
        print(f"Generating {report_type} report for dates {start_date} to {end_date}")

        # For now, use fallback HTML reports for all report types
        # This ensures users see something while we resolve Marimo integration issues
        if report_type == "daily_dashboard":
            date_str = request.GET.get("date", django_timezone.now().date().isoformat())
            try:
                selected_date = datetime.fromisoformat(date_str).date()
            except ValueError:
                selected_date = django_timezone.now().date()

            return generate_daily_dashboard_html(request, selected_date)

        elif report_type == "employee_history":
            employee_id = request.GET.get("employee_id")
            if not employee_id:
                return HttpResponse("Employee ID is required", status=400)

            return generate_employee_history_html(
                request, employee_id, start_date, end_date_with_day
            )

        elif report_type == "period_summary":
            period = request.GET.get("period", "day")
            start_time = request.GET.get("start_time", "09:00")
            end_time = request.GET.get("end_time", "17:00")

            return generate_period_summary_html(
                request, period, start_date, end_date_with_day, start_time, end_time
            )



        else:
            return HttpResponse(f"Unknown report type: {report_type}", status=400)

    except ImportError:
        print("Marimo not installed")
        return HttpResponse(
            "Marimo is not installed. Reports require Marimo to be installed.",
            status=500,
        )
    except Exception as e:
        error_msg = f"Error generating report: {str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)  # Log the full error to the console
        return HttpResponse(f"Error generating report: {str(e)}", status=500)


def generate_daily_dashboard_html(request, selected_date):
    """Generate HTML report for daily dashboard"""
    # Calculate start and end of selected date
    start_of_day = django_timezone.make_aware(
        datetime.combine(selected_date, datetime.min.time())
    )
    end_of_day = django_timezone.make_aware(
        datetime.combine(selected_date, datetime.max.time())
    )

    # Get all employees
    all_employees = Employee.objects.all()
    total_employees = all_employees.count()

    # Get clock events for the selected day
    clock_events = Event.objects.filter(
        timestamp__range=(start_of_day, end_of_day),
        event_type__name__in=["Clock In", "Clock Out"],
    ).select_related("employee", "event_type")

    # Determine which employees are clocked in
    clocked_in_employees = set()
    for employee in all_employees:
        if employee.is_clocked_in():
            clocked_in_employees.add(employee.id)

    clocked_in_count = len(clocked_in_employees)
    not_clocked_in_count = total_employees - clocked_in_count

    # Create a basic HTML report
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Daily Attendance Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            .summary {{ display: flex; justify-content: space-between; margin-bottom: 30px; }}
            .stat-box {{ background-color: #f5f5f5; border-radius: 8px; padding: 15px; width: 30%; text-align: center; }}
            .stat-value {{ font-size: 28px; font-weight: bold; margin: 10px 0; }}
            .stat-label {{ font-size: 14px; color: #666; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .clocked-in {{ background-color: #e6ffe6; }}
            .not-clocked-in {{ background-color: #ffe6e6; }}
            h1, h2 {{ color: #333; }}
        </style>
    </head>
    <body>
        <h1>Daily Attendance Dashboard</h1>
        <p>Date: {selected_date.strftime("%A, %B %d, %Y")}</p>

        <div class="summary">
            <div class="stat-box">
                <div class="stat-label">Total Employees</div>
                <div class="stat-value">{total_employees}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Currently Clocked In</div>
                <div class="stat-value">{clocked_in_count}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Not Clocked In</div>
                <div class="stat-value">{not_clocked_in_count}</div>
            </div>
        </div>

        <h2>Employee Attendance Status</h2>
        <table>
            <tr>
                <th>Employee</th>
                <th>Status</th>
                <th>Last Event</th>
            </tr>
    """

    # Add rows for each employee
    for employee in all_employees:
        status = (
            "Clocked In" if employee.id in clocked_in_employees else "Not Clocked In"
        )
        row_class = (
            "clocked-in" if employee.id in clocked_in_employees else "not-clocked-in"
        )

        # Get employee's last event
        last_event = (
            Event.objects.filter(
                employee=employee, event_type__name__in=["Clock In", "Clock Out"]
            )
            .order_by("-timestamp")
            .first()
        )

        last_event_info = (
            f"{last_event.event_type.name} at {django_timezone.localtime(last_event.timestamp).strftime('%H:%M')} on {django_timezone.localtime(last_event.timestamp).strftime('%Y-%m-%d')}"
            if last_event
            else "No events recorded"
        )

        html += f"""
            <tr class="{row_class}">
                <td>{employee.given_name} {employee.surname}</td>
                <td>{status}</td>
                <td>{last_event_info}</td>
            </tr>
        """

    html += """
        </table>
    </body>
    </html>
    """

    # Create data for the heatmap - Attendance by hour and department
    departments = ["Administration", "Engineering", "Sales", "Support", "Marketing"]
    hours = list(range(7, 19))  # 7 AM to 6 PM

    # Initialize the heatmap data
    heatmap_data = []
    for dept in departments:
        heatmap_data.append([0] * len(hours))

    # Get department for each employee (assuming a department field or property)
    # You'll need to adapt this to your actual data model
    employee_departments = {}
    for employee in all_employees:
        # Assign each employee to a department - modify this based on your model
        dept = getattr(employee, "department", "Administration")
        if dept not in departments:
            dept = "Administration"
        employee_departments[employee.id] = dept

    # Count clock-ins by hour and department
    for event in clock_events:
        if event.event_type.name == "Clock In":
            # Convert to local timezone for hour calculation
            local_timestamp = django_timezone.localtime(event.timestamp)
            hour = local_timestamp.hour
            if 7 <= hour <= 18:  # Only count hours in our range
                dept = employee_departments.get(event.employee.id, "Administration")
                dept_idx = departments.index(dept)
                hour_idx = hours.index(hour)
                heatmap_data[dept_idx][hour_idx] += 1

    # Create Plotly heatmap
    heatmap_plot = {
        "z": heatmap_data,
        "x": [f"{h}:00" for h in hours],
        "y": departments,
        "type": "heatmap",
        "colorscale": "Viridis",
    }

    heatmap_layout = {
        "title": "Clock-ins by Hour and Department",
        "xaxis": {"title": "Hour of Day"},
        "yaxis": {"title": "Department"},
    }

    heatmap_json = json.dumps({"data": [heatmap_plot], "layout": heatmap_layout})

    # Insert this before the employee table in your HTML
    html += f"""
    <h2>Attendance Patterns</h2>
    <div id="heatmap" style="height: 400px;"></div>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script>
        var heatmapData = {heatmap_json};
        Plotly.newPlot('heatmap', heatmapData.data, heatmapData.layout);
    </script>
    """

    return HttpResponse(html, content_type="text/html")


def generate_employee_history_html(request, employee_id, start_date, end_date):
    """Generate HTML report for employee attendance history"""
    try:
        # Get employee
        employee = get_object_or_404(Employee, id=employee_id)

        # Convert to datetime objects for filtering
        start_datetime = django_timezone.make_aware(
            datetime.combine(start_date, datetime.min.time())
        )
        end_datetime = django_timezone.make_aware(
            datetime.combine(end_date, datetime.min.time())
        )

        # Get employee events
        events = (
            Event.objects.filter(
                employee=employee, timestamp__range=(start_datetime, end_datetime)
            )
            .select_related("event_type", "location")
            .order_by("timestamp")
        )

        # Process events to calculate hours
        event_days = {}
        clock_in_time = None
        total_hours = 0

        for event in events:
            # Convert to local timezone for date calculation
            local_timestamp = django_timezone.localtime(event.timestamp)
            event_date = local_timestamp.date()
            if event_date not in event_days:
                event_days[event_date] = {
                    "date": event_date,
                    "clock_in": None,
                    "clock_out": None,
                    "hours": 0,
                }

            if event.event_type.name == "Clock In":
                event_days[event_date]["clock_in"] = event.timestamp
                clock_in_time = event.timestamp
            elif event.event_type.name == "Clock Out" and clock_in_time:
                event_days[event_date]["clock_out"] = event.timestamp
                hours = (event.timestamp - clock_in_time).total_seconds() / 3600
                event_days[event_date]["hours"] = round(hours, 2)
                total_hours += hours
                clock_in_time = None

        # Prepare data for charts
        dates = []
        hours_worked = []
        calendar_data = []

        # Sort days by date
        for date_key in sorted(event_days.keys()):
            day = event_days[date_key]
            dates.append(date_key.strftime("%Y-%m-%d"))
            hours_worked.append(day["hours"])

            # Calendar data needs z-value (intensity)
            calendar_data.append(
                {"date": date_key.strftime("%Y-%m-%d"), "hours": day["hours"]}
            )

        # Create bar chart for hours worked
        bar_chart = {
            "x": dates,
            "y": hours_worked,
            "type": "bar",
            "marker": {"color": "rgba(58, 171, 210, 0.8)"},
            "name": "Hours Worked",
        }

        bar_layout = {
            "title": f"Daily Hours Worked for {employee.given_name} {employee.surname}",
            "xaxis": {"title": "Date"},
            "yaxis": {"title": "Hours"},
            "margin": {"l": 50, "r": 50, "b": 100, "t": 50, "pad": 4},
        }

        # Convert data to JSON for the template
        bar_chart_json = json.dumps({"data": [bar_chart], "layout": bar_layout})

        # Calendar heatmap - this is a bit more complex in Plotly
        # We'll create a function to generate calendar heatmap data
        def generate_calendar_data(calendar_data, start_date, end_date):
            # Generate all dates in range
            all_dates = []
            curr_date = start_date
            while curr_date < end_date:
                all_dates.append(curr_date.strftime("%Y-%m-%d"))
                curr_date += timedelta(days=1)

            # Map of date to hours
            hours_by_date = {item["date"]: item["hours"] for item in calendar_data}

            # Create a list of weeks
            weeks = []
            current_week = []

            # Get the weekday of the start date (0 is Monday in Python's datetime)
            start_weekday = start_date.weekday()

            # Add empty days before the start date
            for _ in range(start_weekday):
                current_week.append(None)

            for date_str in all_dates:
                current_week.append(hours_by_date.get(date_str, 0))

                # If we reach Sunday (6), start a new week
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                if date_obj.weekday() == 6:
                    weeks.append(current_week)
                    current_week = []

            # Add any remaining days
            if current_week:
                while len(current_week) < 7:
                    current_week.append(None)
                weeks.append(current_week)

            return weeks

        calendar_weeks = generate_calendar_data(
            calendar_data, start_date, end_date - timedelta(days=1)
        )

        # Create a heatmap for the calendar view
        calendar_plot = {
            "z": calendar_weeks,
            "x": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "y": [f"Week {i + 1}" for i in range(len(calendar_weeks))],
            "type": "heatmap",
            "colorscale": [
                [0, "rgb(255,255,255)"],  # No hours = white
                [0.1, "rgb(220,237,252)"],
                [0.5, "rgb(66,146,198)"],
                [1, "rgb(8,48,107)"],  # Max hours = dark blue
            ],
            "showscale": True,
        }

        calendar_layout = {
            "title": "Attendance Calendar",
            "margin": {"l": 50, "r": 50, "b": 50, "t": 50, "pad": 4},
        }

        calendar_json = json.dumps({"data": [calendar_plot], "layout": calendar_layout})

        # Create HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Employee Attendance History</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .employee-info {{ margin-bottom: 30px; }}
                .summary {{ display: flex; margin-bottom: 30px; }}
                .stat-box {{ background-color: #f5f5f5; border-radius: 8px; padding: 15px; margin-right: 20px; text-align: center; }}
                .stat-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
                .stat-label {{ font-size: 14px; color: #666; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                h1, h2 {{ color: #333; }}
            </style>
        </head>
        <body>
            <h1>Employee Attendance History</h1>

            <div class="employee-info">
                <h2>{employee.given_name} {employee.surname}</h2>
                <p>Report period: {start_date.strftime("%Y-%m-%d")} to {(end_date - timedelta(days=1)).strftime("%Y-%m-%d")}</p>
            </div>

            <div class="summary">
                <div class="stat-box">
                    <div class="stat-label">Total Days</div>
                    <div class="stat-value">{len(event_days)}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Total Hours</div>
                    <div class="stat-value">{round(total_hours, 2)}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Average Hours/Day</div>
                    <div class="stat-value">{round(total_hours / len(event_days), 2) if event_days else 0}</div>
                </div>
            </div>

            <h2>Hours Overview</h2>
            <div id="barChart" style="height: 300px;"></div>

            <h2>Attendance Calendar</h2>
            <div id="calendarHeatmap" style="height: 400px;"></div>

            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <script>
                var barChartData = {bar_chart_json};
                Plotly.newPlot('barChart', barChartData.data, barChartData.layout);

                var calendarData = {calendar_json};
                Plotly.newPlot('calendarHeatmap', calendarData.data, calendarData.layout);
            </script>
        </body>
        </html>
        """

        return HttpResponse(html, content_type="text/html")

    except Exception as e:
        return HttpResponse(
            f"Error generating employee history report: {str(e)}", status=500
        )


def generate_period_summary_html(
    request, period_type, start_date, end_date, start_time_str, end_time_str
):
    """Generate HTML report for attendance summary by period"""
    try:
        # Convert time strings to time objects
        try:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
        except ValueError:
            start_time = datetime.strptime("09:00", "%H:%M").time()
            end_time = datetime.strptime("17:00", "%H:%M").time()

        # Full date range
        start_datetime = django_timezone.make_aware(
            datetime.combine(start_date, datetime.min.time())
        )
        end_datetime = django_timezone.make_aware(
            datetime.combine(end_date, datetime.min.time())
        )

        # Get all events in the date range
        events = Event.objects.filter(
            timestamp__range=(start_datetime, end_datetime),
            event_type__name__in=["Clock In", "Clock Out"],
        ).select_related("employee", "event_type")

        # Group events by period and employee
        period_data = {}

        # Define period boundaries
        if period_type == "day":
            # For daily, each day is a period
            current_date = start_date
            while current_date < end_date:
                period_data[current_date] = {
                    "label": current_date.strftime("%Y-%m-%d"),
                    "employees": {},
                }
                current_date += timedelta(days=1)

        elif period_type == "week":
            # For weekly, group by calendar week
            current_date = start_date
            while current_date < end_date:
                # Find start of the week (Monday)
                week_start = current_date - timedelta(days=current_date.weekday())
                week_label = f"Week {week_start.strftime('%Y-%m-%d')}"

                if week_label not in period_data:
                    period_data[week_label] = {"label": week_label, "employees": {}}

                current_date += timedelta(days=1)

        elif period_type == "month":
            # For monthly, group by calendar month
            current_date = start_date
            while current_date < end_date:
                month_label = current_date.strftime("%Y-%m")

                if month_label not in period_data:
                    period_data[month_label] = {"label": month_label, "employees": {}}

                current_date += timedelta(days=1)

        # Process all events
        for event in events:
            employee_id = event.employee.id
            employee_name = f"{event.employee.given_name} {event.employee.surname}"
            # Convert to local timezone for date and time calculations
            local_timestamp = django_timezone.localtime(event.timestamp)
            event_date = local_timestamp.date()
            event_time = local_timestamp.time()

            # Determine which period this event belongs to
            if period_type == "day":
                period_key = event_date
            elif period_type == "week":
                week_start = event_date - timedelta(days=event_date.weekday())
                period_key = f"Week {week_start.strftime('%Y-%m-%d')}"
            elif period_type == "month":
                period_key = event_date.strftime("%Y-%m")

            # Skip if period not in our range
            if period_key not in period_data:
                continue

            # Initialize employee data in this period if needed
            if employee_id not in period_data[period_key]["employees"]:
                period_data[period_key]["employees"][employee_id] = {
                    "name": employee_name,
                    "first_clock_in": None,
                    "last_clock_out": None,
                    "hours": 0,
                    "late_arrivals": 0,
                    "early_departures": 0,
                }

            # Update employee data
            emp_data = period_data[period_key]["employees"][employee_id]

            if event.event_type.name == "Clock In":
                # Check if this is the first clock in for the day
                if (
                    emp_data["first_clock_in"] is None
                    or event.timestamp.date() != emp_data["first_clock_in"].date()
                ):
                    emp_data["first_clock_in"] = event.timestamp

                    # Check if late arrival
                    if event_time > start_time:
                        emp_data["late_arrivals"] += 1

            elif event.event_type.name == "Clock Out":
                # Update last clock out
                if (
                    emp_data["last_clock_out"] is None
                    or event.timestamp > emp_data["last_clock_out"]
                ):
                    emp_data["last_clock_out"] = event.timestamp

                    # Check if early departure
                    if event_time < end_time:
                        emp_data["early_departures"] += 1

        # Calculate hours worked for each employee in each period
        for period_key in sorted(period_data.keys()):
            for employee_id, emp_data in period_data[period_key]["employees"].items():
                if emp_data["first_clock_in"] and emp_data["last_clock_out"]:
                    # Calculate hours between first clock in and last clock out
                    hours = (
                        emp_data["last_clock_out"] - emp_data["first_clock_in"]
                    ).total_seconds() / 3600
                    emp_data["hours"] = round(hours, 2)

        # Prepare data for stacked bar chart
        periods = []
        stacked_data = {}  # Employee -> hours for each period

        # Collect data for each period
        for period_key in sorted(period_data.keys()):
            period = period_data[period_key]
            if not period["employees"]:
                continue

            periods.append(period["label"])

            # Add hours for each employee
            for employee_id, emp_data in period["employees"].items():
                employee_name = emp_data["name"]
                if employee_name not in stacked_data:
                    stacked_data[employee_name] = []

                # Find the correct position in the array
                while len(stacked_data[employee_name]) < len(periods) - 1:
                    stacked_data[employee_name].append(0)

                stacked_data[employee_name].append(emp_data["hours"])

        # Create traces for each employee
        stacked_bar_traces = []
        for employee_name, hours in stacked_data.items():
            # Fill in zeros for missing periods
            while len(hours) < len(periods):
                hours.append(0)

            trace = {"x": periods, "y": hours, "type": "bar", "name": employee_name}
            stacked_bar_traces.append(trace)

        # Define period_name before using it
        period_name = {"day": "Daily", "week": "Weekly", "month": "Monthly"}[
            period_type
        ]

        stacked_layout = {
            "title": f"{period_name} Hours Worked by Employee",
            "barmode": "stack",
            "xaxis": {"title": period_name},
            "yaxis": {"title": "Hours"},
            "margin": {"l": 50, "r": 50, "b": 100, "t": 50, "pad": 4},
        }

        stacked_json = json.dumps(
            {"data": stacked_bar_traces, "layout": stacked_layout}
        )

        # Also create a trend line for late/early occurrences
        late_trend = []
        early_trend = []

        for period_key in sorted(period_data.keys()):
            period = period_data[period_key]
            if not period["employees"]:
                continue

            # Sum up late arrivals and early departures
            late_count = sum(
                emp_data["late_arrivals"]
                for emp_id, emp_data in period["employees"].items()
            )
            early_count = sum(
                emp_data["early_departures"]
                for emp_id, emp_data in period["employees"].items()
            )

            late_trend.append(late_count)
            early_trend.append(early_count)

        trend_traces = [
            {
                "x": periods,
                "y": late_trend,
                "type": "scatter",
                "mode": "lines+markers",
                "name": "Late Arrivals",
                "line": {"color": "red"},
            },
            {
                "x": periods,
                "y": early_trend,
                "type": "scatter",
                "mode": "lines+markers",
                "name": "Early Departures",
                "line": {"color": "orange"},
            },
        ]

        trend_layout = {
            "title": "Punctuality Trends",
            "xaxis": {"title": period_name},
            "yaxis": {"title": "Count"},
            "margin": {"l": 50, "r": 50, "b": 100, "t": 50, "pad": 4},
        }

        trend_json = json.dumps({"data": trend_traces, "layout": trend_layout})

        # Create HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{period_name} Attendance Summary</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .summary {{ margin-bottom: 30px; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 30px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                h1, h2 {{ color: #333; }}
                .late {{ color: #e74c3c; }}
                .early {{ color: #e67e22; }}
            </style>
        </head>
        <body>
            <h1>{period_name} Attendance Summary</h1>
            <p>Period: {start_date.strftime("%Y-%m-%d")} to {(end_date - timedelta(days=1)).strftime("%Y-%m-%d")}</p>
            <p>Standard hours: {start_time_str} to {end_time_str}</p>
        """

        # Create a table for each period
        for period_key in sorted(period_data.keys()):
            period = period_data[period_key]

            if not period["employees"]:
                continue

            html += f"""
                <h2>{period["label"]}</h2>
                <table>
                    <tr>
                        <th>Employee</th>
                        <th>First Clock In</th>
                        <th>Last Clock Out</th>
                        <th>Hours</th>
                        <th>Late Arrivals</th>
                        <th>Early Departures</th>
                    </tr>
            """

            # Add rows for each employee
            for employee_id, emp_data in sorted(
                period["employees"].items(), key=lambda x: x[1]["name"]
            ):
                first_in = (
                    django_timezone.localtime(emp_data["first_clock_in"]).strftime("%Y-%m-%d %H:%M")
                    if emp_data["first_clock_in"]
                    else "—"
                )
                last_out = (
                    django_timezone.localtime(emp_data["last_clock_out"]).strftime("%Y-%m-%d %H:%M")
                    if emp_data["last_clock_out"]
                    else "—"
                )

                late_class = " class='late'" if emp_data["late_arrivals"] > 0 else ""
                early_class = (
                    " class='early'" if emp_data["early_departures"] > 0 else ""
                )

                html += f"""
                    <tr>
                        <td>{emp_data["name"]}</td>
                        <td>{first_in}</td>
                        <td>{last_out}</td>
                        <td>{emp_data["hours"]}</td>
                        <td{late_class}>{emp_data["late_arrivals"]}</td>
                        <td{early_class}>{emp_data["early_departures"]}</td>
                    </tr>
                """

            html += """
                </table>
            """

        html += f"""
        <div id="stackedBar" style="height: 400px;"></div>
        <div id="trendLines" style="height: 300px;"></div>

        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <script>
            var stackedData = {stacked_json};
            Plotly.newPlot('stackedBar', stackedData.data, stackedData.layout);

            var trendData = {trend_json};
            Plotly.newPlot('trendLines', trendData.data, trendData.layout);
        </script>
        """

        html += """
        </body>
        </html>
        """

        return HttpResponse(html, content_type="text/html")

    except Exception as e:
        error_msg = f"Error generating period summary report: {str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)  # Log the full error to the console
        return HttpResponse(
            f"Error generating period summary report: {str(e)}", status=500
        )



    """Generate HTML report for late arrivals and early departures"""
    try:
        # Convert time strings to time objects
        try:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
        except ValueError:
            start_time = datetime.strptime("09:00", "%H:%M").time()
            end_time = datetime.strptime("17:00", "%H:%M").time()

        # Full date range
        start_datetime = django_timezone.make_aware(
            datetime.combine(start_date, datetime.min.time())
        )
        end_datetime = django_timezone.make_aware(
            datetime.combine(end_date, datetime.min.time())
        )

        # Get all clock events in the date range
        events = Event.objects.filter(
            timestamp__range=(start_datetime, end_datetime),
            event_type__name__in=["Clock In", "Clock Out"],
        ).select_related("employee", "event_type")

        # Process events to find late arrivals and early departures
        late_arrivals = []
        early_departures = []

        for event in events:
            local_timestamp = django_timezone.localtime(event.timestamp)
            event_time = local_timestamp.time()
            employee_name = f"{event.employee.given_name} {event.employee.surname}"

            if event.event_type.name == "Clock In":
                if event_time > start_time:
                    # Calculate minutes late
                    minutes_late = (
                        datetime.combine(date.min, event_time)
                        - datetime.combine(date.min, start_time)
                    ).total_seconds() / 60

                    if minutes_late >= late_threshold:
                        late_arrivals.append(
                            {
                                "employee_name": employee_name,
                                "date": event.timestamp.date(),
                                "time": event_time,
                                "minutes_late": int(minutes_late),
                            }
                        )

            elif event.event_type.name == "Clock Out":
                if event_time < end_time:
                    # Calculate minutes early
                    minutes_early = (
                        datetime.combine(date.min, end_time)
                        - datetime.combine(date.min, event_time)
                    ).total_seconds() / 60

                    if minutes_early >= early_threshold:
                        early_departures.append(
                            {
                                "employee_name": employee_name,
                                "date": event.timestamp.date(),
                                "time": event_time,
                                "minutes_early": int(minutes_early),
                            }
                        )

        # Sort by date
        late_arrivals.sort(key=lambda x: (x["date"], x["minutes_late"]), reverse=True)
        early_departures.sort(
            key=lambda x: (x["date"], x["minutes_early"]), reverse=True
        )

        # Prepare data for timeline visualization
        timeline_data = []

        # Add late arrivals
        for late in late_arrivals:
            timeline_data.append(
                {
                    "date": late["date"].strftime("%Y-%m-%d"),
                    "time": late["time"].strftime("%H:%M"),
                    "minutes": late["minutes_late"],
                    "employee": late["employee_name"],
                    "type": "Late Arrival",
                }
            )

        # Add early departures
        for early in early_departures:
            timeline_data.append(
                {
                    "date": early["date"].strftime("%Y-%m-%d"),
                    "time": early["time"].strftime("%H:%M"),
                    "minutes": early["minutes_early"],
                    "employee": early["employee_name"],
                    "type": "Early Departure",
                }
            )

        # Sort by date
        timeline_data.sort(key=lambda x: x["date"])

        # Group by date
        timeline_dates = sorted(set(item["date"] for item in timeline_data))

        # Create a histogram by day of week
        weekday_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        late_by_weekday = [0] * 7
        early_by_weekday = [0] * 7

        for item in timeline_data:
            date_obj = datetime.strptime(item["date"], "%Y-%m-%d").date()
            weekday = date_obj.weekday()  # 0 = Monday, 6 = Sunday

            if item["type"] == "Late Arrival":
                late_by_weekday[weekday] += 1
            else:
                early_by_weekday[weekday] += 1

        # Create the weekday histogram
        weekday_traces = [
            {
                "x": weekday_names,
                "y": late_by_weekday,
                "type": "bar",
                "name": "Late Arrivals",
                "marker": {"color": "rgba(231, 76, 60, 0.8)"},
            },
            {
                "x": weekday_names,
                "y": early_by_weekday,
                "type": "bar",
                "name": "Early Departures",
                "marker": {"color": "rgba(230, 126, 34, 0.8)"},
            },
        ]

        weekday_layout = {
            "title": "Events by Day of Week",
            "barmode": "group",
            "xaxis": {"title": "Day of Week"},
            "yaxis": {"title": "Number of Events"},
            "margin": {"l": 50, "r": 50, "b": 50, "t": 50, "pad": 4},
        }

        weekday_json = json.dumps({"data": weekday_traces, "layout": weekday_layout})

        # Create a timeline showing events over the date range
        timeline_traces = []

        # Add trace for late arrivals
        late_dates = [
            item["date"] for item in timeline_data if item["type"] == "Late Arrival"
        ]
        late_employees = [
            item["employee"] for item in timeline_data if item["type"] == "Late Arrival"
        ]
        late_minutes = [
            item["minutes"] for item in timeline_data if item["type"] == "Late Arrival"
        ]

        if late_dates:
            timeline_traces.append(
                {
                    "x": late_dates,
                    "y": late_employees,
                    "mode": "markers",
                    "marker": {
                        "color": "red",
                        "size": [min(m, 30) for m in late_minutes],  # Cap size at 30px
                        "opacity": 0.7,
                    },
                    "text": [f"{m} minutes late" for m in late_minutes],
                    "name": "Late Arrivals",
                }
            )

        # Add trace for early departures
        early_dates = [
            item["date"] for item in timeline_data if item["type"] == "Early Departure"
        ]
        early_employees = [
            item["employee"]
            for item in timeline_data
            if item["type"] == "Early Departure"
        ]
        early_minutes = [
            item["minutes"]
            for item in timeline_data
            if item["type"] == "Early Departure"
        ]

        if early_dates:
            timeline_traces.append(
                {
                    "x": early_dates,
                    "y": early_employees,
                    "mode": "markers",
                    "marker": {
                        "color": "orange",
                        "size": [min(m, 30) for m in early_minutes],  # Cap size at 30px
                        "opacity": 0.7,
                    },
                    "text": [f"{m} minutes early" for m in early_minutes],
                    "name": "Early Departures",
                }
            )

        timeline_layout = {
            "title": "Punctuality Timeline",
            "xaxis": {"title": "Date"},
            "yaxis": {"title": "Employee"},
            "margin": {"l": 150, "r": 50, "b": 50, "t": 50, "pad": 4},
            "height": 500,
        }

        timeline_json = json.dumps({"data": timeline_traces, "layout": timeline_layout})

        # Create HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Late Arrival and Early Departure Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .summary {{ display: flex; margin-bottom: 30px; }}
                .stat-box {{ background-color: #f5f5f5; border-radius: 8px; padding: 15px; margin-right: 20px; text-align: center; }}
                .stat-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
                .stat-label {{ font-size: 14px; color: #666; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 30px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                h1, h2 {{ color: #333; }}
                .late {{ background-color: #ffeaea; }}
                .early {{ background-color: #fff5ea; }}
            </style>
        </head>
        <body>
            <h1>Late Arrival and Early Departure Report</h1>
            <p>Period: {start_date.strftime("%Y-%m-%d")} to {(end_date - timedelta(days=1)).strftime("%Y-%m-%d")}</p>
            <p>Standard hours: {start_time_str} to {end_time_str}</p>
            <p>Thresholds: Late {late_threshold} minutes, Early {early_threshold} minutes</p>

            <div class="summary">
                <div class="stat-box">
                    <div class="stat-label">Total Late Arrivals</div>
                    <div class="stat-value">{len(late_arrivals)}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Total Early Departures</div>
                    <div class="stat-value">{len(early_departures)}</div>
                </div>
            </div>

            <h2>Punctuality Patterns</h2>
            <div id="weekdayChart" style="height: 300px;"></div>

            <h2>Timeline View</h2>
            <div id="timelineChart" style="height: 500px;"></div>

            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <script>
                var weekdayData = {weekday_json};
                Plotly.newPlot('weekdayChart', weekdayData.data, weekdayData.layout);

                var timelineData = {timeline_json};
                Plotly.newPlot('timelineChart', timelineData.data, timelineData.layout);
            </script>
        </body>
        </html>
        """

        return HttpResponse(html, content_type="text/html")

    except Exception as e:
        return HttpResponse(f"Error generating late/early report: {str(e)}", status=500)


# --- Health Check Views ---
# No login required, no permissions needed for a basic health check
# Exclude from schema if using drf-spectacular


@extend_schema(exclude=True)
def health_check(request):
    """
    Basic health check endpoint. Returns HTTP 200 OK if the app is running.
    """
    try:
        connections["default"].cursor()
    except Exception as e:
        return HttpResponse("Database unavailable", status=503)

    return HttpResponse("OK", status=200)


def employee_history_report_csv(request):
    """Download employee attendance history as CSV"""
    employee_id = request.GET.get("employee_id")
    start_date = request.GET.get(
        "start_date", (django_timezone.now() - timedelta(days=30)).date().isoformat()
    )
    end_date = request.GET.get("end_date", django_timezone.now().date().isoformat())
    if not employee_id:
        return HttpResponseBadRequest("Employee ID is required")
    try:
        start_date = datetime.fromisoformat(start_date).date()
        end_date = datetime.fromisoformat(end_date).date()
    except ValueError:
        return HttpResponseBadRequest("Invalid date format")
    employee = get_object_or_404(Employee, id=employee_id)
    start_datetime = django_timezone.make_aware(
        datetime.combine(start_date, datetime.min.time())
    )
    end_datetime = django_timezone.make_aware(datetime.combine(end_date, datetime.min.time()))
    events = (
        Event.objects.filter(
            employee=employee, timestamp__range=(start_datetime, end_datetime)
        )
        .select_related("event_type", "location")
        .order_by("timestamp")
    )

    def row_gen():
        yield ["Date", "Clock In", "Clock Out", "Hours"]
        event_days = {}
        clock_in_time = None
        for event in events:
            # Convert to local timezone for date calculation
            local_timestamp = django_timezone.localtime(event.timestamp)
            event_date = local_timestamp.date()
            if event_date not in event_days:
                event_days[event_date] = {
                    "clock_in": None,
                    "clock_out": None,
                    "hours": 0,
                }
            if event.event_type.name == "Clock In":
                event_days[event_date]["clock_in"] = event.timestamp
                clock_in_time = event.timestamp
            elif event.event_type.name == "Clock Out" and clock_in_time:
                event_days[event_date]["clock_out"] = event.timestamp
                hours = (event.timestamp - clock_in_time).total_seconds() / 3600
                event_days[event_date]["hours"] = round(hours, 2)
                clock_in_time = None
        for date_key in sorted(event_days.keys()):
            day = event_days[date_key]
            yield [
                date_key.strftime("%Y-%m-%d"),
                django_timezone.localtime(day["clock_in"]).strftime("%H:%M") if day["clock_in"] else "",
                django_timezone.localtime(day["clock_out"]).strftime("%H:%M") if day["clock_out"] else "",
                day["hours"],
            ]

    response = StreamingHttpResponse(
        (",".join(map(str, row)) + "\n" for row in row_gen()), content_type="text/csv"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="employee_history_{employee_id}.csv"'
    )
    return response


def period_summary_report_csv(request):
    """Download period summary as CSV"""
    period = request.GET.get("period", "day")
    start_date = request.GET.get("start_date", django_timezone.now().date().isoformat())
    start_time = request.GET.get("start_time", "09:00")
    end_time = request.GET.get("end_time", "17:00")
    try:
        start_date = datetime.fromisoformat(start_date).date()
        end_date = django_timezone.now().date()
    except ValueError:
        return HttpResponseBadRequest("Invalid date format")
    end_date = request.GET.get("end_date", end_date.isoformat())
    try:
        end_date = datetime.fromisoformat(end_date).date()
    except ValueError:
        return HttpResponseBadRequest("Invalid end date format")
    start_datetime = django_timezone.make_aware(
        datetime.combine(start_date, datetime.min.time())
    )
    end_datetime = django_timezone.make_aware(datetime.combine(end_date, datetime.min.time()))
    events = Event.objects.filter(
        timestamp__range=(start_datetime, end_datetime),
        event_type__name__in=["Clock In", "Clock Out"],
    ).select_related("employee", "event_type")
    # Group events by period and employee
    period_data = {}
    if period == "day":
        current_date = start_date
        while current_date < end_date:
            period_data[current_date] = {}
            current_date += timedelta(days=1)
    elif period == "week":
        current_date = start_date
        while current_date < end_date:
            week_start = current_date - timedelta(days=current_date.weekday())
            if week_start not in period_data:
                period_data[week_start] = {}
            current_date += timedelta(days=1)
    elif period == "month":
        current_date = start_date
        while current_date < end_date:
            month_start = current_date.replace(day=1)
            if month_start not in period_data:
                period_data[month_start] = {}
            current_date += timedelta(days=1)
    for event in events:
        employee_id = event.employee.id
        employee_name = f"{event.employee.given_name} {event.employee.surname}"
        # Convert to local timezone for date calculation
        local_timestamp = django_timezone.localtime(event.timestamp)
        event_date = local_timestamp.date()
        if period == "day":
            period_key = event_date
        elif period == "week":
            period_key = event_date - timedelta(days=event_date.weekday())
        elif period == "month":
            period_key = event_date.replace(day=1)
        if period_key not in period_data:
            continue
        if employee_id not in period_data[period_key]:
            period_data[period_key][employee_id] = {
                "name": employee_name,
                "first_clock_in": None,
                "last_clock_out": None,
                "hours": 0,
            }
        emp_data = period_data[period_key][employee_id]
        if event.event_type.name == "Clock In":
            if (
                emp_data["first_clock_in"] is None
                or event.timestamp < emp_data["first_clock_in"]
            ):
                emp_data["first_clock_in"] = event.timestamp
        elif event.event_type.name == "Clock Out":
            if (
                emp_data["last_clock_out"] is None
                or event.timestamp > emp_data["last_clock_out"]
            ):
                emp_data["last_clock_out"] = event.timestamp
    for period_key in period_data:
        for emp_id, emp_data in period_data[period_key].items():
            if emp_data["first_clock_in"] and emp_data["last_clock_out"]:
                hours = (
                    emp_data["last_clock_out"] - emp_data["first_clock_in"]
                ).total_seconds() / 3600
                emp_data["hours"] = round(hours, 2)

    def row_gen():
        yield ["Period", "Employee", "First Clock In", "Last Clock Out", "Hours"]
        for period_key in sorted(period_data.keys()):
            for emp_id, emp_data in period_data[period_key].items():
                yield [
                    str(period_key),
                    emp_data["name"],
                    django_timezone.localtime(emp_data["first_clock_in"]).strftime("%Y-%m-%d %H:%M")
                    if emp_data["first_clock_in"]
                    else "",
                    django_timezone.localtime(emp_data["last_clock_out"]).strftime("%Y-%m-%d %H:%M")
                    if emp_data["last_clock_out"]
                    else "",
                    emp_data["hours"],
                ]

    response = StreamingHttpResponse(
        (",".join(map(str, row)) + "\n" for row in row_gen()), content_type="text/csv"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="period_summary_{period}.csv"'
    )
    return response





@attendance_required  # Attendance management role and above
def attendance_entry(request):
    """Single day attendance entry form"""
    if request.method == 'POST':
        form = AttendanceRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.created_by = request.user
            record.save()
            messages.success(request, f"Attendance record saved for {record.employee} on {record.date}")
            return redirect('attendance_list')
    else:
        form = AttendanceRecordForm()
    
    return render(request, 'attendance/entry_form.html', {'form': form})


@attendance_required  # Attendance management role and above
def attendance_edit(request, record_id):
    """Edit existing attendance record"""
    record = get_object_or_404(AttendanceRecord, id=record_id)
    
    if request.method == 'POST':
        form = AttendanceRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, f"Attendance record updated for {record.employee} on {record.date}")
            return redirect('attendance_list')
    else:
        form = AttendanceRecordForm(instance=record)
    
    return render(request, 'attendance/edit_form.html', {'form': form, 'record': record})


@attendance_required  # Attendance management role and above
def attendance_delete(request, record_id):
    """Delete attendance record"""
    record = get_object_or_404(AttendanceRecord, id=record_id)
    
    if request.method == 'POST':
        employee_name = str(record.employee)
        date_str = record.date.strftime('%Y-%m-%d')
        record.delete()
        messages.success(request, f"Attendance record deleted for {employee_name} on {date_str}")
        return redirect('attendance_list')
    
    return render(request, 'attendance/delete_confirm.html', {'record': record})


@attendance_required  # Attendance management role and above
def bulk_historical_update(request):
    """Bulk update historical attendance records"""
    
    if request.method == 'POST':
        form = BulkHistoricalUpdateForm(request.POST)
        if form.is_valid():
            field_to_update = form.cleaned_data['field_to_update']
            new_value = form.cleaned_data['new_value']
            
            # Get the records to update from session or request
            record_ids = request.POST.getlist('record_ids')
            
            if not record_ids:
                messages.error(request, 'No records selected for update')
                return redirect('historical_progressive_entry')
            
            # Convert lunch time if needed
            if field_to_update == 'lunch_time' and new_value:
                try:
                    new_value = datetime.strptime(new_value, "%H:%M").time()
                except Exception:
                    new_value = None
            
            # Update the records
            updated_count = 0
            for record_id in record_ids:
                try:
                    record = AttendanceRecord.objects.get(id=record_id)
                    if hasattr(record, field_to_update):
                        setattr(record, field_to_update, new_value)
                        record.last_updated_by = request.user
                        record.save()
                        updated_count += 1
                except AttendanceRecord.DoesNotExist:
                    continue
            
            messages.success(request, f'Successfully updated {updated_count} records')
            return redirect('historical_progressive_entry')
    else:
        form = BulkHistoricalUpdateForm()
    
    context = {
        'form': form,
        'page_title': 'Bulk Historical Update',
    }
    
    return render(request, 'attendance/bulk_historical_update.html', context)


@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
@xframe_options_sameorigin
def comprehensive_attendance_report(request):
    """Comprehensive attendance report based on the CSV analysis format"""
    today = django_timezone.localtime(django_timezone.now()).date()
    
    # Get date range parameters
    start_date = request.GET.get('start_date', (today - timedelta(days=30)).isoformat())
    end_date = request.GET.get('end_date', today.isoformat())
    department_filter = request.GET.get('department', 'Digitization Tech')  # Default to Digitization Tech
    
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        start_date = today - timedelta(days=30)
        end_date = today
    
    # Get all employees
    employees = Employee.objects.filter(is_active=True).order_by('surname', 'given_name')
    
    # Apply department filter
    if department_filter:
        employees = filter_employees_by_department(employees, department_filter)
    
    # Calculate comprehensive attendance data for each employee
    employee_data = []
    
    for employee in employees:
        # Get attendance records for the date range
        records = AttendanceRecord.objects.filter(
            employee=employee,
            date__range=[start_date, end_date]
        )
        
        total_working_days = records.count()
        
        if total_working_days == 0:
            continue
        
        # Calculate problematic days (days with issues)
        problematic_days = 0
        standup_issues = 0
        return_lunch_issues = 0
        early_departure_issues = 0
        
        for record in records:
            # Check for problematic values
            problematic_values = ['NO', 'LATE']
            
            if record.standup_attendance in problematic_values:
                standup_issues += 1
            
            if record.returned_on_time_after_lunch in problematic_values:
                return_lunch_issues += 1
            
            if record.is_early_departure:
                early_departure_issues += 1
            
            # Count problematic days
            if record.is_problematic_day():
                problematic_days += 1
        
        non_problematic_days = total_working_days - problematic_days
        problematic_percentage = (problematic_days / total_working_days * 100) if total_working_days > 0 else 0
        non_problematic_percentage = (non_problematic_days / total_working_days * 100) if total_working_days > 0 else 0
        total_individual_issues = standup_issues + return_lunch_issues + early_departure_issues
        
        employee_data.append({
            'name': f"{employee.given_name} {employee.surname}",
            'total_working_days': total_working_days,
            'problematic_days': problematic_days,
            'problematic_percentage': round(problematic_percentage, 2),
            'non_problematic_days': non_problematic_days,
            'non_problematic_percentage': round(non_problematic_percentage, 2),
            'standup_issues': standup_issues,
            'return_lunch_issues': return_lunch_issues,
            'early_departure_issues': early_departure_issues,
            'total_individual_issues': total_individual_issues,
        })
    
    # Get sorting parameters
    sort_by = request.GET.get('sort', 'problematic_percentage')
    sort_direction = request.GET.get('direction', 'desc')
    
    # Sort data based on parameters
    reverse_sort = sort_direction == 'desc'
    if sort_by == 'name':
        employee_data.sort(key=lambda x: x['name'], reverse=reverse_sort)
    elif sort_by == 'total_working_days':
        employee_data.sort(key=lambda x: x['total_working_days'], reverse=reverse_sort)
    elif sort_by == 'problematic_days':
        employee_data.sort(key=lambda x: x['problematic_days'], reverse=reverse_sort)
    elif sort_by == 'total_individual_issues':
        employee_data.sort(key=lambda x: x['total_individual_issues'], reverse=reverse_sort)
    else:  # Default to problematic_percentage
        employee_data.sort(key=lambda x: x['problematic_percentage'], reverse=reverse_sort)
    
    # Calculate summary statistics
    total_employees = len(employee_data)
    avg_problematic_percentage = sum(e['problematic_percentage'] for e in employee_data) / total_employees if total_employees > 0 else 0
    total_issues = sum(e['total_individual_issues'] for e in employee_data)
    
    # Check if this is being loaded in an iframe
    is_iframe = request.GET.get('iframe', False) or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Get available departments for filter
    available_departments = get_available_departments()
    
    context = {
        'employee_data': employee_data,
        'start_date': start_date,
        'end_date': end_date,
        'department_filter': department_filter,
        'available_departments': available_departments,
        'total_employees': total_employees,
        'avg_problematic_percentage': round(avg_problematic_percentage, 2),
        'total_issues': total_issues,
        'is_iframe': is_iframe,
    }
    
    # Use different template for iframe to avoid navigation duplication
    if is_iframe:
        return render(request, 'reports/comprehensive_attendance_report_iframe.html', context)
    else:
        return render(request, 'reports/comprehensive_attendance_report.html', context)


def get_department_from_designation(designation):
    """
    Extract and normalize department from card designation.
    Returns the normalized department name or None if not found.
    """
    if not designation:
        return None
    
    # Extract department from designation (e.g., "Digitization Tech.1" -> "Digitization Tech")
    match = re.match(r'^([^.]+)', designation.strip())
    if match:
        raw_dept = match.group(1).strip()
        
        # Normalize department names to main departments
        dept = raw_dept.lower()
        
        # Map to main departments
        if ('digitization' in dept or 'digitzation' in dept) and 'tech' in dept:
            return 'Digitization Tech'
        elif 'digitization' in dept or 'digitzation' in dept:
            return 'Digitization Tech'
        elif 'tech' in dept and 'compute' in dept:
            return 'Tech Compute'
        elif 'tech' in dept or 'tch' in dept:
            return 'Tech Compute'
        elif 'con' in dept:
            return 'Con'
        elif 'custodian' in dept:
            return 'Custodian'
        elif 'material' in dept and 'retriever' in dept:
            return 'Material Retriever'
        elif 'material' in dept and 'retriver' in dept:
            return 'Material Retriever'
        elif 'admin' in dept:
            return 'Con'  # Map Admin to Con as specified
        else:
            # Return original if no match found
            return raw_dept
    return None

def get_available_departments():
    """
    Get list of all available departments from card designations.
    """
    departments = set()
    for card in Card.objects.all():
        dept = get_department_from_designation(card.designation)
        if dept:
            departments.add(dept)
    return sorted(list(departments))

def filter_employees_by_department(employees, department):
    """
    Filter employees by department using their card designation.
    """
    if not department:
        return employees
    
    filtered_employees = []
    for employee in employees:
        if employee.card_number:
            emp_dept = get_department_from_designation(employee.card_number.designation)
            if emp_dept == department:
                filtered_employees.append(employee)
    
    return filtered_employees


@admin_required  # Admin role only
@extend_schema(exclude=True)
def performance_dashboard(request):
    """Performance monitoring dashboard."""
    from .utils import get_performance_metrics, get_query_metrics, get_cache_metrics
    
    # Get performance metrics for key functions
    metrics = {
        'main_security': get_performance_metrics('main_security'),
        'progressive_entry': get_performance_metrics('progressive_entry'),
        'attendance_list': get_performance_metrics('attendance_list'),
    }
    
    # Get query metrics
    query_metrics = {
        'main_security': get_query_metrics('main_security'),
        'progressive_entry': get_query_metrics('progressive_entry'),
        'attendance_list': get_query_metrics('attendance_list'),
    }
    
    # Calculate overall performance stats
    total_calls = sum(m.get('count', 0) for m in metrics.values())
    total_time = sum(m.get('total_time', 0) for m in metrics.values())
    avg_time = total_time / total_calls if total_calls > 0 else 0
    
    # Calculate overall query stats
    total_queries = sum(qm.get('total_queries', 0) for qm in query_metrics.values())
    avg_queries = total_queries / total_calls if total_calls > 0 else 0
    
    context = {
        'metrics': metrics,
        'query_metrics': query_metrics,
        'total_calls': total_calls,
        'total_time': total_time,
        'avg_time': avg_time,
        'total_queries': total_queries,
        'avg_queries': avg_queries,
    }
    
    return render(request, 'performance_dashboard.html', context)


def custom_login(request):
    """Custom login view that redirects users to appropriate pages based on their role"""
    if request.user.is_authenticated:
        # User is already logged in, redirect based on role
        return redirect_based_on_role(request.user)
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect_based_on_role(user)
    else:
        form = AuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})


def redirect_based_on_role(user):
    """Redirect user to appropriate page based on their role"""
    try:
        user_role = user.userrole.role
        if user_role == 'reporting':
            return redirect('comprehensive_reports')
        elif user_role == 'attendance':
            return redirect('attendance_list')
        elif user_role == 'admin':
            return redirect('main_security')
        elif user_role == 'security':
            return redirect('main_security')
        else:
            return redirect('main_security')
    except:
        # If no role is assigned, redirect to main security
        return redirect('main_security')

# Real-time Analytics API Views
class RealTimeEmployeeStatusView(generics.ListAPIView):
    """API endpoint for real-time employee status data"""
    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]
    serializer_class = EmployeeSerializer
    
    def get_queryset(self):
        """Get current employee status with latest activity"""
        return Employee.objects.select_related('department').prefetch_related(
            'employee_events'
        ).filter(is_active=True)
    
    def get_serializer_context(self):
        """Add real-time context to serializer"""
        context = super().get_serializer_context()
        context['include_realtime_status'] = True
        return context

class LiveAttendanceCounterView(generics.RetrieveAPIView):
    """API endpoint for live attendance counter data"""
    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]
    serializer_class = EmployeeSerializer
    
    def get_object(self):
        """Return live attendance statistics"""
        from django.db.models import Count, Q
        
        today = django_timezone.localtime(django_timezone.now()).date()
        
        # Get total employees
        total_employees = Employee.objects.filter(is_active=True).count()
        
        # Get currently clocked in (have clock in event today, no clock out)
        clocked_in = Employee.objects.filter(
            is_active=True,
            employee_events__event_type__name='Clock In',
            employee_events__timestamp__date=today
        ).exclude(
            employee_events__event_type__name='Clock Out',
            employee_events__timestamp__date=today
        ).distinct().count()
        
        # Get currently clocked out
        clocked_out = total_employees - clocked_in
        
        # Calculate attendance rate
        attendance_rate = (clocked_in / total_employees * 100) if total_employees > 0 else 0
        
        return {
            'total_employees': total_employees,
            'currently_clocked_in': clocked_in,
            'currently_clocked_out': clocked_out,
            'attendance_rate': round(attendance_rate, 1),
            'last_updated': django_timezone.now()
        }
    
    def retrieve(self, request, *args, **kwargs):
        """Return live attendance data"""
        data = self.get_object()
        return Response(data)



@reporting_required
@extend_schema(exclude=True)
def realtime_analytics_dashboard(request):
    """
    Real-time analytics dashboard with live employee status and attendance analytics.
    This is the main dashboard for Phase 2 of the report enhancement roadmap.
    """
    context = {
        'page_title': 'Real-Time Analytics Dashboard',
        'active_tab': 'realtime_analytics',
    }
    return render(request, 'attendance/realtime_analytics_dashboard.html', context)

@reporting_required  # Reporting role and above
@extend_schema(exclude=True)
def comprehensive_attendance_export_csv(request):
    """Export comprehensive attendance report data to CSV with sorting capabilities"""
    today = django_timezone.localtime(django_timezone.now()).date()
    
    # Get parameters
    start_date = request.GET.get('start_date', (today - timedelta(days=30)).isoformat())
    end_date = request.GET.get('end_date', today.isoformat())
    department_filter = request.GET.get('department', 'Digitization Tech')
    sort_by = request.GET.get('sort', 'problematic_percentage')
    sort_direction = request.GET.get('direction', 'desc')
    
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        start_date = today - timedelta(days=30)
        end_date = today
    
    # Get all employees
    employees = Employee.objects.filter(is_active=True).order_by('surname', 'given_name')
    
    # Apply department filter
    if department_filter:
        employees = filter_employees_by_department(employees, department_filter)
    
    # Calculate comprehensive attendance data for each employee
    employee_data = []
    
    for employee in employees:
        # Get attendance records for the date range
        records = AttendanceRecord.objects.filter(
            employee=employee,
            date__range=[start_date, end_date]
        )
        
        total_working_days = records.count()
        
        if total_working_days == 0:
            continue
        
        # Calculate problematic days (days with issues)
        problematic_days = 0
        standup_issues = 0
        return_lunch_issues = 0
        early_departure_issues = 0
        
        for record in records:
            # Check for problematic values
            problematic_values = ['NO', 'LATE']
            
            if record.standup_attendance in problematic_values:
                standup_issues += 1
            
            if record.returned_on_time_after_lunch in problematic_values:
                return_lunch_issues += 1
            
            if record.is_early_departure:
                early_departure_issues += 1
            
            # Count problematic days
            if record.is_problematic_day():
                problematic_days += 1
        
        non_problematic_days = total_working_days - problematic_days
        problematic_percentage = (problematic_days / total_working_days * 100) if total_working_days > 0 else 0
        non_problematic_percentage = (non_problematic_days / total_working_days * 100) if total_working_days > 0 else 0
        total_individual_issues = standup_issues + return_lunch_issues + early_departure_issues
        
        employee_data.append({
            'name': f"{employee.given_name} {employee.surname}",
            'department': employee.department.name if employee.department else 'N/A',
            'total_working_days': total_working_days,
            'problematic_days': problematic_days,
            'problematic_percentage': round(problematic_percentage, 2),
            'non_problematic_days': non_problematic_days,
            'non_problematic_percentage': round(non_problematic_percentage, 2),
            'standup_issues': standup_issues,
            'return_lunch_issues': return_lunch_issues,
            'early_departure_issues': early_departure_issues,
            'total_individual_issues': total_individual_issues,
        })
    
    # Sort data based on parameters
    reverse_sort = sort_direction == 'desc'
    if sort_by == 'name':
        employee_data.sort(key=lambda x: x['name'], reverse=reverse_sort)
    elif sort_by == 'department':
        employee_data.sort(key=lambda x: x['department'], reverse=reverse_sort)
    elif sort_by == 'total_working_days':
        employee_data.sort(key=lambda x: x['total_working_days'], reverse=reverse_sort)
    elif sort_by == 'problematic_days':
        employee_data.sort(key=lambda x: x['problematic_days'], reverse=reverse_sort)
    elif sort_by == 'total_individual_issues':
        employee_data.sort(key=lambda x: x['total_individual_issues'], reverse=reverse_sort)
    else:  # Default to problematic_percentage
        employee_data.sort(key=lambda x: x['problematic_percentage'], reverse=reverse_sort)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="comprehensive_attendance_report_{start_date}_{end_date}_{department_filter}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Employee Name',
        'Department',
        'Total Working Days',
        'Problematic Days',
        'Problematic Percentage (%)',
        'Non-Problematic Days',
        'Non-Problematic Percentage (%)',
        'Standup Issues',
        'Return Lunch Issues',
        'Early Departure Issues',
        'Total Individual Issues',
        'Risk Level'
    ])
    
    for data in employee_data:
        # Determine risk level
        risk_level = 'Low'
        if data['problematic_percentage'] >= 50:
            risk_level = 'High'
        elif data['problematic_percentage'] >= 25:
            risk_level = 'Medium'
        
        writer.writerow([
            data['name'],
            data['department'],
            data['total_working_days'],
            data['problematic_days'],
            data['problematic_percentage'],
            data['non_problematic_days'],
            data['non_problematic_percentage'],
            data['standup_issues'],
            data['return_lunch_issues'],
            data['early_departure_issues'],
            data['total_individual_issues'],
            risk_level
        ])
    
    return response

def location_dashboard(request):
    """Location dashboard view."""
    
    # Get current date
    today = date.today()
    
    # Get all locations with analytics
    locations = Location.objects.filter(
        task_assignments__assigned_date=today
    ).distinct()
    
    # Get current analytics
    current_analytics = LocationAnalytics.objects.filter(
        date=today
    ).select_related('location')
    
    # Get recent assignments
    recent_assignments = TaskAssignment.objects.filter(
        assigned_date=today
    ).select_related('employee', 'location')[:10]
    
    # Get recent movements
    recent_movements = LocationMovement.objects.filter(
        timestamp__date=today
    ).select_related('employee', 'to_location')[:10]
    
    # Calculate summary statistics
    total_assignments = TaskAssignment.objects.filter(
        assigned_date=today
    ).count()
    
    total_employees = TaskAssignment.objects.filter(
        assigned_date=today
    ).values('employee').distinct().count()
    
    avg_utilization = current_analytics.aggregate(
        avg_util=Avg('utilization_rate')
    )['avg_util'] or 0
    
    context = {
        'locations': locations,
        'current_analytics': current_analytics,
        'recent_assignments': recent_assignments,
        'recent_movements': recent_movements,
        'total_assignments': total_assignments,
        'total_employees': total_employees,
        'avg_utilization': avg_utilization,
        'today': today,
    }
    
    return render(request, 'common/location_dashboard.html', context)

def location_analytics_api(request, location_id):
    """API endpoint for location analytics."""
    
    try:
        location = Location.objects.get(id=location_id)
        
        # Get date range (last 30 days)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        # Get analytics for the location
        analytics = LocationAnalytics.objects.filter(
            location=location,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        # Prepare data for charts
        dates = [a.date.isoformat() for a in analytics]
        utilization_rates = [float(a.utilization_rate) for a in analytics]
        occupancies = [a.current_occupancy for a in analytics]
        
        data = {
            'location_name': location.name,
            'dates': dates,
            'utilization_rates': utilization_rates,
            'occupancies': occupancies,
            'current_occupancy': location.current_occupancy,
            'utilization_rate': location.utilization_rate,
            'capacity': location.capacity,
        }
        
        return JsonResponse(data)
        
    except Location.DoesNotExist:
        return JsonResponse({'error': 'Location not found'}, status=404)

def employee_locations_api(request):
    """API endpoint for current employee locations."""
    
    today = date.today()
    
    # Get current assignments
    assignments = TaskAssignment.objects.filter(
        assigned_date=today,
        is_completed=False
    ).select_related('employee', 'location')
    
    data = []
    for assignment in assignments:
        data.append({
            'employee_name': f"{assignment.employee.given_name} {assignment.employee.surname}",
            'location_name': assignment.location.name,
            'task_type': assignment.task_type,
            'assigned_date': assignment.assigned_date.isoformat(),
        })
    
    return JsonResponse({'assignments': data})

def location_summary_api(request):
    """API endpoint for location summary."""
    
    today = date.today()
    
    # Get all locations with current activity
    locations = Location.objects.filter(
        task_assignments__assigned_date=today
    ).distinct()
    
    summary = []
    for location in locations:
        current_assignments = TaskAssignment.objects.filter(
            location=location,
            assigned_date=today,
            is_completed=False
        ).count()
        
        total_assignments = TaskAssignment.objects.filter(
            location=location,
            assigned_date=today
        ).count()
        
        summary.append({
            'location_name': location.name,
            'current_occupancy': current_assignments,
            'total_assignments': total_assignments,
            'utilization_rate': location.utilization_rate,
            'capacity': location.capacity,
        })
    
    return JsonResponse({'locations': summary})

def location_assignment_list(request):
    """List and filter location assignments."""
    
    # Get filter parameters
    form = LocationAssignmentFilterForm(request.GET)
    assignments = TaskAssignment.objects.select_related('employee', 'location').all()
    
    if form.is_valid():
        # Apply filters
        if form.cleaned_data.get('date_from'):
            assignments = assignments.filter(assigned_date__gte=form.cleaned_data['date_from'])
        
        if form.cleaned_data.get('date_to'):
            assignments = assignments.filter(assigned_date__lte=form.cleaned_data['date_to'])
        
        if form.cleaned_data.get('employee'):
            assignments = assignments.filter(employee=form.cleaned_data['employee'])
        
        if form.cleaned_data.get('location'):
            assignments = assignments.filter(location=form.cleaned_data['location'])
        
        if form.cleaned_data.get('task_type'):
            assignments = assignments.filter(task_type__icontains=form.cleaned_data['task_type'])
        
        if form.cleaned_data.get('is_completed') == 'yes':
            assignments = assignments.filter(is_completed=True)
        elif form.cleaned_data.get('is_completed') == 'no':
            assignments = assignments.filter(is_completed=False)
    
    # Pagination
    paginator = Paginator(assignments, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'total_assignments': assignments.count(),
        'completed_assignments': assignments.filter(is_completed=True).count(),
        'pending_assignments': assignments.filter(is_completed=False).count(),
    }
    
    return render(request, 'common/location_assignment_list.html', context)


def location_assignment_create(request):
    """Create a new location assignment."""
    
    if request.method == 'POST':
        form = TaskAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.created_by = request.user
            assignment.save()
            
            # Create location movement record
            LocationMovement.objects.create(
                employee=assignment.employee,
                to_location=assignment.location,
                movement_type='TASK_ASSIGNMENT',
                notes=f'Assignment created: {assignment.task_type}',
                created_by=request.user
            )
            
            messages.success(request, f'Assignment created for {assignment.employee} at {assignment.location}')
            return redirect('location_assignment_list')
    else:
        form = TaskAssignmentForm()
    
    context = {
        'form': form,
        'title': 'Create Location Assignment',
        'submit_text': 'Create Assignment'
    }
    
    return render(request, 'common/location_assignment_form.html', context)


def location_assignment_edit(request, assignment_id):
    """Edit an existing location assignment."""
    
    try:
        assignment = TaskAssignment.objects.get(id=assignment_id)
    except TaskAssignment.DoesNotExist:
        messages.error(request, 'Assignment not found')
        return redirect('location_assignment_list')
    
    if request.method == 'POST':
        form = TaskAssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            old_location = assignment.location
            assignment = form.save()
            
            # Create movement record if location changed
            if old_location != assignment.location:
                LocationMovement.objects.create(
                    employee=assignment.employee,
                    from_location=old_location,
                    to_location=assignment.location,
                    movement_type='TASK_ASSIGNMENT',
                    notes=f'Assignment moved from {old_location} to {assignment.location}',
                    created_by=request.user
                )
            
            messages.success(request, f'Assignment updated for {assignment.employee}')
            return redirect('location_assignment_list')
    else:
        form = TaskAssignmentForm(instance=assignment)
    
    context = {
        'form': form,
        'assignment': assignment,
        'title': 'Edit Location Assignment',
        'submit_text': 'Update Assignment'
    }
    
    return render(request, 'common/location_assignment_form.html', context)


def location_assignment_delete(request, assignment_id):
    """Delete a location assignment."""
    
    try:
        assignment = TaskAssignment.objects.get(id=assignment_id)
    except TaskAssignment.DoesNotExist:
        messages.error(request, 'Assignment not found')
        return redirect('location_assignment_list')
    
    if request.method == 'POST':
        employee_name = f"{assignment.employee.given_name} {assignment.employee.surname}"
        location_name = assignment.location.name
        assignment.delete()
        
        messages.success(request, f'Assignment for {employee_name} at {location_name} deleted')
        return redirect('location_assignment_list')
    
    context = {
        'assignment': assignment,
        'title': 'Delete Location Assignment'
    }
    
    return render(request, 'common/location_assignment_confirm_delete.html', context)


def bulk_location_assignment(request):
    """Bulk assign employees to a location."""
    
    if request.method == 'POST':
        form = BulkTaskAssignmentForm(request.POST)
        if form.is_valid():
            assigned_date = form.cleaned_data['assigned_date']
            location = form.cleaned_data['location']
            task_type = form.cleaned_data['task_type']
            start_time = form.cleaned_data.get('start_time')
            end_time = form.cleaned_data.get('end_time')
            
            assignments_created = 0
            employees_assigned = []
            
            for field_name, value in form.cleaned_data.items():
                if field_name.startswith('assign_') and value:
                    employee_id = field_name.replace('assign_', '')
                    try:
                        employee = Employee.objects.get(id=employee_id)
                        
                        # Check if assignment already exists
                        assignment, created = TaskAssignment.objects.get_or_create(
                            employee=employee,
                            location=location,
                            assigned_date=assigned_date,
                            defaults={
                                'task_type': task_type,
                                'start_time': start_time,
                                'end_time': end_time,
                                'created_by': request.user
                            }
                        )
                        
                        if created:
                            assignments_created += 1
                            employees_assigned.append(employee)
                            
                            # Create movement record
                            LocationMovement.objects.create(
                                employee=employee,
                                to_location=location,
                                movement_type='TASK_ASSIGNMENT',
                                notes=f'Bulk assignment: {task_type}',
                                created_by=request.user
                            )
                    
                    except Employee.DoesNotExist:
                        continue
            
            if assignments_created > 0:
                messages.success(
                    request, 
                    f'Created {assignments_created} assignments for {location.name}'
                )
            else:
                messages.warning(request, 'No new assignments created (may already exist)')
            
            return redirect('location_assignment_list')
    else:
        form = BulkTaskAssignmentForm()
    
    context = {
        'form': form,
        'title': 'Bulk Location Assignment',
        'submit_text': 'Create Assignments'
    }
    
    return render(request, 'common/bulk_location_assignment_form.html', context)


def location_assignment_complete(request, assignment_id):
    """Mark an assignment as completed."""
    
    try:
        assignment = TaskAssignment.objects.get(id=assignment_id)
    except TaskAssignment.DoesNotExist:
        messages.error(request, 'Assignment not found')
        return redirect('location_assignment_list')
    
    if request.method == 'POST':
        assignment.is_completed = True
        assignment.save()
        
        messages.success(
            request, 
            f'Assignment for {assignment.employee} at {assignment.location} marked as completed'
        )
        return redirect('location_assignment_list')
    
    context = {
        'assignment': assignment,
        'title': 'Complete Assignment'
    }
    
    return render(request, 'common/location_assignment_confirm_complete.html', context)

# Phase 3: Advanced Analytics - Pattern Recognition Dashboard

class PatternRecognitionView(generics.ListAPIView):
    """API endpoint for pattern recognition analysis"""
    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]
    serializer_class = EmployeeAnalyticsSerializer
    
    def get_queryset(self):
        """Return pattern analysis data"""
        # This will be implemented to return pattern analysis data
        return EmployeeAnalytics.objects.none()
    
    def list(self, request, *args, **kwargs):
        """Return pattern recognition data"""
        from datetime import datetime, timedelta
        from django.db.models import Avg, Count, Q
        
        # Get date range from request
        days_back = int(request.GET.get('days', 30))
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        # Get employee analytics for pattern analysis
        analytics = EmployeeAnalytics.objects.filter(
            date__range=[start_date, end_date]
        ).select_related('employee', 'employee__department')
        
        # Pattern analysis data
        pattern_data = {
            'arrival_patterns': self._analyze_arrival_patterns(analytics),
            'departure_patterns': self._analyze_departure_patterns(analytics),
            'location_patterns': self._analyze_location_patterns(analytics),
            'anomaly_detection': self._detect_anomalies(analytics),
            'trend_analysis': self._analyze_trends(analytics),
            'correlation_analysis': self._analyze_correlations(analytics),
        }
        
        return Response(pattern_data)
    
    def _analyze_arrival_patterns(self, analytics):
        """Analyze employee arrival time patterns"""
        patterns = {}
        
        # Group by employee and analyze arrival times
        for employee_analytics in analytics:
            employee = employee_analytics.employee
            if employee.id not in patterns:
                patterns[employee.id] = {
                    'employee_name': f"{employee.given_name} {employee.surname}",
                    'department': employee.department.name if employee.department else 'Unknown',
                    'arrival_times': [],
                    'average_arrival': None,
                    'consistency_score': 0,
                }
            
            if employee_analytics.average_arrival_time:
                patterns[employee.id]['arrival_times'].append(
                    employee_analytics.average_arrival_time.strftime('%H:%M')
                )
        
        # Calculate consistency scores
        for emp_id, data in patterns.items():
            if data['arrival_times']:
                # Calculate average arrival time
                times = [datetime.strptime(t, '%H:%M').time() for t in data['arrival_times']]
                avg_hour = sum(t.hour for t in times) / len(times)
                avg_minute = sum(t.minute for t in times) / len(times)
                data['average_arrival'] = f"{int(avg_hour):02d}:{int(avg_minute):02d}"
                
                # Calculate consistency (lower variance = higher consistency)
                hour_variance = sum((t.hour - avg_hour) ** 2 for t in times) / len(times)
                data['consistency_score'] = max(0, 100 - (hour_variance * 10))
        
        return patterns
    
    def _analyze_departure_patterns(self, analytics):
        """Analyze employee departure time patterns"""
        patterns = {}
        
        # Similar to arrival patterns but for departures
        for employee_analytics in analytics:
            employee = employee_analytics.employee
            if employee.id not in patterns:
                patterns[employee.id] = {
                    'employee_name': f"{employee.given_name} {employee.surname}",
                    'department': employee.department.name if employee.department else 'Unknown',
                    'departure_times': [],
                    'average_departure': None,
                    'consistency_score': 0,
                }
            
            if employee_analytics.average_departure_time:
                patterns[employee.id]['departure_times'].append(
                    employee_analytics.average_departure_time.strftime('%H:%M')
                )
        
        # Calculate consistency scores
        for emp_id, data in patterns.items():
            if data['departure_times']:
                times = [datetime.strptime(t, '%H:%M').time() for t in data['departure_times']]
                avg_hour = sum(t.hour for t in times) / len(times)
                avg_minute = sum(t.minute for t in times) / len(times)
                data['average_departure'] = f"{int(avg_hour):02d}:{int(avg_minute):02d}"
                
                hour_variance = sum((t.hour - avg_hour) ** 2 for t in times) / len(times)
                data['consistency_score'] = max(0, 100 - (hour_variance * 10))
        
        return patterns
    
    def _analyze_location_patterns(self, analytics):
        """Analyze employee location preference patterns"""
        from collections import defaultdict
        
        location_patterns = defaultdict(lambda: {
            'visits': 0,
            'total_time': 0,
            'employees': set(),
        })
        
        for employee_analytics in analytics:
            employee = employee_analytics.employee
            locations_visited = employee_analytics.locations_visited
            
            for location in locations_visited:
                location_patterns[location]['visits'] += 1
                location_patterns[location]['employees'].add(employee.id)
        
        # Convert to serializable format
        patterns = {}
        for location, data in location_patterns.items():
            patterns[location] = {
                'visits': data['visits'],
                'unique_employees': len(data['employees']),
                'popularity_score': data['visits'] * len(data['employees']),
            }
        
        return patterns
    
    def _detect_anomalies(self, analytics):
        """Detect anomalous behavior patterns"""
        anomalies = []
        
        for employee_analytics in analytics:
            employee = employee_analytics.employee
            
            # Detect various types of anomalies
            anomaly_flags = []
            
            # Late arrival anomaly
            if employee_analytics.is_late_arrival:
                anomaly_flags.append('late_arrival')
            
            # Early departure anomaly
            if employee_analytics.is_early_departure:
                anomaly_flags.append('early_departure')
            
            # Low attendance score anomaly
            if employee_analytics.attendance_score < 70:
                anomaly_flags.append('low_attendance_score')
            
            # Unusual movement pattern
            if employee_analytics.movement_count > 10:  # Threshold for unusual movement
                anomaly_flags.append('high_movement')
            
            # Unusual hours worked
            if employee_analytics.total_hours_worked < 6 or employee_analytics.total_hours_worked > 12:
                anomaly_flags.append('unusual_hours')
            
            if anomaly_flags:
                anomalies.append({
                    'employee_id': employee.id,
                    'employee_name': f"{employee.given_name} {employee.surname}",
                    'department': employee.department.name if employee.department else 'Unknown',
                    'date': employee_analytics.date,
                    'anomaly_types': anomaly_flags,
                    'severity_score': len(anomaly_flags),
                })
        
        return anomalies
    
    def _analyze_trends(self, analytics):
        """Analyze attendance trends over time"""
        from django.db.models import Avg
        
        # Group by date and calculate trends
        daily_trends = analytics.values('date').annotate(
            avg_attendance_score=Avg('attendance_score'),
            avg_hours_worked=Avg('total_hours_worked'),
            total_employees=Count('employee'),
            late_arrivals=Count('employee', filter=Q(is_late_arrival=True)),
            early_departures=Count('employee', filter=Q(is_early_departure=True)),
        ).order_by('date')
        
        trends = {
            'daily_attendance_scores': list(daily_trends.values('date', 'avg_attendance_score')),
            'daily_hours_worked': list(daily_trends.values('date', 'avg_hours_worked')),
            'daily_late_arrivals': list(daily_trends.values('date', 'late_arrivals')),
            'daily_early_departures': list(daily_trends.values('date', 'early_departures')),
        }
        
        return trends
    
    def _analyze_correlations(self, analytics):
        """Analyze correlations between different factors"""
        correlations = {}
        
        # Department vs attendance correlation
        dept_analytics = analytics.values('employee__department__name').annotate(
            avg_attendance_score=Avg('attendance_score'),
            avg_hours_worked=Avg('total_hours_worked'),
            employee_count=Count('employee'),
        )
        
        correlations['department_performance'] = list(dept_analytics)
        
        # Day of week correlation
        from django.db.models.functions import ExtractDayOfWeek
        day_analytics = analytics.annotate(
            day_of_week=ExtractDayOfWeek('date')
        ).values('day_of_week').annotate(
            avg_attendance_score=Avg('attendance_score'),
            avg_hours_worked=Avg('total_hours_worked'),
        ).order_by('day_of_week')
        
        correlations['day_of_week_performance'] = list(day_analytics)
        
        return correlations


class AnomalyDetectionView(generics.ListAPIView):
    """API endpoint for anomaly detection system"""
    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]
    serializer_class = EmployeeAnalyticsSerializer
    
    def get_queryset(self):
        """Return anomaly detection data"""
        return EmployeeAnalytics.objects.none()
    
    def list(self, request, *args, **kwargs):
        """Return anomaly detection results"""
        from datetime import datetime, timedelta
        
        # Get date range from request
        days_back = int(request.GET.get('days', 7))
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        # Get recent analytics for anomaly detection
        analytics = EmployeeAnalytics.objects.filter(
            date__range=[start_date, end_date],
            is_anomaly=True
        ).select_related('employee', 'employee__department')
        
        anomalies = []
        for employee_analytics in analytics:
            anomalies.append({
                'employee_id': employee_analytics.employee.id,
                'employee_name': f"{employee_analytics.employee.given_name} {employee_analytics.employee.surname}",
                'department': employee_analytics.employee.department.name if employee_analytics.employee.department else 'Unknown',
                'date': employee_analytics.date,
                'anomaly_reason': employee_analytics.anomaly_reason,
                'attendance_score': float(employee_analytics.attendance_score),
                'hours_worked': float(employee_analytics.total_hours_worked),
                'severity': self._calculate_anomaly_severity(employee_analytics),
            })
        
        return Response({
            'anomalies': anomalies,
            'total_anomalies': len(anomalies),
            'date_range': {
                'start_date': start_date,
                'end_date': end_date,
            }
        })
    
    def _calculate_anomaly_severity(self, analytics):
        """Calculate anomaly severity score"""
        severity = 0
        
        if analytics.is_late_arrival:
            severity += 1
        if analytics.is_early_departure:
            severity += 1
        if analytics.attendance_score < 70:
            severity += 2
        if analytics.total_hours_worked < 6:
            severity += 1
        if analytics.total_hours_worked > 12:
            severity += 1
        
        return min(severity, 5)  # Cap at 5


class PredictiveAnalyticsView(generics.ListAPIView):
    """API endpoint for predictive analytics"""
    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]
    serializer_class = EmployeeAnalyticsSerializer
    
    def get_queryset(self):
        """Return predictive analytics data"""
        return EmployeeAnalytics.objects.none()
    
    def list(self, request, *args, **kwargs):
        """Return predictive analytics forecasts"""
        from datetime import datetime, timedelta
        from django.db.models import Avg, Count
        
        # Get historical data for forecasting
        days_back = int(request.GET.get('days', 90))
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        # Get historical analytics
        analytics = EmployeeAnalytics.objects.filter(
            date__range=[start_date, end_date]
        ).select_related('employee', 'employee__department')
        
        # Generate forecasts
        forecasts = {
            'attendance_forecast': self._forecast_attendance(analytics),
            'capacity_planning': self._forecast_capacity(analytics),
            'risk_assessment': self._assess_risks(analytics),
            'optimization_recommendations': self._generate_recommendations(analytics),
        }
        
        return Response(forecasts)
    
    def _forecast_attendance(self, analytics):
        """Forecast future attendance patterns"""
        # Simple moving average forecast
        daily_attendance = analytics.values('date').annotate(
            avg_attendance_score=Avg('attendance_score'),
            total_employees=Count('employee'),
        ).order_by('date')
        
        # Calculate 7-day moving average
        attendance_scores = [a['avg_attendance_score'] for a in daily_attendance]
        if len(attendance_scores) >= 7:
            recent_avg = sum(attendance_scores[-7:]) / 7
        else:
            recent_avg = sum(attendance_scores) / len(attendance_scores) if attendance_scores else 0
        
        # Generate next 7 days forecast
        forecast_dates = []
        for i in range(1, 8):
            forecast_date = datetime.now().date() + timedelta(days=i)
            forecast_dates.append({
                'date': forecast_date,
                'predicted_attendance_score': recent_avg,
                'confidence_interval': [max(0, recent_avg - 5), min(100, recent_avg + 5)],
            })
        
        return {
            'current_trend': recent_avg,
            'forecast_dates': forecast_dates,
            'method': '7-day_moving_average',
        }
    
    def _forecast_capacity(self, analytics):
        """Forecast capacity planning needs"""
        # Analyze peak usage patterns
        daily_employee_counts = analytics.values('date').annotate(
            total_employees=Count('employee'),
        ).order_by('date')
        
        employee_counts = [d['total_employees'] for d in daily_employee_counts]
        if employee_counts:
            avg_employees = sum(employee_counts) / len(employee_counts)
            max_employees = max(employee_counts)
        else:
            avg_employees = 0
            max_employees = 0
        
        return {
            'average_daily_employees': avg_employees,
            'peak_daily_employees': max_employees,
            'recommended_capacity': int(max_employees * 1.1),  # 10% buffer
            'capacity_utilization': (avg_employees / max_employees * 100) if max_employees > 0 else 0,
        }
    
    def _assess_risks(self, analytics):
        """Assess attendance risk factors"""
        risks = []
        
        # Analyze risk factors
        late_arrival_rate = analytics.filter(is_late_arrival=True).count() / analytics.count() if analytics.count() > 0 else 0
        early_departure_rate = analytics.filter(is_early_departure=True).count() / analytics.count() if analytics.count() > 0 else 0
        low_attendance_rate = analytics.filter(attendance_score__lt=70).count() / analytics.count() if analytics.count() > 0 else 0
        
        if late_arrival_rate > 0.1:  # More than 10% late arrivals
            risks.append({
                'risk_type': 'high_late_arrivals',
                'severity': 'medium',
                'description': f"{late_arrival_rate:.1%} of employees arriving late",
                'recommendation': 'Review arrival time policies and consider flexible start times',
            })
        
        if early_departure_rate > 0.1:  # More than 10% early departures
            risks.append({
                'risk_type': 'high_early_departures',
                'severity': 'medium',
                'description': f"{early_departure_rate:.1%} of employees leaving early",
                'recommendation': 'Investigate workload distribution and employee satisfaction',
            })
        
        if low_attendance_rate > 0.2:  # More than 20% low attendance
            risks.append({
                'risk_type': 'low_attendance_scores',
                'severity': 'high',
                'description': f"{low_attendance_rate:.1%} of employees with low attendance scores",
                'recommendation': 'Implement attendance improvement programs and support systems',
            })
        
        return risks
    
    def _generate_recommendations(self, analytics):
        """Generate optimization recommendations"""
        recommendations = []
        
        # Analyze patterns and generate recommendations
        avg_attendance_score = analytics.aggregate(Avg('attendance_score'))['attendance_score__avg'] or 0
        avg_hours_worked = analytics.aggregate(Avg('total_hours_worked'))['total_hours_worked__avg'] or 0
        
        if avg_attendance_score < 80:
            recommendations.append({
                'category': 'attendance_improvement',
                'priority': 'high',
                'title': 'Improve Overall Attendance',
                'description': f'Current average attendance score is {avg_attendance_score:.1f}%. Consider implementing attendance incentives.',
                'action_items': [
                    'Implement attendance recognition programs',
                    'Provide flexible work arrangements',
                    'Address underlying causes of absenteeism',
                ]
            })
        
        if avg_hours_worked < 7.5:
            recommendations.append({
                'category': 'productivity_optimization',
                'priority': 'medium',
                'title': 'Optimize Work Hours',
                'description': f'Average hours worked is {avg_hours_worked:.1f} hours. Consider workload distribution.',
                'action_items': [
                    'Review workload distribution',
                    'Implement productivity tracking',
                    'Provide time management training',
                ]
            })
        
        return recommendations


@reporting_required
@extend_schema(exclude=True)
def pattern_recognition_dashboard(request):
    """
    Pattern Recognition Dashboard for Phase 3 of the report enhancement roadmap.
    Provides behavioral pattern analysis, anomaly detection, and trend analysis.
    """
    context = {
        'page_title': 'Pattern Recognition Dashboard',
        'active_tab': 'pattern_recognition',
    }
    return render(request, 'attendance/pattern_recognition_dashboard.html', context)


@reporting_required
@extend_schema(exclude=True)
def predictive_analytics_dashboard(request):
    """
    Predictive Analytics Dashboard for Phase 3 of the report enhancement roadmap.
    Provides attendance forecasting, capacity planning, and risk assessment.
    """
    context = {
        'page_title': 'Predictive Analytics Dashboard',
        'active_tab': 'predictive_analytics',
    }
    return render(request, 'attendance/predictive_analytics_dashboard.html', context)
