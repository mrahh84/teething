"""
Location tracking and assignment views.

This module contains all location-related functionality including
location dashboards, assignments, and analytics. 
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as django_timezone
from drf_spectacular.utils import extend_schema
from django.db.models import Q, Count
from datetime import datetime, timedelta, date
from django.http import JsonResponse
import json
from django.core.paginator import Paginator

from ..models import (
    Employee, Event, EventType, Location, AttendanceRecord, Card, Department,
    TaskAssignment, LocationMovement, LocationAnalytics
)
from ..forms import (
    TaskAssignmentForm, BulkTaskAssignmentForm, LocationAssignmentFilterForm
)
from ..services.attendance_service import (
    normalize_department_from_designation as svc_normalize_department_from_designation,
    list_available_departments as svc_list_available_departments,
    filter_employees_by_department as svc_filter_employees_by_department,
)
from ..decorators import security_required, attendance_required, reporting_required, admin_required


@reporting_required
@extend_schema(exclude=True)
def location_dashboard(request):
    """Location dashboard with assignments and analytics."""
    from django.db.models import Count, Avg
    from datetime import timedelta
    
    today = django_timezone.localtime(django_timezone.now()).date()
    last_7_days = today - timedelta(days=7)
    
    # Get location data
    locations = Location.objects.filter(is_active=True)
    
    # Get assignment data
    active_assignments = TaskAssignment.objects.filter(
        is_active=True,
        due_date__gte=today
    ).select_related('employee', 'location')
    
    # Get movement data
    recent_movements = LocationMovement.objects.filter(
        timestamp__date__gte=last_7_days
    ).select_related('employee', 'location')
    
    # Calculate location metrics
    location_metrics = []
    for location in locations:
        # Count active assignments
        assignment_count = active_assignments.filter(location=location).count()
        
        # Count recent movements
        movement_count = recent_movements.filter(location=location).count()
        
        # Calculate completion rate
        total_assignments = TaskAssignment.objects.filter(location=location).count()
        completed_assignments = TaskAssignment.objects.filter(
            location=location,
            status='completed'
        ).count()
        completion_rate = (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0
        
        location_metrics.append({
            'location': location,
            'assignment_count': assignment_count,
            'movement_count': movement_count,
            'completion_rate': round(completion_rate, 1),
            'total_assignments': total_assignments,
            'completed_assignments': completed_assignments
        })
    
    # Sort by assignment count (highest first)
    location_metrics.sort(key=lambda x: x['assignment_count'], reverse=True)
    
    # Get employee location data
    employee_locations = []
    for assignment in active_assignments[:10]:  # Top 10
        employee_locations.append({
            'employee_name': f"{assignment.employee.given_name} {assignment.employee.surname}",
            'location_name': assignment.location.name,
            'assignment_type': assignment.assignment_type,
            'due_date': assignment.due_date,
            'status': assignment.status
        })
    
    context = {
        'page_title': 'Location Dashboard',
        'active_tab': 'location_dashboard',
        'location_metrics': location_metrics,
        'employee_locations': employee_locations,
        'total_locations': locations.count(),
        'total_assignments': active_assignments.count(),
        'total_movements': recent_movements.count(),
    }
    return render(request, 'common/location_dashboard.html', context)


@reporting_required
@extend_schema(exclude=True)
def location_analytics_api(request, location_id):
    """API endpoint for location analytics."""
    try:
        location = get_object_or_404(Location, id=location_id)
        
        # Get date range from request
        end_date = django_timezone.localtime(django_timezone.now()).date()
        start_date = end_date - timedelta(days=30)
        
        # Get movement data for this location
        movements = LocationMovement.objects.filter(
            location=location,
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        ).select_related('employee', 'employee__department')
        
        # Get assignment data
        assignments = TaskAssignment.objects.filter(
            location=location,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).select_related('employee', 'employee__department')
        
        # Calculate analytics
        analytics_data = {
            'location_id': location.id,
            'location_name': location.name,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'movements': {
                'total': movements.count(),
                'by_employee': {},
                'by_department': {},
                'daily_trend': {}
            },
            'assignments': {
                'total': assignments.count(),
                'completed': assignments.filter(status='completed').count(),
                'pending': assignments.filter(status='pending').count(),
                'overdue': assignments.filter(
                    status='pending',
                    due_date__lt=today
                ).count()
            }
        }
        
        # Calculate movements by employee
        for movement in movements:
            employee_name = f"{movement.employee.given_name} {movement.employee.surname}"
            if employee_name not in analytics_data['movements']['by_employee']:
                analytics_data['movements']['by_employee'][employee_name] = 0
            analytics_data['movements']['by_employee'][employee_name] += 1
        
        # Calculate movements by department
        for movement in movements:
            dept_name = movement.employee.department.name if movement.employee.department else 'Unknown'
            if dept_name not in analytics_data['movements']['by_department']:
                analytics_data['movements']['by_department'][dept_name] = 0
            analytics_data['movements']['by_department'][dept_name] += 1
        
        # Calculate daily trends
        for movement in movements:
            date_str = movement.timestamp.date().isoformat()
            if date_str not in analytics_data['movements']['daily_trend']:
                analytics_data['movements']['daily_trend'][date_str] = 0
            analytics_data['movements']['daily_trend'][date_str] += 1
        
        return JsonResponse(analytics_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@reporting_required
@extend_schema(exclude=True)
def employee_locations_api(request):
    """API endpoint for employee location data."""
    try:
        # Get date range from request
        end_date = django_timezone.localtime(django_timezone.now()).date()
        start_date = end_date - timedelta(days=7)
        
        # Get employee location data
        employees = Employee.objects.filter(is_active=True).select_related('department')
        
        employee_data = []
        for employee in employees:
            # Get current location assignment
            current_assignment = TaskAssignment.objects.filter(
                employee=employee,
                is_active=True,
                due_date__gte=today
            ).select_related('location').first()
            
            # Get recent movements
            recent_movements = LocationMovement.objects.filter(
                employee=employee,
                timestamp__date__gte=start_date,
                timestamp__date__lte=end_date
            ).select_related('location').order_by('-timestamp')
            
            # Get location preferences
            all_movements = LocationMovement.objects.filter(employee=employee)
            location_counts = all_movements.values('location__name').annotate(count=Count('id'))
            preferred_locations = [loc['location__name'] for loc in location_counts.order_by('-count')[:3]]
            
            employee_data.append({
                'employee_id': employee.id,
                'employee_name': f"{employee.given_name} {employee.surname}",
                'department': employee.department.name if employee.department else 'N/A',
                'current_location': current_assignment.location.name if current_assignment else 'Unassigned',
                'recent_movements': [
                    {
                        'location': movement.location.name,
                        'timestamp': movement.timestamp.isoformat(),
                        'movement_type': movement.movement_type
                    } for movement in recent_movements[:5]
                ],
                'preferred_locations': preferred_locations,
                'total_movements': all_movements.count()
            })
        
        return JsonResponse({'employees': employee_data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@reporting_required
@extend_schema(exclude=True)
def location_summary_api(request):
    """API endpoint for location summary data."""
    try:
        # Get overall location statistics
        total_locations = Location.objects.filter(is_active=True).count()
        total_assignments = TaskAssignment.objects.filter(is_active=True).count()
        active_assignments = TaskAssignment.objects.filter(
            is_active=True,
            due_date__gte=today
        ).count()
        
        # Get location utilization
        location_utilization = []
        locations = Location.objects.filter(is_active=True)
        
        for location in locations:
            assignment_count = TaskAssignment.objects.filter(
                location=location,
                is_active=True
            ).count()
            
            utilization_rate = (assignment_count / max(active_assignments, 1)) * 100 if active_assignments > 0 else 0
            
            location_utilization.append({
                'location_name': location.name,
                'assignment_count': assignment_count,
                'utilization_rate': round(utilization_rate, 1)
            })
        
        # Sort by utilization rate
        location_utilization.sort(key=lambda x: x['utilization_rate'], reverse=True)
        
        summary_data = {
            'total_locations': total_locations,
            'total_assignments': total_assignments,
            'active_assignments': active_assignments,
            'location_utilization': location_utilization,
            'timestamp': django_timezone.now().isoformat()
        }
        
        return JsonResponse(summary_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@attendance_required
@extend_schema(exclude=True)
def location_assignment_list(request):
    """List view for location assignments."""
    # Get filter parameters
    department_filter = request.GET.get('department')
    status_filter = request.GET.get('status')
    location_filter = request.GET.get('location')
    
    # Get assignments with filtering
    assignments = TaskAssignment.objects.filter(is_active=True).select_related(
        'employee', 'employee__department', 'location'
    ).order_by('-created_at')
    
    if department_filter:
        assignments = assignments.filter(employee__department__name__icontains=department_filter)
    
    if status_filter:
        assignments = assignments.filter(status=status_filter)
    
    if location_filter:
        assignments = assignments.filter(location__name__icontains=location_filter)
    
    # Pagination
    paginator = Paginator(assignments, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    departments = Department.objects.filter(is_active=True)
    locations = Location.objects.filter(is_active=True)
    status_choices = TaskAssignment.STATUS_CHOICES
    
    context = {
        'page_title': 'Location Assignments',
        'active_tab': 'location_assignments',
        'page_obj': page_obj,
        'departments': departments,
        'locations': locations,
        'status_choices': status_choices,
        'filters': {
            'department': department_filter,
            'status': status_filter,
            'location': location_filter
        }
    }
    return render(request, 'common/location_assignment_list.html', context)


@attendance_required
@extend_schema(exclude=True)
def location_assignment_create(request):
    """Create new location assignment."""
    if request.method == 'POST':
        form = TaskAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.created_by = request.user
            assignment.save()
            
            messages.success(request, f'Location assignment created successfully for {assignment.employee}.')
            return redirect('location_assignment_list')
    else:
        form = TaskAssignmentForm()
    
    context = {
        'page_title': 'Create Location Assignment',
        'active_tab': 'location_assignments',
        'form': form,
        'action': 'create'
    }
    return render(request, 'common/location_assignment_form.html', context)


@attendance_required
@extend_schema(exclude=True)
def location_assignment_edit(request, assignment_id):
    """Edit existing location assignment."""
    assignment = get_object_or_404(TaskAssignment, id=assignment_id)
    
    if request.method == 'POST':
        form = TaskAssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            form.save()
            messages.success(request, f'Location assignment updated successfully for {assignment.employee}.')
            return redirect('location_assignment_list')
    else:
        form = TaskAssignmentForm(instance=assignment)
    
    context = {
        'page_title': 'Edit Location Assignment',
        'active_tab': 'location_assignments',
        'form': form,
        'assignment': assignment,
        'action': 'edit'
    }
    return render(request, 'common/location_assignment_form.html', context)


@attendance_required
@extend_schema(exclude=True)
def location_assignment_delete(request, assignment_id):
    """Delete location assignment."""
    assignment = get_object_or_404(TaskAssignment, id=assignment_id)
    
    if request.method == 'POST':
        employee_name = f"{assignment.employee.given_name} {assignment.employee.surname}"
        assignment.delete()
        messages.success(request, f'Location assignment deleted successfully for {employee_name}.')
        return redirect('location_assignment_list')
    
    context = {
        'page_title': 'Delete Location Assignment',
        'active_tab': 'location_assignments',
        'assignment': assignment
    }
    return render(request, 'common/delete_confirm.html', context)


@attendance_required
@extend_schema(exclude=True)
def bulk_location_assignment(request):
    """Bulk location assignment operations."""
    if request.method == 'POST':
        form = BulkTaskAssignmentForm(request.POST)
        if form.is_valid():
            # Get form data
            employees = form.cleaned_data['employees']
            location = form.cleaned_data['location']
            assignment_type = form.cleaned_data['assignment_type']
            due_date = form.cleaned_data['due_date']
            notes = form.cleaned_data.get('notes', '')
            
            # Create assignments
            created_count = 0
            for employee in employees:
                assignment = TaskAssignment.objects.create(
                    employee=employee,
                    location=location,
                    assignment_type=assignment_type,
                    due_date=due_date,
                    notes=notes,
                    created_by=request.user
                )
                created_count += 1
            
            messages.success(request, f'Successfully created {created_count} location assignments.')
            return redirect('location_assignment_list')
    else:
        form = BulkTaskAssignmentForm()
    
    context = {
        'page_title': 'Bulk Location Assignment',
        'active_tab': 'location_assignments',
        'form': form
    }
    return render(request, 'common/bulk_location_assignment_form.html', context)


@attendance_required
@extend_schema(exclude=True)
def location_assignment_complete(request, assignment_id):
    """Mark location assignment as complete."""
    assignment = get_object_or_404(TaskAssignment, id=assignment_id)
    
    if request.method == 'POST':
        assignment.status = 'completed'
        assignment.completed_at = django_timezone.now()
        assignment.save()
        
        messages.success(request, f'Location assignment marked as complete for {assignment.employee}.')
        return redirect('location_assignment_list')
    
    context = {
        'page_title': 'Complete Location Assignment',
        'active_tab': 'location_assignments',
        'assignment': assignment
    }
    return render(request, 'common/delete_confirm.html', context)