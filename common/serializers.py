from rest_framework import serializers

from common.models import (
    Card, Employee, Event, EventType, Location, Department, AnalyticsCache,
    ReportConfiguration, EmployeeAnalytics, DepartmentAnalytics, SystemPerformance
)


class CardSerializer(serializers.ModelSerializer):
    """Serializer for the Card model."""

    class Meta:
        model = Card
        fields = "__all__"


class LocationSerializer(serializers.ModelSerializer):
    """Serializer for the Location model."""

    class Meta:
        model = Location
        fields = "__all__"


class EventTypeSerializer(serializers.ModelSerializer):
    """Serializer for the EventType model."""

    class Meta:
        model = EventType
        fields = "__all__"


class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for the Department model."""

    class Meta:
        model = Department
        fields = "__all__"


class EmployeeSerializer(serializers.ModelSerializer):
    """Serializer for the Employee model, including clock-in status."""

    # Use the model's methods/properties directly
    is_clocked_in = serializers.BooleanField(read_only=True)
    last_clockinout_time = serializers.DateTimeField(read_only=True)
    # Serialize the related card number designation for convenience
    card_designation = serializers.CharField(
        source="card_number.designation", read_only=True, allow_null=True
    )
    # Department information
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    # Provide IDs for related objects for easier linking/updates if needed
    assigned_location_ids = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(),
        source="assigned_locations",
        many=True,
        write_only=True,
        required=False,
    )
    card_id = serializers.PrimaryKeyRelatedField(
        queryset=Card.objects.all(),
        source="card_number",
        write_only=True,
        allow_null=True,
        required=False,
    )
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True,
        allow_null=True,
        required=False,
    )
    # Real-time status fields
    current_status = serializers.SerializerMethodField()
    last_activity = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        # List fields explicitly for clarity and control
        fields = [
            "id",
            "given_name",
            "surname",
            "card_number",
            "card_designation",
            "department",
            "department_name",
            "assigned_locations",
            "is_clocked_in",
            "last_clockinout_time",
            "assigned_lunch_time",
            "assigned_departure_time",
            "is_active",
            # Write-only fields for updates via API:
            "assigned_location_ids",
            "card_id",
            "department_id",
            # Real-time fields
            "current_status",
            "last_activity",
        ]
        # Make related fields read-only in the default representation
        read_only_fields = [
            "card_number",
            "department",
            "assigned_locations",
            "is_clocked_in",
            "last_clockinout_time",
            "current_status",
            "last_activity",
        ]

    def get_current_status(self, obj):
        """Get current employee status (clocked in/out)"""
        from django.utils import timezone
        from datetime import timedelta

        today = timezone.now().date()

        # Check if employee has clocked in today
        clock_in_today = obj.employee_events.filter(
            event_type__name='Clock In',
            timestamp__date=today
        ).exists()
        
        # Check if employee has clocked out today
        clock_out_today = obj.employee_events.filter(
            event_type__name='Clock Out', 
            timestamp__date=today
        ).exists()

        if clock_in_today and not clock_out_today:
            return 'clocked_in'
        elif clock_in_today and clock_out_today:
            return 'clocked_out'
        else:
            return 'not_clocked_in'

    def get_last_activity(self, obj):
        """Get last activity timestamp"""
        last_event = obj.employee_events.order_by('-timestamp').first()
        return last_event.timestamp if last_event else None


class EventSerializer(serializers.ModelSerializer):
    """Serializer for the Event model, showing related object details."""

    # Use nested serializers for read-only representation
    event_type = EventTypeSerializer(many=False, read_only=True)
    # Original employee representation:
    employee = EmployeeSerializer(many=False, read_only=True)
    # Use a simpler employee representation here to avoid deep nesting
    # employee = serializers.StringRelatedField(many=False, read_only=True)
    location = LocationSerializer(many=False, read_only=True)
    # Show username of the user who created the event
    created_by_user = serializers.CharField(
        source="created_by.username", read_only=True, allow_null=True
    )

    class Meta:
        model = Event
        fields = [
            "id",
            "event_type",
            "employee",
            "location",
            "timestamp",
            "created_by",
            "created_by_user",
        ]
        read_only_fields = [
            "id",
            "timestamp",
            "created_by",
        ]


class SingleEventSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating a single Event instance."""

    # Use PrimaryKeyRelatedField for writable related fields
    event_type = serializers.PrimaryKeyRelatedField(queryset=EventType.objects.all())
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all())

    class Meta:
        model = Event
        fields = [
            "id",
            "event_type",
            "employee",
            "location",
            "timestamp",
            "created_by",
            # Add 'timestamp' if you want to allow setting it via API,
            # otherwise remove it to always use default=timezone.now
            # 'created_by' is often excluded and set in the view
        ]
        read_only_fields = ["id", "created_by"]  # 'timestamp' might also be read-only


class AnalyticsCacheSerializer(serializers.ModelSerializer):
    """Serializer for the AnalyticsCache model."""

    class Meta:
        model = AnalyticsCache
        fields = "__all__"
        read_only_fields = ["created_at"]


class ReportConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for the ReportConfiguration model."""

    class Meta:
        model = ReportConfiguration
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class EmployeeAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for the EmployeeAnalytics model."""

    employee_name = serializers.CharField(source="employee.__str__", read_only=True)
    department_name = serializers.CharField(source="employee.department.name", read_only=True, allow_null=True)

    class Meta:
        model = EmployeeAnalytics
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class DepartmentAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for the DepartmentAnalytics model."""

    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = DepartmentAnalytics
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class SystemPerformanceSerializer(serializers.ModelSerializer):
    """Serializer for the SystemPerformance model."""

    class Meta:
        model = SystemPerformance
        fields = "__all__"
        read_only_fields = ["timestamp"]
