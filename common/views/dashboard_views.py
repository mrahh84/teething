"""
Dashboard and analytics views.

This module contains advanced analytics dashboards including
pattern recognition and predictive analytics.
Migrated from legacy_views.py as part of Phase 2 modularization.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as django_timezone
from drf_spectacular.utils import extend_schema
from django.db.models import Q, Count
from datetime import datetime, timedelta, date
import json

from ..models import (
    Employee, Event, EventType, Location, AttendanceRecord, Card, Department,
    AnalyticsCache, ReportConfiguration, EmployeeAnalytics, DepartmentAnalytics, SystemPerformance,
)
from ..services.attendance_service import (
    normalize_department_from_designation as svc_normalize_department_from_designation,
    list_available_departments as svc_list_available_departments,
    filter_employees_by_department as svc_filter_employees_by_department,
)
from ..decorators import security_required, attendance_required, reporting_required, admin_required


# NOTE: These functions delegate to legacy implementations for now
# In production, they would be fully migrated with complete implementations

def pattern_recognition_dashboard(request):
    """Pattern recognition dashboard for attendance analysis."""
    # Implementation from legacy_views.py line 4625
    from ..legacy_views import pattern_recognition_dashboard as legacy_pattern_recognition_dashboard
    return legacy_pattern_recognition_dashboard(request)


def predictive_analytics_dashboard(request):
    """Predictive analytics dashboard with forecasting."""
    # Implementation from legacy_views.py line 4752
    from ..legacy_views import predictive_analytics_dashboard as legacy_predictive_analytics_dashboard
    return legacy_predictive_analytics_dashboard(request)