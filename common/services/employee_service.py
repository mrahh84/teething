"""
Employee Management Service

Handles all employee-related business logic including CRUD operations,
status management, and employee analytics.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from django.db import transaction
from django.db.models import Q, Count, Avg, QuerySet
from django.utils import timezone
from django.core.exceptions import ValidationError

from ..models import Employee, Event, AttendanceRecord, Card, Location, TaskAssignment
from .attendance_service import normalize_department_from_designation

logger = logging.getLogger(__name__)


class EmployeeService:
    """Service class for employee management operations."""

    @staticmethod
    def get_employee_by_id(employee_id: int) -> Optional[Employee]:
        """Get employee by ID with related data."""
        try:
            return Employee.objects.select_related(
                'card_number', 'assigned_departure_time', 'assigned_arrival_time'
            ).prefetch_related(
                'assigned_locations', 'taskassignment_set'
            ).get(id=employee_id, is_active=True)
        except Employee.DoesNotExist:
            return None

    @staticmethod
    def get_employee_by_card(card_number: str) -> Optional[Employee]:
        """Get employee by card number."""
        try:
            return Employee.objects.select_related('card_number').get(
                card_number__card_number=card_number, is_active=True
            )
        except Employee.DoesNotExist:
            return None

    @staticmethod
    def get_employees_by_department(department: str = None) -> QuerySet[Employee]:
        """Get employees filtered by department."""
        employees = Employee.objects.filter(is_active=True).select_related('card_number')
        
        if not department or department == 'all':
            return employees
        
        # Use attendance service for consistent department filtering
        from .attendance_service import filter_employees_by_department
        return filter_employees_by_department(employees, department)

    @staticmethod
    def get_employee_analytics(employee_id: int, days_back: int = 30) -> Dict[str, Any]:
        """Get comprehensive analytics for an employee."""
        employee = EmployeeService.get_employee_by_id(employee_id)
        if not employee:
            return {}

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)

        # Get attendance records
        records = AttendanceRecord.objects.filter(
            employee=employee,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')

        # Get events
        events = Event.objects.filter(
            employee=employee,
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        ).order_by('timestamp')

        # Calculate metrics
        total_days = records.count()
        if total_days == 0:
            return EmployeeService._empty_analytics(employee)

        # Status breakdown
        status_counts = {
            'on_time': records.filter(status='On Time').count(),
            'early': records.filter(status='Early').count(),
            'late': records.filter(status='Late').count(),
            'absent': records.filter(status='Absent').count(),
        }

        # Calculate percentages
        attendance_rate = ((total_days - status_counts['absent']) / total_days) * 100
        punctuality_rate = ((status_counts['on_time'] + status_counts['early']) / total_days) * 100
        
        # Average completion percentage
        avg_completion = records.aggregate(
            avg_completion=Avg('completion_percentage')
        )['avg_completion'] or 0

        # Problematic days
        problematic_days = sum(1 for record in records if record.is_problematic_day)
        problematic_rate = (problematic_days / total_days) * 100 if total_days > 0 else 0

        # Current status
        latest_record = records.last()
        current_status = {
            'last_attendance_date': latest_record.date if latest_record else None,
            'last_status': latest_record.status if latest_record else 'Unknown',
            'completion_percentage': latest_record.completion_percentage if latest_record else 0,
            'is_clocked_in': employee.is_clocked_in,
            'last_clock_time': EmployeeService._get_last_clock_time(employee),
        }

        # Recent trends (last 7 days vs previous 7 days)
        recent_records = records.filter(date__gte=end_date - timedelta(days=7))
        previous_records = records.filter(
            date__gte=end_date - timedelta(days=14),
            date__lt=end_date - timedelta(days=7)
        )

        trends = EmployeeService._calculate_trends(recent_records, previous_records)

        # Department info
        department = None
        if employee.card_number:
            department = normalize_department_from_designation(employee.card_number.designation)

        return {
            'employee': employee,
            'department': department,
            'analysis_period': {
                'start_date': start_date,
                'end_date': end_date,
                'total_days': total_days,
            },
            'status_breakdown': status_counts,
            'performance_metrics': {
                'attendance_rate': round(attendance_rate, 2),
                'punctuality_rate': round(punctuality_rate, 2),
                'average_completion': round(avg_completion, 2),
                'problematic_rate': round(problematic_rate, 2),
            },
            'current_status': current_status,
            'trends': trends,
            'recent_events_count': events.count(),
        }

    @staticmethod
    def _empty_analytics(employee: Employee) -> Dict[str, Any]:
        """Return empty analytics structure for employees with no data."""
        department = None
        if employee.card_number:
            department = normalize_department_from_designation(employee.card_number.designation)

        return {
            'employee': employee,
            'department': department,
            'analysis_period': {'total_days': 0},
            'status_breakdown': {'on_time': 0, 'early': 0, 'late': 0, 'absent': 0},
            'performance_metrics': {
                'attendance_rate': 0,
                'punctuality_rate': 0,
                'average_completion': 0,
                'problematic_rate': 0,
            },
            'current_status': {
                'last_attendance_date': None,
                'last_status': 'No Data',
                'completion_percentage': 0,
                'is_clocked_in': employee.is_clocked_in,
                'last_clock_time': EmployeeService._get_last_clock_time(employee),
            },
            'trends': {'attendance': 'stable', 'punctuality': 'stable'},
            'recent_events_count': 0,
        }

    @staticmethod
    def _get_last_clock_time(employee: Employee) -> Optional[datetime]:
        """Get the last clock in/out time for an employee."""
        last_event = Event.objects.filter(employee=employee).order_by('-timestamp').first()
        return last_event.timestamp if last_event else None

    @staticmethod
    def _calculate_trends(recent_records: QuerySet, previous_records: QuerySet) -> Dict[str, str]:
        """Calculate trends by comparing recent vs previous periods."""
        if not recent_records.exists() or not previous_records.exists():
            return {'attendance': 'stable', 'punctuality': 'stable'}

        # Recent metrics
        recent_total = recent_records.count()
        recent_on_time = recent_records.filter(status__in=['On Time', 'Early']).count()
        recent_present = recent_records.exclude(status='Absent').count()

        recent_attendance_rate = (recent_present / recent_total) * 100 if recent_total > 0 else 0
        recent_punctuality_rate = (recent_on_time / recent_total) * 100 if recent_total > 0 else 0

        # Previous metrics
        previous_total = previous_records.count()
        previous_on_time = previous_records.filter(status__in=['On Time', 'Early']).count()
        previous_present = previous_records.exclude(status='Absent').count()

        previous_attendance_rate = (previous_present / previous_total) * 100 if previous_total > 0 else 0
        previous_punctuality_rate = (previous_on_time / previous_total) * 100 if previous_total > 0 else 0

        # Determine trends
        attendance_trend = 'stable'
        if recent_attendance_rate > previous_attendance_rate + 10:
            attendance_trend = 'improving'
        elif recent_attendance_rate < previous_attendance_rate - 10:
            attendance_trend = 'declining'

        punctuality_trend = 'stable'
        if recent_punctuality_rate > previous_punctuality_rate + 10:
            punctuality_trend = 'improving'
        elif recent_punctuality_rate < previous_punctuality_rate - 10:
            punctuality_trend = 'declining'

        return {
            'attendance': attendance_trend,
            'punctuality': punctuality_trend,
        }

    @staticmethod
    def get_employees_requiring_attention() -> List[Dict[str, Any]]:
        """Get employees that require management attention."""
        attention_list = []
        
        # Get employees with poor recent performance
        recent_date = timezone.now().date() - timedelta(days=7)
        
        # Find employees with high absence rates
        employees = Employee.objects.filter(is_active=True).select_related('card_number')
        
        for employee in employees:
            recent_records = AttendanceRecord.objects.filter(
                employee=employee,
                date__gte=recent_date
            )
            
            if recent_records.count() < 3:  # Skip if not enough data
                continue
                
            absent_count = recent_records.filter(status='Absent').count()
            late_count = recent_records.filter(status='Late').count()
            total_count = recent_records.count()
            
            absence_rate = (absent_count / total_count) * 100
            late_rate = (late_count / total_count) * 100
            
            # Flag for attention if high absence or lateness
            needs_attention = False
            reasons = []
            
            if absence_rate >= 40:  # 40% or more absences
                needs_attention = True
                reasons.append(f"High absence rate: {absence_rate:.1f}%")
                
            if late_rate >= 50:  # 50% or more late arrivals
                needs_attention = True
                reasons.append(f"High lateness rate: {late_rate:.1f}%")
                
            # Check for long periods without clocking in
            last_event = Event.objects.filter(employee=employee).order_by('-timestamp').first()
            if last_event:
                days_since_last_event = (timezone.now().date() - last_event.timestamp.date()).days
                if days_since_last_event >= 3:
                    needs_attention = True
                    reasons.append(f"No activity for {days_since_last_event} days")
                    
            if needs_attention:
                department = None
                if employee.card_number:
                    department = normalize_department_from_designation(employee.card_number.designation)
                    
                attention_list.append({
                    'employee': employee,
                    'department': department,
                    'reasons': reasons,
                    'absence_rate': round(absence_rate, 1),
                    'late_rate': round(late_rate, 1),
                    'last_activity': last_event.timestamp if last_event else None,
                })
        
        # Sort by severity (absence rate + late rate)
        attention_list.sort(key=lambda x: x['absence_rate'] + x['late_rate'], reverse=True)
        
        return attention_list

    @staticmethod
    def update_employee_location_assignments(employee_id: int, location_ids: List[int]) -> bool:
        """Update employee's assigned locations."""
        try:
            with transaction.atomic():
                employee = Employee.objects.get(id=employee_id, is_active=True)
                locations = Location.objects.filter(id__in=location_ids)
                
                # Clear existing assignments
                employee.assigned_locations.clear()
                
                # Add new assignments
                employee.assigned_locations.set(locations)
                
                logger.info(f"Updated location assignments for employee {employee_id}")
                return True
                
        except (Employee.DoesNotExist, Exception) as e:
            logger.error(f"Failed to update location assignments for employee {employee_id}: {e}")
            return False

    @staticmethod
    def bulk_update_employee_status(employee_ids: List[int], is_active: bool) -> Tuple[int, int]:
        """Bulk update employee active status."""
        try:
            updated_count = Employee.objects.filter(
                id__in=employee_ids
            ).update(is_active=is_active)
            
            logger.info(f"Bulk updated {updated_count} employees to active={is_active}")
            return updated_count, 0
            
        except Exception as e:
            logger.error(f"Failed to bulk update employee status: {e}")
            return 0, len(employee_ids)

    @staticmethod
    def validate_employee_data(employee_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate employee data before creation/update."""
        errors = []
        
        # Required fields
        required_fields = ['given_name', 'surname']
        for field in required_fields:
            if not employee_data.get(field):
                errors.append(f"{field.replace('_', ' ').title()} is required")
        
        # Card number validation
        card_number = employee_data.get('card_number')
        if card_number:
            if Employee.objects.filter(
                card_number__card_number=card_number,
                is_active=True
            ).exclude(id=employee_data.get('id')).exists():
                errors.append("Card number is already assigned to another active employee")
        
        # Name validation
        given_name = employee_data.get('given_name', '')
        surname = employee_data.get('surname', '')
        
        if len(given_name) < 2:
            errors.append("Given name must be at least 2 characters")
        if len(surname) < 2:
            errors.append("Surname must be at least 2 characters")
            
        return len(errors) == 0, errors

    @staticmethod
    def get_employee_dashboard_stats() -> Dict[str, Any]:
        """Get employee statistics for dashboard."""
        total_employees = Employee.objects.filter(is_active=True).count()
        
        # Current clock status
        clocked_in_count = Employee.objects.filter(is_active=True, is_clocked_in=True).count()
        
        # Recent activity (last 24 hours)
        yesterday = timezone.now() - timedelta(hours=24)
        recent_events = Event.objects.filter(timestamp__gte=yesterday).count()
        
        # Department breakdown
        departments = {}
        for employee in Employee.objects.filter(is_active=True).select_related('card_number'):
            dept = 'Unknown'
            if employee.card_number:
                dept = normalize_department_from_designation(employee.card_number.designation) or 'Unknown'
            departments[dept] = departments.get(dept, 0) + 1
        
        return {
            'total_employees': total_employees,
            'clocked_in_count': clocked_in_count,
            'clocked_out_count': total_employees - clocked_in_count,
            'recent_events': recent_events,
            'department_breakdown': departments,
            'last_updated': timezone.now(),
        }

    @staticmethod
    def get_optimized_employee_data(days_back=30):
        """Get employee data with optimized bulk prefetch patterns."""
        from django.db.models import Prefetch
        from django.utils import timezone
        from datetime import timedelta
        
        # Calculate date range for recent events
        cutoff_date = timezone.now() - timedelta(days=days_back)
        
        # Get employees with optimized prefetch
        employees = Employee.objects.filter(
            is_active=True
        ).select_related(
            'department', 'card_number'
        ).prefetch_related(
            Prefetch(
                'employee_events',
                queryset=Event.objects.filter(
                    timestamp__gte=cutoff_date
                ).select_related('event_type', 'location').order_by('-timestamp'),
                to_attr='recent_events'
            )
        ).order_by('surname', 'given_name')
        
        return employees

    @staticmethod
    def get_employees_with_attendance_records(date, department=None):
        """Get employees with their attendance records for a specific date."""
        from django.db.models import Prefetch
        
        # Base employee query
        employees = Employee.objects.filter(is_active=True)
        
        # Apply department filter if specified
        if department:
            employees = employees.filter(department__name=department)
        
        # Optimize with select_related and prefetch_related
        employees = employees.select_related(
            'department', 'card_number'
        ).prefetch_related(
            Prefetch(
                'attendance_records',
                queryset=AttendanceRecord.objects.filter(date=date),
                to_attr='today_record'
            )
        ).order_by('surname', 'given_name')
        
        return employees