from rest_framework import serializers

from common.models import Card, Employee, Event, EventType, Location


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


class EmployeeSerializer(serializers.ModelSerializer):
    """Serializer for the Employee model, including clock-in status."""

    # Use the model's methods/properties directly
    is_clocked_in = serializers.BooleanField(read_only=True)
    last_clockinout_time = serializers.DateTimeField(read_only=True)
    # Serialize the related card number designation for convenience
    card_designation = serializers.CharField(
        source="card_number.designation", read_only=True, allow_null=True
    )
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

    class Meta:
        model = Employee
        # List fields explicitly for clarity and control
        fields = [
            "id",
            "given_name",
            "surname",
            "card_number",
            "card_designation",
            "assigned_locations",
            "is_clocked_in",
            "last_clockinout_time",
            # Write-only fields for updates via API:
            "assigned_location_ids",
            "card_id",
        ]
        # Make related fields read-only in the default representation
        read_only_fields = [
            "card_number",
            "assigned_locations",
            "is_clocked_in",
            "last_clockinout_time",
        ]


class EventSerializer(serializers.ModelSerializer):
    """Serializer for the Event model, showing related object details."""

    # Use nested serializers for read-only representation
    event_type = EventTypeSerializer(many=False, read_only=True)
    # Use a simpler employee representation here to avoid deep nesting
    employee = serializers.StringRelatedField(many=False, read_only=True)
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
            "timestamp",
            "created_by",
            "created_by_user",
        ]  # Assuming create/update handles these


class SingleEventSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating a single Event instance."""

    # Use PrimaryKeyRelatedField for writable related fields
    event_type = serializers.PrimaryKeyRelatedField(queryset=EventType.objects.all())
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all())
    # created_by will likely be set automatically in the view based on request.user

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
