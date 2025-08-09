"""
Location tracking and assignment views.

This module contains all location-related functionality including
location dashboards, assignments, and analytics.
Migrated from legacy_views.py as part of Phase 2 modularization.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as django_timezone
from drf_spectacular.utils import extend_schema
from django.db.models import Q, Count
from datetime import datetime, timedelta, date
from django.http import JsonResponse
import json

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


# NOTE: These functions delegate to legacy implementations for now
# In production, they would be fully migrated with complete implementations

def location_dashboard(request):
    """Location dashboard with assignments and analytics."""
    # Implementation from legacy_views.py line 3784
    from ..legacy_views import location_dashboard as legacy_location_dashboard
    return legacy_location_dashboard(request)

def location_analytics_api(request, location_id):
    """API endpoint for location analytics."""
    # Implementation from legacy_views.py line 3836
    from ..legacy_views import location_analytics_api as legacy_location_analytics_api
    return legacy_location_analytics_api(request, location_id)

def employee_locations_api(request):
    """API endpoint for employee location data."""
    # Implementation from legacy_views.py line 3872
    from ..legacy_views import employee_locations_api as legacy_employee_locations_api
    return legacy_employee_locations_api(request)

def location_summary_api(request):
    """API endpoint for location summary data."""
    # Implementation from legacy_views.py line 3894
    from ..legacy_views import location_summary_api as legacy_location_summary_api
    return legacy_location_summary_api(request)

def location_assignment_list(request):
    """List view for location assignments."""
    # Implementation from legacy_views.py line 3927
    from ..legacy_views import location_assignment_list as legacy_location_assignment_list
    return legacy_location_assignment_list(request)

def location_assignment_create(request):
    """Create new location assignment."""
    # Implementation from legacy_views.py line 3972
    from ..legacy_views import location_assignment_create as legacy_location_assignment_create
    return legacy_location_assignment_create(request)

def location_assignment_edit(request, assignment_id):
    """Edit existing location assignment."""
    # Implementation from legacy_views.py line 4005
    from ..legacy_views import location_assignment_edit as legacy_location_assignment_edit
    return legacy_location_assignment_edit(request, assignment_id)

def location_assignment_delete(request, assignment_id):
    """Delete location assignment."""
    # Implementation from legacy_views.py line 4046
    from ..legacy_views import location_assignment_delete as legacy_location_assignment_delete
    return legacy_location_assignment_delete(request, assignment_id)

def bulk_location_assignment(request):
    """Bulk location assignment operations."""
    # Implementation from legacy_views.py line 4071
    from ..legacy_views import bulk_location_assignment as legacy_bulk_location_assignment
    return legacy_bulk_location_assignment(request)

def location_assignment_complete(request, assignment_id):
    """Mark location assignment as complete."""
    # Implementation from legacy_views.py line 4142
    from ..legacy_views import location_assignment_complete as legacy_location_assignment_complete
    return legacy_location_assignment_complete(request, assignment_id)