"""
Event Management Service

Handles all event-related business logic including clock-in/out operations,
time calculations, and event validations.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple, Any

from django.db import transaction
from django.db.models import Q, QuerySet, Max, Min
from django.utils import timezone
from django.core.exceptions import ValidationError

from ..models import Employee, Event, EventType, Location, AttendanceRecord

logger = logging.getLogger(__name__)


class EventService:
    """Service class for event management operations."""

    @staticmethod
    def clock_in_employee(
        employee_id: int, 
        location_id: Optional[int] = None,
        event_type: str = "Clock In",
        notes: str = ""
    ) -> Tuple[bool, str, Optional[Event]]:
        """
        Clock in an employee with validation and business logic.
        
        Returns:
            Tuple of (success, message, event_object)
        """
        try:
            with transaction.atomic():
                employee = Employee.objects.get(id=employee_id, is_active=True)
                
                # Validation: Check if already clocked in
                if employee.is_clocked_in:
                    return False, "Employee is already clocked in", None
                
                # Get or create event type
                event_type_obj, _ = EventType.objects.get_or_create(name=event_type)
                
                # Get location if provided
                location = None
                if location_id:
                    try:
                        location = Location.objects.get(id=location_id)
                    except Location.DoesNotExist:
                        return False, "Invalid location specified", None
                
                # Create the clock-in event
                event = Event.objects.create(
                    employee=employee,
                    event_type=event_type_obj,
                    location=location,
                    timestamp=timezone.now(),
                    notes=notes
                )
                
                # Update employee status
                employee.is_clocked_in = True
                employee.last_clockinout_time = event.timestamp
                employee.save(update_fields=['is_clocked_in', 'last_clockinout_time'])
                
                logger.info(f"Employee {employee_id} clocked in successfully")
                return True, "Clock in successful", event
                
        except Employee.DoesNotExist:
            return False, "Employee not found or inactive", None
        except Exception as e:
            logger.error(f"Clock in failed for employee {employee_id}: {e}")
            return False, f"Clock in failed: {str(e)}", None

    @staticmethod
    def clock_out_employee(
        employee_id: int,
        location_id: Optional[int] = None,
        event_type: str = "Clock Out",
        notes: str = ""
    ) -> Tuple[bool, str, Optional[Event]]:
        """
        Clock out an employee with validation and business logic.
        
        Returns:
            Tuple of (success, message, event_object)
        """
        try:
            with transaction.atomic():
                employee = Employee.objects.get(id=employee_id, is_active=True)
                
                # Validation: Check if actually clocked in
                if not employee.is_clocked_in:
                    return False, "Employee is not currently clocked in", None
                
                # Get or create event type
                event_type_obj, _ = EventType.objects.get_or_create(name=event_type)
                
                # Get location if provided
                location = None
                if location_id:
                    try:
                        location = Location.objects.get(id=location_id)
                    except Location.DoesNotExist:
                        return False, "Invalid location specified", None
                
                # Create the clock-out event
                event = Event.objects.create(
                    employee=employee,
                    event_type=event_type_obj,
                    location=location,
                    timestamp=timezone.now(),
                    notes=notes
                )
                
                # Update employee status
                employee.is_clocked_in = False
                employee.last_clockinout_time = event.timestamp
                employee.save(update_fields=['is_clocked_in', 'last_clockinout_time'])
                
                # Create or update attendance record for today
                EventService._update_attendance_record(employee, event.timestamp.date())
                
                logger.info(f"Employee {employee_id} clocked out successfully")
                return True, "Clock out successful", event
                
        except Employee.DoesNotExist:
            return False, "Employee not found or inactive", None
        except Exception as e:
            logger.error(f"Clock out failed for employee {employee_id}: {e}")
            return False, f"Clock out failed: {str(e)}", None

    @staticmethod
    def _update_attendance_record(employee: Employee, date: datetime.date) -> None:
        """Update or create attendance record for the given date."""
        try:
            # Get all events for this employee on this date
            events = Event.objects.filter(
                employee=employee,
                timestamp__date=date
            ).order_by('timestamp')
            
            if not events.exists():
                return
            
            # Calculate attendance metrics
            first_event = events.first()
            last_event = events.last()
            
            arrival_time = first_event.timestamp.time()
            departure_time = last_event.timestamp.time() if events.count() > 1 else None
            
            # Determine status based on arrival time and assigned times
            status = EventService._calculate_attendance_status(employee, arrival_time)
            
            # Get or create attendance record
            attendance_record, created = AttendanceRecord.objects.get_or_create(
                employee=employee,
                date=date,
                defaults={
                    'arrival_time': arrival_time,
                    'departure_time': departure_time,
                    'status': status,
                }
            )
            
            if not created:
                # Update existing record
                attendance_record.arrival_time = arrival_time
                attendance_record.departure_time = departure_time
                attendance_record.status = status
                attendance_record.save()
                
        except Exception as e:
            logger.error(f"Failed to update attendance record for {employee.id} on {date}: {e}")

    @staticmethod
    def _calculate_attendance_status(employee: Employee, arrival_time: time) -> str:
        """Calculate attendance status based on arrival time."""
        # Default business hours (can be made configurable)
        standard_start_time = time(8, 0)  # 8:00 AM
        early_threshold = time(7, 30)     # Before 7:30 AM is early
        late_threshold = time(8, 30)      # After 8:30 AM is late
        
        # Use employee's assigned arrival time if available
        if employee.assigned_arrival_time:
            assigned_time = employee.assigned_arrival_time.time
            early_threshold = (datetime.combine(datetime.today(), assigned_time) - timedelta(minutes=30)).time()
            late_threshold = (datetime.combine(datetime.today(), assigned_time) + timedelta(minutes=30)).time()
            standard_start_time = assigned_time
        
        if arrival_time <= early_threshold:
            return "Early"
        elif arrival_time <= standard_start_time:
            return "On Time"
        elif arrival_time <= late_threshold:
            return "On Time"  # Within grace period
        else:
            return "Late"

    @staticmethod
    def get_employee_events(
        employee_id: int,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        limit: int = 50
    ) -> QuerySet[Event]:
        """Get events for an employee within a date range."""
        events = Event.objects.filter(employee_id=employee_id).select_related(
            'event_type', 'location', 'employee'
        ).order_by('-timestamp')
        
        if start_date:
            events = events.filter(timestamp__date__gte=start_date)
        if end_date:
            events = events.filter(timestamp__date__lte=end_date)
            
        return events[:limit]

    @staticmethod
    def get_daily_events_summary(date: datetime.date) -> Dict[str, Any]:
        """Get summary of all events for a specific date."""
        events = Event.objects.filter(timestamp__date=date).select_related(
            'employee', 'event_type', 'location'
        ).order_by('timestamp')
        
        # Categorize events
        clock_ins = events.filter(event_type__name__icontains='clock in')
        clock_outs = events.filter(event_type__name__icontains='clock out')
        
        # Calculate metrics
        total_events = events.count()
        unique_employees = events.values('employee').distinct().count()
        
        # Time distribution
        hourly_distribution = {}
        for event in events:
            hour = event.timestamp.hour
            hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1
        
        # Location distribution
        location_distribution = {}
        for event in events.filter(location__isnull=False):
            loc_name = event.location.name
            location_distribution[loc_name] = location_distribution.get(loc_name, 0) + 1
        
        return {
            'date': date,
            'total_events': total_events,
            'clock_ins': clock_ins.count(),
            'clock_outs': clock_outs.count(),
            'unique_employees': unique_employees,
            'hourly_distribution': hourly_distribution,
            'location_distribution': location_distribution,
            'events': events,
        }

    @staticmethod
    def calculate_work_duration(employee_id: int, date: datetime.date) -> Optional[timedelta]:
        """Calculate total work duration for an employee on a specific date."""
        events = Event.objects.filter(
            employee_id=employee_id,
            timestamp__date=date
        ).order_by('timestamp')
        
        if events.count() < 2:
            return None
        
        total_duration = timedelta()
        clock_in_time = None
        
        for event in events:
            event_name = event.event_type.name.lower()
            
            if 'clock in' in event_name or 'in' in event_name:
                clock_in_time = event.timestamp
            elif 'clock out' in event_name or 'out' in event_name:
                if clock_in_time:
                    duration = event.timestamp - clock_in_time
                    total_duration += duration
                    clock_in_time = None
        
        return total_duration if total_duration.total_seconds() > 0 else None

    @staticmethod
    def get_overtime_analysis(
        start_date: datetime.date,
        end_date: datetime.date,
        standard_hours: float = 8.0
    ) -> List[Dict[str, Any]]:
        """Analyze overtime for all employees in a date range."""
        overtime_data = []
        
        employees = Employee.objects.filter(is_active=True)
        
        for employee in employees:
            total_hours = 0
            overtime_hours = 0
            working_days = 0
            
            current_date = start_date
            while current_date <= end_date:
                duration = EventService.calculate_work_duration(employee.id, current_date)
                if duration:
                    hours = duration.total_seconds() / 3600
                    total_hours += hours
                    working_days += 1
                    
                    if hours > standard_hours:
                        overtime_hours += (hours - standard_hours)
                
                current_date += timedelta(days=1)
            
            if working_days > 0:
                overtime_data.append({
                    'employee': employee,
                    'total_hours': round(total_hours, 2),
                    'overtime_hours': round(overtime_hours, 2),
                    'working_days': working_days,
                    'average_daily_hours': round(total_hours / working_days, 2),
                })
        
        # Sort by overtime hours (descending)
        overtime_data.sort(key=lambda x: x['overtime_hours'], reverse=True)
        
        return overtime_data

    @staticmethod
    def bulk_clock_operation(
        employee_ids: List[int],
        operation: str,
        location_id: Optional[int] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Perform bulk clock in/out operations."""
        results = {
            'successful': [],
            'failed': [],
            'total_processed': len(employee_ids),
        }
        
        for employee_id in employee_ids:
            if operation.lower() == 'clock_in':
                success, message, event = EventService.clock_in_employee(
                    employee_id, location_id, "Clock In", notes
                )
            elif operation.lower() == 'clock_out':
                success, message, event = EventService.clock_out_employee(
                    employee_id, location_id, "Clock Out", notes
                )
            else:
                success, message, event = False, "Invalid operation", None
            
            if success:
                results['successful'].append({
                    'employee_id': employee_id,
                    'event_id': event.id if event else None,
                    'message': message,
                })
            else:
                results['failed'].append({
                    'employee_id': employee_id,
                    'error': message,
                })
        
        return results

    @staticmethod
    def validate_event_data(event_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate event data before creation."""
        errors = []
        
        # Required fields
        if not event_data.get('employee_id'):
            errors.append("Employee ID is required")
        
        if not event_data.get('event_type'):
            errors.append("Event type is required")
        
        # Validate employee exists
        employee_id = event_data.get('employee_id')
        if employee_id:
            try:
                employee = Employee.objects.get(id=employee_id, is_active=True)
                
                # Business logic validation
                event_type = event_data.get('event_type', '').lower()
                if 'clock in' in event_type and employee.is_clocked_in:
                    errors.append("Employee is already clocked in")
                elif 'clock out' in event_type and not employee.is_clocked_in:
                    errors.append("Employee is not currently clocked in")
                    
            except Employee.DoesNotExist:
                errors.append("Employee not found or inactive")
        
        # Validate location if provided
        location_id = event_data.get('location_id')
        if location_id:
            if not Location.objects.filter(id=location_id).exists():
                errors.append("Invalid location specified")
        
        return len(errors) == 0, errors

    @staticmethod
    def get_event_statistics(days_back: int = 30) -> Dict[str, Any]:
        """Get event statistics for dashboard."""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        events = Event.objects.filter(
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        )
        
        total_events = events.count()
        
        # Event type breakdown
        event_types = {}
        for event in events.select_related('event_type'):
            event_type = event.event_type.name
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        # Daily trend
        daily_counts = {}
        for event in events:
            date_str = event.timestamp.date().strftime('%Y-%m-%d')
            daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
        
        # Peak hours analysis
        hourly_counts = {}
        for event in events:
            hour = event.timestamp.hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        
        peak_hour = max(hourly_counts.items(), key=lambda x: x[1])[0] if hourly_counts else None
        
        return {
            'total_events': total_events,
            'event_types': event_types,
            'daily_trend': daily_counts,
            'hourly_distribution': hourly_counts,
            'peak_hour': peak_hour,
            'analysis_period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days_back,
            },
        }