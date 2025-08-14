"""
Attendance management views.

This module contains all attendance-related functionality including
listing, entry, editing, and bulk operations.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseBadRequest, StreamingHttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as django_timezone
from zoneinfo import ZoneInfo
from drf_spectacular.utils import extend_schema
from django.db.models import Q, Count, Prefetch, Avg
from datetime import datetime, timedelta, date, time
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
import json
import traceback
import csv
import re
import logging
from typing import Optional

from ..models import (
    Employee, Event, EventType, Location, AttendanceRecord, Card, Department,
    AnalyticsCache, ReportConfiguration, EmployeeAnalytics, DepartmentAnalytics, SystemPerformance,
    TaskAssignment, LocationMovement, LocationAnalytics
)
from ..forms import (
    AttendanceRecordForm, BulkHistoricalUpdateForm, ProgressiveEntryForm, 
    HistoricalProgressiveEntryForm, AttendanceFilterForm,
    TaskAssignmentForm, BulkTaskAssignmentForm, LocationAssignmentFilterForm
)
from ..utils import performance_monitor, query_count_monitor
from ..services.attendance_service import (
    normalize_department_from_designation as svc_normalize_department_from_designation,
    list_available_departments as svc_list_available_departments,
    filter_employees_by_department as svc_filter_employees_by_department,
)
from ..decorators import security_required, attendance_required, reporting_required, admin_required


@attendance_required  # Attendance role and above
@extend_schema(exclude=True)
def attendance_analytics(request):
    """
    Enhanced analytics view with real-time insights.
    Shows performance metrics, trends, and visualizations.
    """
    # Get filter parameters
    date_range = request.GET.get('range', '30')  # Default to 30 days
    department_filter = request.GET.get('department', 'all')
    
    try:
        days_back = int(date_range)
        if days_back not in [7, 14, 30, 60, 90]:
            days_back = 30
    except ValueError:
        days_back = 30
    
    # Calculate date range
    end_date = django_timezone.now().date()
    start_date = end_date - timedelta(days=days_back)
    
    # Get attendance records for the period
    records_query = AttendanceRecord.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).select_related('employee', 'employee__card_number')
    
    # Apply department filter
    if department_filter != 'all':
        # Use service layer for consistent department filtering
        all_employees = Employee.objects.filter(is_active=True).select_related('card_number')
        filtered_employees = svc_filter_employees_by_department(all_employees, department_filter)
        employee_ids = [emp.id for emp in filtered_employees]
        records_query = records_query.filter(employee_id__in=employee_ids)
    
    records = list(records_query)
    
    # Calculate analytics
    total_records = len(records)
    on_time_count = sum(1 for r in records if r.status == 'On Time')
    early_count = sum(1 for r in records if r.status == 'Early')
    late_count = sum(1 for r in records if r.status == 'Late')
    absent_count = sum(1 for r in records if r.status == 'Absent')
    
    # Calculate percentages
    if total_records > 0:
        on_time_percentage = round((on_time_count / total_records) * 100, 1)
        early_percentage = round((early_count / total_records) * 100, 1)
        late_percentage = round((late_count / total_records) * 100, 1)
        absent_percentage = round((absent_count / total_records) * 100, 1)
    else:
        on_time_percentage = early_percentage = late_percentage = absent_percentage = 0
    
    # Daily breakdown for chart
    daily_stats = {}
    for record in records:
        day_key = record.date.strftime('%Y-%m-%d')
        if day_key not in daily_stats:
            daily_stats[day_key] = {'total': 0, 'on_time': 0, 'early': 0, 'late': 0, 'absent': 0}
        
        daily_stats[day_key]['total'] += 1
        if record.status == 'On Time':
            daily_stats[day_key]['on_time'] += 1
        elif record.status == 'Early':
            daily_stats[day_key]['early'] += 1
        elif record.status == 'Late':
            daily_stats[day_key]['late'] += 1
        elif record.status == 'Absent':
            daily_stats[day_key]['absent'] += 1
    
    # Sort daily stats by date
    sorted_daily_stats = sorted(daily_stats.items(), key=lambda x: x[0])
    
    # Get available departments for filter
    available_departments = svc_list_available_departments()
    
    context = {
        'total_records': total_records,
        'on_time_count': on_time_count,
        'early_count': early_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'on_time_percentage': on_time_percentage,
        'early_percentage': early_percentage,
        'late_percentage': late_percentage,
        'absent_percentage': absent_percentage,
        'daily_stats': sorted_daily_stats,
        'date_range': days_back,
        'start_date': start_date,
        'end_date': end_date,
        'department_filter': department_filter,
        'available_departments': available_departments,
    }
    
    return render(request, 'attendance/analytics.html', context)


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
        # Handle AJAX save requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Handle batch updates
            if request.POST.get('batch_update') == 'true':
                completions = {}
                
                # Parse all POST data to find changes
                for key, value in request.POST.items():
                    if key.startswith('changes[') and value:  # Only process non-empty values
                        try:
                            # Parse key format: changes[employee_id][field_name]
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
            
            # Handle single field updates
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
                             'returned_on_time_after_lunch', 'lunch_time', 'notes']:
                if form.cleaned_data.get(field_name):
                    setattr(record, field_name, form.cleaned_data[field_name])
            
            record.last_updated_by = request.user
            record.save()
            
            messages.success(request, f'Attendance data saved for {employee} ({record.status})')
            return redirect('progressive_entry')
    else:
        form = ProgressiveEntryForm()
    
    # Get employees who were actually present (had clock-in events) today
    # Convert today to UTC for proper timezone handling
    start_of_day_local = django_timezone.make_aware(datetime.combine(today, time.min))
    end_of_day_local = django_timezone.make_aware(datetime.combine(today, time.max))
    
    # Convert to UTC for database query
    start_of_day_utc = start_of_day_local.astimezone(ZoneInfo("UTC"))
    end_of_day_utc = end_of_day_local.astimezone(ZoneInfo("UTC"))
    
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
    
    # Apply department filter using service layer
    if department_filter and department_filter != 'All Departments':
        employees = svc_filter_employees_by_department(employees, department_filter)
    
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
    
    # Get available departments for filter using service layer
    available_departments = svc_list_available_departments()
    
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
    Daily attendance overview dashboard showing who's present, absent, and late.
    """
    # Get filter parameters
    date_filter = request.GET.get('date')
    department_filter = request.GET.get('department', 'Digitization Tech')  # Default to Digitization Tech
    status_filter = request.GET.get('status')  # New: filter by attendance status
    
    # Default to today if no date specified
    if not date_filter:
        date_filter = django_timezone.localtime(django_timezone.now()).date().isoformat()
    
    try:
        target_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
    except ValueError:
        target_date = django_timezone.localtime(django_timezone.now()).date()
    
    # Get all active employees with optimized prefetch
    all_employees = Employee.objects.filter(is_active=True).select_related('card_number').order_by('surname', 'given_name')
    
    # Apply department filter to employees using service layer
    if department_filter:
        all_employees = svc_filter_employees_by_department(all_employees, department_filter)
    
    # Get attendance records for the target date with optimized prefetch
    records = AttendanceRecord.objects.filter(date=target_date).select_related('employee', 'employee__card_number')
    
    # Identify absent employees (those who didn't clock in) - OPTIMIZED
    # Convert local date to UTC for proper timezone handling
    start_of_day_local = django_timezone.make_aware(datetime.combine(target_date, time.min))
    end_of_day_local = django_timezone.make_aware(datetime.combine(target_date, time.max))
    
    # Convert to UTC for database query
    start_of_day = start_of_day_local.astimezone(ZoneInfo("UTC"))
    end_of_day = end_of_day_local.astimezone(ZoneInfo("UTC"))
    
    # Single optimized query to get all clocked-in employee IDs
    clocked_in_employees = set(
        Event.objects.filter(
            event_type__name='Clock In',
            timestamp__gte=start_of_day,
            timestamp__lte=end_of_day
        ).values_list('employee_id', flat=True)
    )
    
    # Apply status filter if specified
    if status_filter:
        # Convert to list if it's a QuerySet to handle filtering consistently
        if hasattr(all_employees, 'filter'):
            # It's a QuerySet, convert to list for consistent processing
            all_employees = list(all_employees)
        
        if status_filter == 'present':
            # Show only employees with attendance records
            all_employees = [emp for emp in all_employees if emp.id in clocked_in_employees]
        elif status_filter == 'absent':
            # Show only employees without attendance records
            all_employees = [emp for emp in all_employees if emp.id not in clocked_in_employees]
        elif status_filter == 'late':
            # Show only employees who arrived late (after 9:00 AM)
            late_employees = []
            for employee in all_employees:
                if employee.id in clocked_in_employees:
                    arrival_event = Event.objects.filter(
                        event_type__name='Clock In',
                        employee=employee,
                        timestamp__date=target_date
                    ).order_by('timestamp').first()
                    if arrival_event:
                        local_arrival = django_timezone.localtime(arrival_event.timestamp)
                        if local_arrival.time() > time(9, 0):  # After 9:00 AM
                            late_employees.append(employee)
            all_employees = late_employees
        elif status_filter == 'on_time':
            # Show only employees who arrived on time (before or at 9:00 AM)
            on_time_employees = []
            for employee in all_employees:
                if employee.id in clocked_in_employees:
                    arrival_event = Event.objects.filter(
                        event_type__name='Clock In',
                        employee=employee,
                        timestamp__date=target_date
                    ).order_by('timestamp').first()
                    if arrival_event:
                        local_arrival = django_timezone.localtime(arrival_event.timestamp)
                        if local_arrival.time() <= time(9, 0):  # Before or at 9:00 AM
                            on_time_employees.append(employee)
            all_employees = on_time_employees
    
    # Apply department filter to records using the same logic
    if department_filter:
        filtered_records = []
        for record in records:
            if record.employee.card_number:
                emp_dept = svc_normalize_department_from_designation(record.employee.card_number.designation)
                if emp_dept == department_filter:
                    filtered_records.append(record)
        records = filtered_records
    
    absentees = [emp for emp in all_employees if emp.id not in clocked_in_employees]
    
    # Calculate summary statistics
    total_employees = len(all_employees)
    present_count = len(clocked_in_employees)
    absent_count = len(absentees)
    late_count = 0
    on_time_count = 0
    
    # Check for late arrivals (after 9:00 AM)
    for employee in all_employees:
        if employee.id in clocked_in_employees:
            # Get arrival time for this employee
            arrival_event = Event.objects.filter(
                event_type__name='Clock In',
                employee=employee,
                timestamp__date=target_date
            ).order_by('timestamp').first()
            
            if arrival_event:
                local_arrival = django_timezone.localtime(arrival_event.timestamp)
                if local_arrival.time() > time(9, 0):  # After 9:00 AM
                    late_count += 1
                else:
                    on_time_count += 1
    
    # Build a list of display records for the overview table
    display_records = []
    
    # Add present employees
    for employee in all_employees:
        if employee.id in clocked_in_employees:
            # Get attendance record if exists
            record = next((r for r in records if r.employee.id == employee.id), None)
            
            # Get arrival time
            arrival_event = Event.objects.filter(
                event_type__name='Clock In',
                employee=employee,
                timestamp__date=target_date
            ).order_by('timestamp').first()
            
            arrival_time = None
            if arrival_event:
                local_arrival = django_timezone.localtime(arrival_event.timestamp)
                arrival_time = local_arrival.time()
            
            # Create overview record
            overview_record = type('OverviewRecord', (), {
                'employee': employee,
                'date': target_date,
                'arrival_time': arrival_time,
                'is_absent': False,
                'is_late': arrival_time and arrival_time > time(9, 0),
                'status': record.status if record else 'PRESENT',
                'has_attendance_record': record is not None,
            })()
            display_records.append(overview_record)
    
    # Add absent employees
    for employee in absentees:
        overview_record = type('OverviewRecord', (), {
            'employee': employee,
            'date': target_date,
            'arrival_time': None,
            'is_absent': True,
            'is_late': False,
            'status': 'ABSENT',
            'has_attendance_record': False,
        })()
        display_records.append(overview_record)
    
    # Sort display records
    display_records.sort(key=lambda x: (x.employee.surname, x.employee.given_name))
    
    # Pagination
    paginator = Paginator(display_records, 50)  # Show 50 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get available departments for filter using service layer
    available_departments = svc_list_available_departments()
    
    context = {
        'date_filter': target_date,
        'department_filter': department_filter,
        'status_filter': status_filter,  # Add status filter to context
        'available_departments': available_departments,
        'page_obj': page_obj,
        'total_employees': total_employees,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'on_time_count': on_time_count,
        'attendance_rate': (present_count / total_employees * 100) if total_employees > 0 else 0,
        'punctuality_rate': (on_time_count / present_count * 100) if present_count > 0 else 0,
    }
    
    return render(request, 'attendance/list.html', context)

@attendance_required  # Attendance management role and above
@extend_schema(exclude=True)
def historical_progressive_entry(request):
    """
    Historical progressive entry for past dates.
    """
    from ..forms import HistoricalProgressiveEntryForm
    
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
    
    # Get employees by department filter using service layer
    all_employees = Employee.objects.filter(is_active=True)
    if department_filter and department_filter != 'All Departments':
        filtered_employees = svc_filter_employees_by_department(all_employees, department_filter)
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
        
        # Create a list of employees with INCOMPLETE records only (completion < 100%)
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
            
            # Check if record is incomplete (needs data entry)
            is_incomplete = False
            
            if existing_record:
                # Check if existing record is incomplete based on completion percentage
                if existing_record.completion_percentage < 100:
                    is_incomplete = True
                    # Add clock times to existing record
                    existing_record.clock_in_time = clock_in_time
                    existing_record.clock_out_time = clock_out_time
                    employee_records.append(existing_record)
            else:
                # No record exists - definitely incomplete
                is_incomplete = True
                # Create a dummy record object for present employees without attendance records
                dummy_record = type('DummyRecord', (), {
                    'id': None,
                    'employee': emp,
                    'date': date_key,
                    'lunch_time': None,
                    'left_lunch_on_time': None,
                    'returned_on_time_after_lunch': None,
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
    
    # Flatten records for template display
    all_records = []
    for date_records in records_by_date.values():
        all_records.extend(date_records)
    
    # Calculate updated and pending records
    updated_records = len([r for r in all_records if hasattr(r, 'status') and r.status in ['COMPLETE', 'PARTIAL']])
    pending_records = len([r for r in all_records if hasattr(r, 'status') and r.status in ['DRAFT', 'ABSENT']])
    
    # Get available departments for filter using service layer
    available_departments = svc_list_available_departments()
    
    context = {
        'date_from': date_from,
        'date_to': date_to,
        'department_filter': department_filter,
        'available_departments': available_departments,
        'date_page': date_paginator.get_page(page_number), # Use paginator for date_page
        'records_by_date': records_by_date,
        'records': all_records,  # Flattened records for template
        'total_days': total_days,
        'total_records': total_records,
        'updated_records': updated_records,
        'pending_records': pending_records,
        'date_range': f"{date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}",
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
            record.total_issues,
            record.status,
            record.notes or ''
        ])
    
    return response


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
    
    # Apply department filter using service layer
    if department_filter:
        employees = svc_filter_employees_by_department(employees, department_filter)
    
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
def debug_view(request):
    """Debug view to test template context"""
    
    today = django_timezone.localtime(django_timezone.now()).date()
    
    # Test progressive entry logic
    start_of_day_local = django_timezone.make_aware(datetime.combine(today, time.min))
    end_of_day_local = django_timezone.make_aware(datetime.combine(today, time.max))
    start_of_day_utc = start_of_day_local.astimezone(ZoneInfo("UTC"))
    end_of_day_utc = end_of_day_local.astimezone(ZoneInfo("UTC"))
    
    present_employees = Event.objects.filter(
        event_type__name='Clock In',
        timestamp__gte=start_of_day_utc,
        timestamp__lte=end_of_day_utc
    ).values_list('employee', flat=True).distinct()
    
    employees = Employee.objects.filter(
        id__in=present_employees,
        is_active=True
    ).select_related('card_number').order_by('surname', 'given_name')
    
    # Apply department filter using service layer
    department_filter = 'Digitization Tech'
    filtered_employees = svc_filter_employees_by_department(employees, department_filter)
    
    # Get attendance records
    today_records = AttendanceRecord.objects.filter(
        date=today,
        employee__in=filtered_employees
    ).select_related('employee', 'employee__card_number')
    
    # Create employee attendance list
    records_by_employee = {record.employee_id: record for record in today_records}
    
    employee_attendance = []
    for employee in filtered_employees:
        record = records_by_employee.get(employee.id)
        
        employee_attendance.append({
            'employee': employee,
            'record': record,
            'is_clocked_in': True,
            'arrival_time': record.arrival_time if record else None,
            'departure_time': record.departure_time if record else None,
        })
    
    # Test attendance list logic
    all_employees = Employee.objects.filter(is_active=True).select_related('card_number').order_by('surname', 'given_name')
    filtered_all_employees = svc_filter_employees_by_department(all_employees, department_filter)
    
    context = {
        'today': today,
        'employee_attendance': employee_attendance,
        'filtered_employees': filtered_employees,
        'all_employees': all_employees,
        'filtered_all_employees': filtered_all_employees,
        'department_filter': department_filter,
    }
    
    return render(request, 'attendance/debug.html', context)


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
    """Comprehensive attendance report based on the CSV analysis format with notes support"""
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
    
    # Apply department filter using service layer
    if department_filter:
        employees = svc_filter_employees_by_department(employees, department_filter)
    
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
        
        # Collect notes for this employee
        employee_notes = []
        for record in records:
            if record.notes and record.notes.strip():
                employee_notes.append(f"{record.date.strftime('%Y-%m-%d')}: {record.notes}")
            
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
            'notes': '; '.join(employee_notes) if employee_notes else None,
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
    
    # Get available departments for filter using service layer
    available_departments = svc_list_available_departments()
    
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