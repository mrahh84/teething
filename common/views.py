from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import Employee, Event, EventType, Location
from .serializers import (
    EmployeeSerializer,
    EventSerializer,
    LocationSerializer,
    SingleEventSerializer,
)

# --- API Views ---
# Apply authentication and permissions to all API views


class SingleEventView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Event.
    Requires authentication.
    Uses PrimaryKeyRelatedFields for related objects during updates.
    """

    authentication_classes = [SessionAuthentication]  # Or TokenAuthentication, etc.
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = SingleEventSerializer
    queryset = Event.objects.all()
    lookup_field = "id"

    # Optional: Set created_by automatically on create/update
    # def perform_create(self, serializer):
    #     serializer.save(created_by=self.request.user)

    # def perform_update(self, serializer):
    #     serializer.save(created_by=self.request.user) # Or maybe don't update created_by


class SingleLocationView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Location.
    Requires authentication.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = LocationSerializer
    queryset = Location.objects.all()
    lookup_field = "id"


class SingleEmployeeView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single Employee.
    Requires authentication.
    Uses EmployeeSerializer which provides detailed info for retrieve
    and accepts IDs for related fields during updates.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = EmployeeSerializer
    queryset = Employee.objects.all()
    lookup_field = "id"


class ListEventsView(generics.ListAPIView):
    """
    API endpoint for listing all Events.
    Requires authentication. Shows nested details of related objects.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = EventSerializer  # Use the detailed serializer for listing
    queryset = (
        Event.objects.all()
        .select_related(  # Optimize query
            "event_type", "employee", "location", "created_by"
        )
        .order_by("-timestamp")
    )


# --- Template Views ---
# Apply login_required decorator


@login_required  # Redirects to LOGIN_URL if user not authenticated
# @extend_schema(exclude=True) # Keep exclude if you don't want this in API docs
def main_security(request):
    """
    Displays the main security dashboard, listing all employees
    and their current clock-in/out status. Requires login.
    """
    # Get employees ordered by surname, then given name (using model's Meta ordering)
    employees = Employee.objects.prefetch_related("employee_events__event_type").all()

    context = {
        "employees": employees,
        "user": request.user,  # Pass user for potential use in template (e.g., showing username)
    }
    return render(request, "main_security.html", context)


@login_required  # Protect this view
# @extend_schema(exclude=True)
def main_security_clocked_in_status_flip(request, id):
    """
    Handles the clock-in/clock-out action for an employee from the main security view.
    Creates a new 'Clock In' or 'Clock Out' event. Requires login.
    Includes a basic debounce mechanism.
    """
    employee = get_object_or_404(Employee, id=id)

    # Determine the *opposite* action to take
    currently_clocked_in = employee.is_clocked_in()
    target_event_type_name = "Clock Out" if currently_clocked_in else "Clock In"

    # Basic Debounce: Prevent accidental double-clicks/rapid toggling
    # Check the time of the *very last* clock event for this user
    last_event_time = employee.last_clockinout_time
    debounce_seconds = 5  # Adjust as needed
    if (
        last_event_time
        and (timezone.now() - last_event_time).total_seconds() < debounce_seconds
    ):
        # NOTE: include a message for the user
        messages.warning(
            request, f"Please wait {debounce_seconds} seconds before clocking again."
        )
        print(
            f"Clock action for {employee} blocked by debounce ({debounce_seconds}s)"
        )  # Log for debugging
        return redirect("main_security")  # Redirect without making changes

    try:
        # Get the EventType instance (Clock In or Clock Out)
        event_type = EventType.objects.get(name=target_event_type_name)
        # Assume the event happens at 'Main Security' location - adjust if needed
        location = Location.objects.get(
            name="Main Security"
        )  # Ensure this location exists!
    except (EventType.DoesNotExist, Location.DoesNotExist) as e:
        # Handle case where required EventType or Location is missing
        print(f"Error: Required EventType or Location missing: {e}")  # Log error
        messages.error(request, "System configuration error. Cannot process request.")
        return HttpResponseBadRequest(
            "System configuration error."
        )  # Or redirect with message

    # Create the new clock event
    Event.objects.create(
        employee=employee,
        event_type=event_type,
        location=location,
        created_by=request.user,  # Record which logged-in user performed the action
        # timestamp defaults to timezone.now
    )

    # Optional: Add a success message
    messages.success(request, f"{employee} successfully {event_type}.")

    return redirect("main_security")


@login_required  # Protect this view
# @extend_schema(exclude=True)
def employee_events(request, id):
    """
    Displays a detailed list of all events for a specific employee.
    Requires login.
    """
    employee = get_object_or_404(Employee, id=id)

    # Get all events for this employee, ordered by timestamp
    # Use prefetch_related for efficiency if accessing related fields in the loop
    employee_events = employee.employee_events.select_related(
        "event_type", "location"
    ).order_by("-timestamp")

    context = {
        "employee": employee,
        "employee_events": employee_events,
        "user": request.user,
    }
    return render(request, "employee_rollup.html", context)
