"""
REST API views (class-based views).

This module contains all DRF-based API endpoints for the attendance system.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from django.db.models import Q, Count, Avg
from datetime import datetime, timedelta, date, timezone, time
import json

from ..models import (
    Employee, Event, EventType, Location, AttendanceRecord, Card, Department,
    AnalyticsCache, ReportConfiguration, EmployeeAnalytics, DepartmentAnalytics, SystemPerformance,
    TaskAssignment, LocationMovement, LocationAnalytics
)
from ..serializers import (
    EmployeeSerializer,
    EventSerializer,
    LocationSerializer,
    SingleEventSerializer,
    DepartmentSerializer,
    AnalyticsCacheSerializer,
    ReportConfigurationSerializer,
    EmployeeAnalyticsSerializer,
    DepartmentAnalyticsSerializer,
    SystemPerformanceSerializer,
)
from ..permissions import SecurityPermission, AttendancePermission, ReportingPermission, AdminPermission


class SingleEventView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Event.
    Requires authentication for creating, updating or deleting.
    Uses PrimaryKeyRelatedFields for related objects during updates.
    """

    authentication_classes = [SessionAuthentication]  # Or TokenAuthentication, etc.
    permission_classes = [SecurityPermission]  # Security can view events
    serializer_class = SingleEventSerializer
    queryset = Event.objects.all()
    lookup_field = "id"


class SingleLocationView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Location.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [SecurityPermission]  # Security can view locations
    serializer_class = LocationSerializer
    queryset = Location.objects.all()
    lookup_field = "id"


class SingleEmployeeView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Employee.
    Requires authentication for creating, updating or deleting.
    Uses EmployeeSerializer which provides detailed info for retrieve
    and accepts IDs for related fields during updates.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AdminPermission]  # Only admin can manage employees
    serializer_class = EmployeeSerializer
    queryset = Employee.objects.all()
    lookup_field = "id"


class ListEventsView(generics.ListAPIView):
    """
    API endpoint for listing all Events.
    Requires authentication for creating, updating or deleting.
    Shows nested details of related objects.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [SecurityPermission]  # Security can view events
    serializer_class = EventSerializer  # Use the detailed serializer for listing
    queryset = (
        Event.objects.all()
        .select_related(  # Optimize query
            "event_type", "employee", "location", "created_by"
        )
        .order_by("-timestamp")
    )


class ListDepartmentsView(generics.ListAPIView):
    """
    API endpoint for listing all Departments.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [ReportingPermission]  # Reporting can view departments
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()


class SingleDepartmentView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Department.
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AdminPermission]  # Only admin can manage departments
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()
    lookup_field = "id"