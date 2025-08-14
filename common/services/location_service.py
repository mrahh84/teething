"""
Location Management Service

Handles all location-related business logic including location tracking,
assignments, and analytics.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from django.db import transaction
from django.db.models import Q, Count, Avg, QuerySet
from django.utils import timezone
from django.core.exceptions import ValidationError

from ..models import (
    Employee, Event, Location, TaskAssignment, LocationMovement, 
    LocationAnalytics, AttendanceRecord
)

logger = logging.getLogger(__name__)


class LocationService:
    """Service class for location management operations."""

    @staticmethod
    def get_location_by_id(location_id: int) -> Optional[Location]:
        """Get location by ID with related data."""
        try:
            return Location.objects.prefetch_related(
                'employee_set', 'taskassignment_set', 'event_set'
            ).get(id=location_id)
        except Location.DoesNotExist:
            return None

    @staticmethod
    def get_all_locations() -> QuerySet[Location]:
        """Get all locations with basic prefetching."""
        return Location.objects.prefetch_related('employee_set').order_by('name')

    @staticmethod
    def create_location(name: str, description: str = "", coordinates: str = "") -> Tuple[bool, str, Optional[Location]]:
        """Create a new location with validation."""
        try:
            # Validate name uniqueness
            if Location.objects.filter(name__iexact=name).exists():
                return False, "Location with this name already exists", None
            
            # Create location
            location = Location.objects.create(
                name=name.strip(),
                description=description.strip(),
                coordinates=coordinates.strip() if coordinates else ""
            )
            
            logger.info(f"Created location: {location.name}")
            return True, "Location created successfully", location
            
        except Exception as e:
            logger.error(f"Failed to create location {name}: {e}")
            return False, f"Failed to create location: {str(e)}", None

    @staticmethod
    def update_location(location_id: int, **updates) -> Tuple[bool, str]:
        """Update location information."""
        try:
            location = Location.objects.get(id=location_id)
            
            # Validate name uniqueness if name is being updated
            if 'name' in updates:
                new_name = updates['name'].strip()
                if Location.objects.filter(name__iexact=new_name).exclude(id=location_id).exists():
                    return False, "Location with this name already exists"
                updates['name'] = new_name
            
            # Update fields
            for field, value in updates.items():
                if hasattr(location, field):
                    setattr(location, field, value)
            
            location.save()
            logger.info(f"Updated location {location_id}")
            return True, "Location updated successfully"
            
        except Location.DoesNotExist:
            return False, "Location not found"
        except Exception as e:
            logger.error(f"Failed to update location {location_id}: {e}")
            return False, f"Failed to update location: {str(e)}"

    @staticmethod
    def delete_location(location_id: int) -> Tuple[bool, str]:
        """Delete a location if it's safe to do so."""
        try:
            location = Location.objects.get(id=location_id)
            
            # Check if location is in use
            if location.employee_set.exists():
                return False, "Cannot delete location: employees are assigned to it"
            
            if location.event_set.exists():
                return False, "Cannot delete location: it has associated events"
            
            if location.taskassignment_set.exists():
                return False, "Cannot delete location: it has task assignments"
            
            location_name = location.name
            location.delete()
            
            logger.info(f"Deleted location: {location_name}")
            return True, "Location deleted successfully"
            
        except Location.DoesNotExist:
            return False, "Location not found"
        except Exception as e:
            logger.error(f"Failed to delete location {location_id}: {e}")
            return False, f"Failed to delete location: {str(e)}"

    @staticmethod
    def assign_employee_to_location(employee_id: int, location_id: int) -> Tuple[bool, str]:
        """Assign an employee to a location."""
        try:
            employee = Employee.objects.get(id=employee_id, is_active=True)
            location = Location.objects.get(id=location_id)
            
            # Add location to employee's assigned locations
            employee.assigned_locations.add(location)
            
            logger.info(f"Assigned employee {employee_id} to location {location_id}")
            return True, f"Employee assigned to {location.name}"
            
        except Employee.DoesNotExist:
            return False, "Employee not found or inactive"
        except Location.DoesNotExist:
            return False, "Location not found"
        except Exception as e:
            logger.error(f"Failed to assign employee {employee_id} to location {location_id}: {e}")
            return False, f"Assignment failed: {str(e)}"

    @staticmethod
    def remove_employee_from_location(employee_id: int, location_id: int) -> Tuple[bool, str]:
        """Remove an employee from a location."""
        try:
            employee = Employee.objects.get(id=employee_id, is_active=True)
            location = Location.objects.get(id=location_id)
            
            # Remove location from employee's assigned locations
            employee.assigned_locations.remove(location)
            
            logger.info(f"Removed employee {employee_id} from location {location_id}")
            return True, f"Employee removed from {location.name}"
            
        except Employee.DoesNotExist:
            return False, "Employee not found or inactive"
        except Location.DoesNotExist:
            return False, "Location not found"
        except Exception as e:
            logger.error(f"Failed to remove employee {employee_id} from location {location_id}: {e}")
            return False, f"Removal failed: {str(e)}"

    @staticmethod
    def get_location_analytics(location_id: int, days_back: int = 30) -> Dict[str, Any]:
        """Get comprehensive analytics for a location."""
        location = LocationService.get_location_by_id(location_id)
        if not location:
            return {'error': 'Location not found'}
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        # Get events at this location
        events = Event.objects.filter(
            location=location,
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        ).select_related('employee', 'event_type').order_by('timestamp')
        
        # Get assigned employees
        assigned_employees = list(location.employee_set.filter(is_active=True))
        
        # Get task assignments
        task_assignments = TaskAssignment.objects.filter(
            location=location,
            assigned_date__gte=start_date,
            assigned_date__lte=end_date
        ).select_related('employee')
        
        # Calculate metrics
        total_events = events.count()
        unique_employees = events.values('employee').distinct().count()
        
        # Event type breakdown
        event_types = {}
        for event in events:
            event_type = event.event_type.name
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        # Daily activity
        daily_activity = {}
        for event in events:
            date_str = event.timestamp.date().strftime('%Y-%m-%d')
            daily_activity[date_str] = daily_activity.get(date_str, 0) + 1
        
        # Hourly distribution
        hourly_distribution = {}
        for event in events:
            hour = event.timestamp.hour
            hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1
        
        # Peak hour
        peak_hour = max(hourly_distribution.items(), key=lambda x: x[1])[0] if hourly_distribution else None
        
        # Employee activity
        employee_activity = {}
        for event in events:
            emp_id = event.employee.id
            if emp_id not in employee_activity:
                employee_activity[emp_id] = {
                    'employee': event.employee,
                    'event_count': 0,
                    'last_activity': None,
                }
            employee_activity[emp_id]['event_count'] += 1
            if not employee_activity[emp_id]['last_activity'] or event.timestamp > employee_activity[emp_id]['last_activity']:
                employee_activity[emp_id]['last_activity'] = event.timestamp
        
        # Task assignment metrics
        total_tasks = task_assignments.count()
        completed_tasks = task_assignments.filter(is_completed=True).count()
        completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
        
        # Average task duration for completed tasks
        completed_assignments = task_assignments.filter(is_completed=True, completed_date__isnull=False)
        total_duration = timedelta()
        for assignment in completed_assignments:
            if assignment.completed_date and assignment.assigned_date:
                duration = assignment.completed_date - assignment.assigned_date
                total_duration += duration
        
        avg_task_duration = None
        if completed_assignments.count() > 0:
            avg_duration_seconds = total_duration.total_seconds() / completed_assignments.count()
            avg_task_duration = avg_duration_seconds / 3600  # Convert to hours
        
        return {
            'location': location,
            'analysis_period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days_back,
            },
            'event_metrics': {
                'total_events': total_events,
                'unique_employees': unique_employees,
                'event_types': event_types,
                'peak_hour': peak_hour,
            },
            'activity_patterns': {
                'daily_activity': daily_activity,
                'hourly_distribution': hourly_distribution,
            },
            'employee_metrics': {
                'assigned_employees': len(assigned_employees),
                'active_employees': len(employee_activity),
                'employee_activity': list(employee_activity.values()),
            },
            'task_metrics': {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'completion_rate': round(completion_rate, 2),
                'avg_task_duration_hours': round(avg_task_duration, 2) if avg_task_duration else None,
            },
            'generated_at': timezone.now(),
        }

    @staticmethod
    def create_task_assignment(
        employee_id: int,
        location_id: int,
        task_description: str,
        due_date: Optional[date] = None,
        priority: str = "Medium"
    ) -> Tuple[bool, str, Optional[TaskAssignment]]:
        """Create a new task assignment."""
        try:
            with transaction.atomic():
                employee = Employee.objects.get(id=employee_id, is_active=True)
                location = Location.objects.get(id=location_id)
                
                # Validate priority
                valid_priorities = ["Low", "Medium", "High", "Critical"]
                if priority not in valid_priorities:
                    priority = "Medium"
                
                # Create task assignment
                task = TaskAssignment.objects.create(
                    employee=employee,
                    location=location,
                    task_description=task_description.strip(),
                    assigned_date=timezone.now().date(),
                    due_date=due_date,
                    priority=priority,
                    is_completed=False
                )
                
                logger.info(f"Created task assignment {task.id} for employee {employee_id} at location {location_id}")
                return True, "Task assignment created successfully", task
                
        except Employee.DoesNotExist:
            return False, "Employee not found or inactive", None
        except Location.DoesNotExist:
            return False, "Location not found", None
        except Exception as e:
            logger.error(f"Failed to create task assignment: {e}")
            return False, f"Failed to create task assignment: {str(e)}", None

    @staticmethod
    def complete_task_assignment(assignment_id: int, completion_notes: str = "") -> Tuple[bool, str]:
        """Mark a task assignment as completed."""
        try:
            assignment = TaskAssignment.objects.get(id=assignment_id)
            
            if assignment.is_completed:
                return False, "Task is already completed"
            
            assignment.is_completed = True
            assignment.completed_date = timezone.now().date()
            assignment.completion_notes = completion_notes.strip()
            assignment.save()
            
            logger.info(f"Completed task assignment {assignment_id}")
            return True, "Task marked as completed"
            
        except TaskAssignment.DoesNotExist:
            return False, "Task assignment not found"
        except Exception as e:
            logger.error(f"Failed to complete task assignment {assignment_id}: {e}")
            return False, f"Failed to complete task: {str(e)}"

    @staticmethod
    def get_employee_tasks(employee_id: int, include_completed: bool = False) -> QuerySet[TaskAssignment]:
        """Get task assignments for an employee."""
        tasks = TaskAssignment.objects.filter(
            employee_id=employee_id
        ).select_related('location').order_by('-assigned_date')
        
        if not include_completed:
            tasks = tasks.filter(is_completed=False)
        
        return tasks

    @staticmethod
    def get_location_tasks(location_id: int, include_completed: bool = False) -> QuerySet[TaskAssignment]:
        """Get task assignments for a location."""
        tasks = TaskAssignment.objects.filter(
            location_id=location_id
        ).select_related('employee').order_by('-assigned_date')
        
        if not include_completed:
            tasks = tasks.filter(is_completed=False)
        
        return tasks

    @staticmethod
    def get_overdue_tasks() -> QuerySet[TaskAssignment]:
        """Get all overdue task assignments."""
        today = timezone.now().date()
        return TaskAssignment.objects.filter(
            due_date__lt=today,
            is_completed=False
        ).select_related('employee', 'location').order_by('due_date')

    @staticmethod
    def bulk_assign_employees_to_location(
        employee_ids: List[int],
        location_id: int
    ) -> Dict[str, Any]:
        """Bulk assign multiple employees to a location."""
        results = {
            'successful': [],
            'failed': [],
            'total_processed': len(employee_ids),
        }
        
        try:
            location = Location.objects.get(id=location_id)
        except Location.DoesNotExist:
            return {
                'successful': [],
                'failed': [{'employee_id': eid, 'error': 'Location not found'} for eid in employee_ids],
                'total_processed': len(employee_ids),
            }
        
        for employee_id in employee_ids:
            success, message = LocationService.assign_employee_to_location(employee_id, location_id)
            
            if success:
                results['successful'].append({
                    'employee_id': employee_id,
                    'message': message,
                })
            else:
                results['failed'].append({
                    'employee_id': employee_id,
                    'error': message,
                })
        
        return results

    @staticmethod
    def get_location_utilization_report(days_back: int = 30) -> Dict[str, Any]:
        """Generate location utilization report."""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        locations = Location.objects.all()
        utilization_data = []
        
        for location in locations:
            # Get events at this location
            events = Event.objects.filter(
                location=location,
                timestamp__date__gte=start_date,
                timestamp__date__lte=end_date
            )
            
            # Get assigned employees
            assigned_count = location.employee_set.filter(is_active=True).count()
            
            # Get unique employees who actually used the location
            active_users = events.values('employee').distinct().count()
            
            # Calculate utilization rate
            utilization_rate = (active_users / assigned_count) * 100 if assigned_count > 0 else 0
            
            # Get task assignments
            tasks = TaskAssignment.objects.filter(
                location=location,
                assigned_date__gte=start_date,
                assigned_date__lte=end_date
            )
            
            utilization_data.append({
                'location': location,
                'assigned_employees': assigned_count,
                'active_users': active_users,
                'utilization_rate': round(utilization_rate, 2),
                'total_events': events.count(),
                'total_tasks': tasks.count(),
                'completed_tasks': tasks.filter(is_completed=True).count(),
            })
        
        # Sort by utilization rate (descending)
        utilization_data.sort(key=lambda x: x['utilization_rate'], reverse=True)
        
        return {
            'analysis_period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days_back,
            },
            'location_utilization': utilization_data,
            'summary': {
                'total_locations': len(locations),
                'avg_utilization': round(
                    sum(l['utilization_rate'] for l in utilization_data) / len(utilization_data), 2
                ) if utilization_data else 0,
                'most_utilized': utilization_data[0]['location'].name if utilization_data else None,
                'least_utilized': utilization_data[-1]['location'].name if utilization_data else None,
            },
            'generated_at': timezone.now(),
        }

    @staticmethod
    def validate_location_data(location_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate location data before creation/update."""
        errors = []
        
        # Required fields
        name = location_data.get('name', '').strip()
        if not name:
            errors.append("Location name is required")
        elif len(name) < 2:
            errors.append("Location name must be at least 2 characters")
        
        # Check name uniqueness (if creating or name changed)
        location_id = location_data.get('id')
        if name:
            existing_query = Location.objects.filter(name__iexact=name)
            if location_id:
                existing_query = existing_query.exclude(id=location_id)
            
            if existing_query.exists():
                errors.append("Location with this name already exists")
        
        # Validate coordinates format if provided
        coordinates = location_data.get('coordinates', '').strip()
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