"""
Utility functions for views.
"""
from ..services.attendance_service import (
    normalize_department_from_designation as svc_normalize_department_from_designation,
    list_available_departments as svc_list_available_departments,
    filter_employees_by_department as svc_filter_employees_by_department,
)


def get_department_from_designation(designation):
    """Deprecated: use services.attendance_service.normalize_department_from_designation."""
    return svc_normalize_department_from_designation(designation)


def get_available_departments():
    """Deprecated: use services.attendance_service.list_available_departments."""
    return svc_list_available_departments()


def filter_employees_by_department(employees, department):
    """Deprecated: use services.attendance_service.filter_employees_by_department."""
    return svc_filter_employees_by_department(employees, department)