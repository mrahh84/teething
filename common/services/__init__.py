"""
Service Layer Package

This package contains all business logic services for the attendance system.
Services encapsulate domain logic and provide clean interfaces for views and other layers.

Architecture:
- Each service focuses on a specific domain (employees, events, reporting, etc.)
- Services handle business rules, validations, and complex operations
- Views delegate to services instead of directly accessing models
- Services can call other services but avoid circular dependencies

Services Available:
- AttendanceService: Core attendance and time tracking logic
- EmployeeService: Employee management and operations
- EventService: Clock-in/out events and time calculations
- ReportingService: Analytics, reports, and data aggregation
- LocationService: Location tracking and assignments
- AnalyticsService: Pattern recognition and predictive analytics
- ValidationService: Data validation and business rules
- NotificationService: Alerts and notifications
"""

# Import all services for easy access
from .attendance_service import (
    normalize_department_from_designation,
    list_available_departments,
    filter_employees_by_department,
)

__all__ = [
    # Attendance Service
    'normalize_department_from_designation',
    'list_available_departments', 
    'filter_employees_by_department',
    
    # Other services will be added as they're implemented
    'EmployeeService',
    'EventService',
    'ReportingService',
    'LocationService',
    'AnalyticsService',
    'ValidationService',
    'NotificationService',
]

# Service class imports
from .employee_service import EmployeeService
from .event_service import EventService
from .reporting_service import ReportingService
from .location_service import LocationService
from .analytics_service import AnalyticsService
from .validation_service import ValidationService
from .notification_service import NotificationService