"""
Validation Service

Handles all data validation and business rules for the attendance system.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union

from django.core.exceptions import ValidationError
from django.utils import timezone

from ..models import Employee, Event, EventType, Location, AttendanceRecord, Card


class ValidationService:
    """Service class for data validation and business rules."""

    @staticmethod
    def validate_employee_data(data: Dict[str, Any], employee_id: Optional[int] = None) -> Tuple[bool, List[str]]:
        """Comprehensive employee data validation."""
        errors = []
        
        # Required fields
        required_fields = ['given_name', 'surname']
        for field in required_fields:
            value = data.get(field, '').strip()
            if not value:
                errors.append(f"{field.replace('_', ' ').title()} is required")
            elif len(value) < 2:
                errors.append(f"{field.replace('_', ' ').title()} must be at least 2 characters")
            elif len(value) > 50:
                errors.append(f"{field.replace('_', ' ').title()} must not exceed 50 characters")
        
        # Name format validation
        for field in ['given_name', 'surname']:
            value = data.get(field, '').strip()
            if value and not re.match(r'^[a-zA-Z\s\'-]+$', value):
                errors.append(f"{field.replace('_', ' ').title()} can only contain letters, spaces, hyphens, and apostrophes")
        
        # Card number validation
        card_number = data.get('card_number', '').strip()
        if card_number:
            # Check format (adjust pattern as needed)
            if not re.match(r'^[A-Z0-9\-\.]+$', card_number):
                errors.append("Card number format is invalid")
            
            # Check uniqueness
            existing_employee = Employee.objects.filter(
                card_number__card_number=card_number,
                is_active=True
            )
            
            if employee_id:
                existing_employee = existing_employee.exclude(id=employee_id)
            
            if existing_employee.exists():
                errors.append("Card number is already assigned to another active employee")
        
        # Employee number validation
        employee_number = data.get('employee_number', '').strip()
        if employee_number:
            if not re.match(r'^[A-Z0-9\-]+$', employee_number):
                errors.append("Employee number format is invalid")
            
            # Check uniqueness
            existing_employee = Employee.objects.filter(employee_number=employee_number)
            if employee_id:
                existing_employee = existing_employee.exclude(id=employee_id)
            
            if existing_employee.exists():
                errors.append("Employee number is already in use")
        
        # Email validation (if provided)
        email = data.get('email', '').strip()
        if email:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                errors.append("Email format is invalid")
        
        return len(errors) == 0, errors

    @staticmethod
    def validate_event_data(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate event/clock-in data."""
        errors = []
        
        # Required fields
        employee_id = data.get('employee_id')
        if not employee_id:
            errors.append("Employee ID is required")
        else:
            # Validate employee exists and is active
            try:
                employee = Employee.objects.get(id=employee_id, is_active=True)
            except Employee.DoesNotExist:
                errors.append("Employee not found or inactive")
                employee = None
        
        # Event type validation
        event_type = data.get('event_type', '').strip()
        if not event_type:
            errors.append("Event type is required")
        
        # Location validation
        location_id = data.get('location_id')
        if location_id:
            try:
                Location.objects.get(id=location_id)
            except Location.DoesNotExist:
                errors.append("Invalid location specified")
        
        # Timestamp validation
        timestamp = data.get('timestamp')
        if timestamp:
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except ValueError:
                    errors.append("Invalid timestamp format")
            
            # Check if timestamp is not too far in the future
            if timestamp and timestamp > timezone.now() + timedelta(minutes=5):
                errors.append("Timestamp cannot be more than 5 minutes in the future")
        
        # Business logic validation
        if employee_id and event_type and not errors:
            try:
                employee = Employee.objects.get(id=employee_id, is_active=True)
                
                event_type_lower = event_type.lower()
                if 'clock in' in event_type_lower or 'in' in event_type_lower:
                    if employee.is_clocked_in:
                        errors.append("Employee is already clocked in")
                elif 'clock out' in event_type_lower or 'out' in event_type_lower:
                    if not employee.is_clocked_in:
                        errors.append("Employee is not currently clocked in")
                        
            except Employee.DoesNotExist:
                pass  # Already handled above
        
        return len(errors) == 0, errors

    @staticmethod
    def validate_attendance_record(data: Dict[str, Any], record_id: Optional[int] = None) -> Tuple[bool, List[str]]:
        """Validate attendance record data."""
        errors = []
        
        # Employee validation
        employee_id = data.get('employee_id')
        if not employee_id:
            errors.append("Employee ID is required")
        else:
            try:
                Employee.objects.get(id=employee_id, is_active=True)
            except Employee.DoesNotExist:
                errors.append("Employee not found or inactive")
        
        # Date validation
        attendance_date = data.get('date')
        if not attendance_date:
            errors.append("Date is required")
        else:
            if isinstance(attendance_date, str):
                try:
                    attendance_date = datetime.strptime(attendance_date, '%Y-%m-%d').date()
                except ValueError:
                    errors.append("Invalid date format (YYYY-MM-DD required)")
            
            # Check if date is not too far in the future
            if attendance_date and attendance_date > timezone.now().date():
                errors.append("Attendance date cannot be in the future")
            
            # Check for duplicates
            if employee_id and attendance_date:
                existing_record = AttendanceRecord.objects.filter(
                    employee_id=employee_id,
                    date=attendance_date
                )
                
                if record_id:
                    existing_record = existing_record.exclude(id=record_id)
                
                if existing_record.exists():
                    errors.append("Attendance record already exists for this employee and date")
        
        # Status validation
        status = data.get('status', '').strip()
        valid_statuses = ['On Time', 'Early', 'Late', 'Absent']
        if status and status not in valid_statuses:
            errors.append(f"Status must be one of: {', '.join(valid_statuses)}")
        
        # Time validation
        arrival_time = data.get('arrival_time')
        departure_time = data.get('departure_time')
        
        if arrival_time and isinstance(arrival_time, str):
            try:
                arrival_time = datetime.strptime(arrival_time, '%H:%M').time()
            except ValueError:
                errors.append("Invalid arrival time format (HH:MM required)")
        
        if departure_time and isinstance(departure_time, str):
            try:
                departure_time = datetime.strptime(departure_time, '%H:%M').time()
            except ValueError:
                errors.append("Invalid departure time format (HH:MM required)")
        
        # Check logical time sequence
        if arrival_time and departure_time:
            if departure_time <= arrival_time:
                errors.append("Departure time must be after arrival time")
        
        # Completion percentage validation
        completion_percentage = data.get('completion_percentage')
        if completion_percentage is not None:
            try:
                completion_percentage = float(completion_percentage)
                if completion_percentage < 0 or completion_percentage > 100:
                    errors.append("Completion percentage must be between 0 and 100")
            except (ValueError, TypeError):
                errors.append("Completion percentage must be a valid number")
        
        return len(errors) == 0, errors

    @staticmethod
    def validate_location_data(data: Dict[str, Any], location_id: Optional[int] = None) -> Tuple[bool, List[str]]:
        """Validate location data."""
        errors = []
        
        # Name validation
        name = data.get('name', '').strip()
        if not name:
            errors.append("Location name is required")
        elif len(name) < 2:
            errors.append("Location name must be at least 2 characters")
        elif len(name) > 100:
            errors.append("Location name must not exceed 100 characters")
        
        # Check name uniqueness
        if name:
            existing_location = Location.objects.filter(name__iexact=name)
            if location_id:
                existing_location = existing_location.exclude(id=location_id)
            
            if existing_location.exists():
                errors.append("Location with this name already exists")
        
        # Description validation
        description = data.get('description', '').strip()
        if description and len(description) > 500:
            errors.append("Description must not exceed 500 characters")
        
        # Coordinates validation
        coordinates = data.get('coordinates', '').strip()
        if coordinates:
            # Basic validation for lat,lng format
            parts = coordinates.split(',')
            if len(parts) != 2:
                errors.append("Coordinates must be in 'latitude,longitude' format")
            else:
                try:
                    lat, lng = float(parts[0].strip()), float(parts[1].strip())
                    if not (-90 <= lat <= 90):
                        errors.append("Latitude must be between -90 and 90")
                    if not (-180 <= lng <= 180):
                        errors.append("Longitude must be between -180 and 180")
                except ValueError:
                    errors.append("Coordinates must be valid numbers")
        
        return len(errors) == 0, errors

    @staticmethod
    def validate_time_range(start_time: Union[str, time, datetime], end_time: Union[str, time, datetime]) -> Tuple[bool, str]:
        """Validate time range makes logical sense."""
        try:
            # Convert strings to time objects if needed
            if isinstance(start_time, str):
                start_time = datetime.strptime(start_time, '%H:%M').time()
            elif isinstance(start_time, datetime):
                start_time = start_time.time()
            
            if isinstance(end_time, str):
                end_time = datetime.strptime(end_time, '%H:%M').time()
            elif isinstance(end_time, datetime):
                end_time = end_time.time()
            
            if end_time <= start_time:
                return False, "End time must be after start time"
            
            return True, "Valid time range"
            
        except ValueError as e:
            return False, f"Invalid time format: {e}"

    @staticmethod
    def validate_date_range(start_date: Union[str, date], end_date: Union[str, date]) -> Tuple[bool, str]:
        """Validate date range makes logical sense."""
        try:
            # Convert strings to date objects if needed
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            if end_date < start_date:
                return False, "End date must be after or equal to start date"
            
            # Check if range is reasonable (not more than 1 year)
            if (end_date - start_date).days > 365:
                return False, "Date range cannot exceed 1 year"
            
            return True, "Valid date range"
            
        except ValueError as e:
            return False, f"Invalid date format: {e}"

    @staticmethod
    def validate_bulk_operation(operation_type: str, item_ids: List[int], max_items: int = 100) -> Tuple[bool, List[str]]:
        """Validate bulk operation parameters."""
        errors = []
        
        # Operation type validation
        valid_operations = [
            'bulk_clock_in', 'bulk_clock_out', 'bulk_activate', 'bulk_deactivate',
            'bulk_assign_location', 'bulk_remove_location', 'bulk_delete'
        ]
        
        if operation_type not in valid_operations:
            errors.append(f"Invalid operation type. Must be one of: {', '.join(valid_operations)}")
        
        # Item count validation
        if not item_ids:
            errors.append("At least one item must be selected")
        elif len(item_ids) > max_items:
            errors.append(f"Cannot process more than {max_items} items at once")
        
        # ID validation
        for item_id in item_ids:
            if not isinstance(item_id, int) or item_id <= 0:
                errors.append(f"Invalid ID: {item_id}")
                break
        
        return len(errors) == 0, errors

    @staticmethod
    def validate_report_parameters(params: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate report generation parameters."""
        errors = []
        
        # Date range validation
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        if start_date and end_date:
            valid, message = ValidationService.validate_date_range(start_date, end_date)
            if not valid:
                errors.append(message)
        
        # Department validation
        department = params.get('department')
        if department and department != 'all':
            # Could add department validation here if you have a Department model
            pass
        
        # Employee validation
        employee_ids = params.get('employee_ids', [])
        if employee_ids:
            if not isinstance(employee_ids, list):
                errors.append("Employee IDs must be provided as a list")
            else:
                for emp_id in employee_ids:
                    if not isinstance(emp_id, int) or emp_id <= 0:
                        errors.append(f"Invalid employee ID: {emp_id}")
                        break
        
        # Report type validation
        report_type = params.get('report_type')
        valid_report_types = [
            'attendance_summary', 'employee_detail', 'department_analysis',
            'period_summary', 'overtime_report', 'pattern_analysis'
        ]
        
        if report_type and report_type not in valid_report_types:
            errors.append(f"Invalid report type. Must be one of: {', '.join(valid_report_types)}")
        
        return len(errors) == 0, errors

    @staticmethod
    def validate_business_rules(operation: str, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate business-specific rules."""
        errors = []
        
        if operation == 'clock_in':
            # Business hours validation
            current_time = timezone.now().time()
            
            # Example: No clock-ins after 10 PM or before 5 AM
            if current_time >= time(22, 0) or current_time <= time(5, 0):
                errors.append("Clock-in not allowed outside business hours (5 AM - 10 PM)")
            
        elif operation == 'attendance_record':
            # Check if trying to modify old records
            record_date = data.get('date')
            if record_date:
                if isinstance(record_date, str):
                    record_date = datetime.strptime(record_date, '%Y-%m-%d').date()
                
                days_ago = (timezone.now().date() - record_date).days
                if days_ago > 30:
                    errors.append("Cannot modify attendance records older than 30 days")
        
        elif operation == 'employee_activation':
            # Example: Cannot deactivate employees with pending tasks
            employee_id = data.get('employee_id')
            is_active = data.get('is_active')
            
            if employee_id and is_active is False:
                # Check for pending tasks (if TaskAssignment model exists)
                try:
                    from ..models import TaskAssignment
                    pending_tasks = TaskAssignment.objects.filter(
                        employee_id=employee_id,
                        is_completed=False
                    ).count()
                    
                    if pending_tasks > 0:
                        errors.append(f"Cannot deactivate employee with {pending_tasks} pending tasks")
                except ImportError:
                    pass  # TaskAssignment model doesn't exist
        
        return len(errors) == 0, errors

    @staticmethod
    def sanitize_input(data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize input data to prevent common security issues."""
        sanitized = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                # Remove potentially dangerous characters and trim whitespace
                sanitized_value = value.strip()
                
                # Remove HTML tags (basic sanitization)
                sanitized_value = re.sub(r'<[^>]+>', '', sanitized_value)
                
                # Remove null bytes
                sanitized_value = sanitized_value.replace('\x00', '')
                
                # Limit length for text fields
                if len(sanitized_value) > 1000:  # Reasonable default limit
                    sanitized_value = sanitized_value[:1000]
                
                sanitized[key] = sanitized_value
            else:
                sanitized[key] = value
        
        return sanitized

    @staticmethod
    def validate_api_input(data: Dict[str, Any], required_fields: List[str]) -> Tuple[bool, List[str]]:
        """Generic API input validation."""
        errors = []
        
        # Check required fields
        for field in required_fields:
            if field not in data or data[field] is None:
                errors.append(f"Field '{field}' is required")
            elif isinstance(data[field], str) and not data[field].strip():
                errors.append(f"Field '{field}' cannot be empty")
        
        # Check for unexpected fields (optional - helps catch typos)
        allowed_fields = set(required_fields + [
            'id', 'created_at', 'updated_at', 'notes', 'description', 'metadata'
        ])
        
        unexpected_fields = set(data.keys()) - allowed_fields
        if unexpected_fields:
            errors.append(f"Unexpected fields: {', '.join(unexpected_fields)}")
        
        return len(errors) == 0, errors