from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connections
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.db.models import Q, Count, Prefetch
from datetime import datetime, timedelta
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

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
    Requires authentication for creating, updating or deleting.
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
    Requires authentication for creating, updating or deleting.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]
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
    permission_classes = [IsAuthenticatedOrReadOnly]
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
@extend_schema(exclude=True)
# NOTE: Keep exclude if you don't want this in API docs
# Link: https://drf-spectacular.readthedocs.io/en/latest/drf_spectacular.html#drf_spectacular.utils.extend_schema
def main_security(request):
    """
    Displays the main security dashboard, listing all employees
    and their current clock-in/out status. Requires login.
    """
    # Get request parameters for sorting and filtering
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    sort_by = request.GET.get('sort', 'surname')
    sort_direction = request.GET.get('direction', 'asc')
    page_number = request.GET.get('page', '1')
    server_items_per_page = request.GET.get('items', '100')
    start_letter = request.GET.get('letter', '')
    
    try:
        server_items_per_page = int(server_items_per_page)
        if server_items_per_page not in [25, 50, 100, 200]:
            server_items_per_page = 100
    except ValueError:
        server_items_per_page = 100
        
    # Start with all employees, using optimized queries
    employees_query = Employee.objects.select_related('card_number').all()
    
    # Count stats for the dashboard before applying filters
    total_employees = employees_query.count()
    
    # Apply letter filter if provided
    if start_letter and len(start_letter) == 1:
        employees_query = employees_query.filter(surname__istartswith=start_letter)
    
    # Apply search if provided
    if search_query:
        employees_query = employees_query.filter(
            Q(given_name__icontains=search_query) | 
            Q(surname__icontains=search_query) |
            Q(card_number__designation__icontains=search_query)
        )
    
    # Prefetch related events with only the latest clock in/out events to improve performance
    # This optimizes the is_clocked_in calculation
    one_month_ago = timezone.now() - timedelta(days=30)
    latest_events = Event.objects.filter(
        timestamp__gte=one_month_ago,
        event_type__name__in=["Clock In", "Clock Out"]
    ).select_related('event_type').order_by('-timestamp')
    
    employees_query = employees_query.prefetch_related(
        Prefetch('employee_events', queryset=latest_events, to_attr='recent_events')
    )
    
    # Apply sorting
    if sort_by in ['given_name', 'surname']:
        order_by = sort_by
        if sort_direction == 'desc':
            order_by = f'-{order_by}'
        employees_query = employees_query.order_by(order_by)
    
    # Get the employee list - we need to materialize the queryset here
    # because we need to apply status filtering and card sorting in Python
    all_employees = list(employees_query)
    
    # Apply status filtering in Python since it's a calculated property
    if status_filter == 'in':
        all_employees = [employee for employee in all_employees if employee.is_clocked_in()]
    elif status_filter == 'out':
        all_employees = [employee for employee in all_employees if not employee.is_clocked_in()]
    
    # Sort by card number if requested (also needs to be done in Python)
    if sort_by == 'card':
        reverse = (sort_direction == 'desc')
        all_employees.sort(
            key=lambda emp: emp.card_number.designation if emp.card_number else '', 
            reverse=reverse
        )
    
    # Server-side pagination
    paginator = Paginator(all_employees, server_items_per_page)
    try:
        employees = paginator.page(page_number)
    except:
        employees = paginator.page(1)
    
    # Calculate summary statistics
    clocked_in_count = sum(1 for emp in all_employees if emp.is_clocked_in())
    clocked_out_count = len(all_employees) - clocked_in_count
    
    context = {
        "employees": employees,
        "user": request.user,
        "search_query": search_query,
        "status_filter": status_filter,
        "sort_by": sort_by,
        "sort_direction": sort_direction,
        "total_employees": total_employees,
        "clocked_in_count": clocked_in_count,
        "clocked_out_count": clocked_out_count,
        "start_letter": start_letter,
        "current_page": int(page_number),
        "total_pages": paginator.num_pages,
        "items_per_page": server_items_per_page,
    }
    return render(request, "main_security.html", context)


@login_required  # Protect this view
@extend_schema(exclude=True)
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

    # Preserve the filter parameters when redirecting
    query_params = request.GET.copy()
    redirect_url = "main_security"
    
    if query_params:
        query_string = query_params.urlencode()
        return redirect(f"{redirect_url}?{query_string}")
    else:
        return redirect(redirect_url)


@login_required  # Protect this view
@extend_schema(exclude=True)
def employee_events(request, id):
    """
    Displays a detailed list of all events for a specific employee.
    Requires login.
    """
    employee = get_object_or_404(Employee.objects.select_related('card_number'), id=id)
    
    # Get filter parameters
    date_filter = request.GET.get('date', '')
    event_type_filter = request.GET.get('event_type', '')
    
    # Get all events for this employee
    employee_events_query = employee.employee_events.select_related(
        "event_type", "location", "created_by"
    )
    
    # Apply date filter if provided
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            employee_events_query = employee_events_query.filter(
                timestamp__date=filter_date
            )
        except ValueError:
            # Invalid date format - ignore the filter
            pass
    
    # Apply event type filter if provided
    if event_type_filter:
        employee_events_query = employee_events_query.filter(
            event_type__name=event_type_filter
        )
    
    # Order by timestamp
    employee_events = employee_events_query.order_by("-timestamp")
    
    # Get all event types for the filter dropdown
    event_types = EventType.objects.values_list('name', flat=True).distinct()
    
    # Get all locations for the location dropdown in the edit form
    locations = Location.objects.all()
    
    # Get some statistics for the employee
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    today_events_count = Event.objects.filter(
        employee=employee,
        timestamp__date=today
    ).count()
    
    week_events_count = Event.objects.filter(
        employee=employee,
        timestamp__date__gte=week_ago
    ).count()
    
    context = {
        "employee": employee,
        "employee_events": employee_events,
        "user": request.user,
        "date_filter": date_filter,
        "event_type_filter": event_type_filter,
        "event_types": event_types,
        "locations": locations,
        "today_events_count": today_events_count,
        "week_events_count": week_events_count,
    }
    return render(request, "employee_rollup.html", context)


@login_required
@extend_schema(exclude=True)
def update_event(request, employee_id):
    """
    Handle updating an event from the frontend.
    """
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('employee_events', id=employee_id)
    
    employee = get_object_or_404(Employee, id=employee_id)
    event_id = request.POST.get('event_id')
    
    if not event_id:
        messages.error(request, "No event specified.")
        return redirect('employee_events', id=employee_id)
    
    try:
        event = Event.objects.get(id=event_id, employee=employee)
    except Event.DoesNotExist:
        messages.error(request, "Event not found.")
        return redirect('employee_events', id=employee_id)
    
    # Get form data
    event_type_name = request.POST.get('event_type')
    location_id = request.POST.get('location')
    date_str = request.POST.get('date')
    time_str = request.POST.get('time')
    
    # Validate data
    if not all([event_type_name, location_id, date_str, time_str]):
        messages.error(request, "All fields are required.")
        return redirect('employee_events', id=employee_id)
    
    try:
        # Get event type and location
        event_type = EventType.objects.get(name=event_type_name)
        location = Location.objects.get(id=location_id)
        
        # Parse date and time
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        time_obj = datetime.strptime(time_str, '%H:%M:%S').time()
        timestamp = timezone.make_aware(datetime.combine(date_obj, time_obj))
        
        # Update event
        event.event_type = event_type
        event.location = location
        event.timestamp = timestamp
        event.save()
        
        messages.success(request, f"Event successfully updated.")
    except (EventType.DoesNotExist, Location.DoesNotExist, ValueError) as e:
        messages.error(request, f"Error updating event: {str(e)}")
    
    return redirect('employee_events', id=employee_id)


@login_required
@extend_schema(exclude=True)
def delete_event(request, employee_id):
    """
    Handle deleting an event from the frontend.
    """
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('employee_events', id=employee_id)
    
    employee = get_object_or_404(Employee, id=employee_id)
    event_id = request.POST.get('event_id')
    
    if not event_id:
        messages.error(request, "No event specified.")
        return redirect('employee_events', id=employee_id)
    
    try:
        event = Event.objects.get(id=event_id, employee=employee)
        event_type_name = event.event_type.name
        event.delete()
        messages.success(request, f"'{event_type_name}' event successfully deleted.")
    except Event.DoesNotExist:
        messages.error(request, "Event not found.")
    
    return redirect('employee_events', id=employee_id)


# --- Reports Views ---
@login_required
@extend_schema(exclude=True)
def reports_dashboard(request):
    """
    Main reports dashboard with links to different report types.
    """
    context = {
        "user": request.user,
    }
    return render(request, "reports/dashboard.html", context)


@login_required
@extend_schema(exclude=True)
def attendance_report(request):
    """
    Display the interactive attendance report.
    """
    # Get filter parameters
    start_date = request.GET.get('start_date', (timezone.now() - timedelta(days=30)).date().isoformat())
    end_date = request.GET.get('end_date', timezone.now().date().isoformat())
    
    # Get all employees for the filter dropdown
    employees = Employee.objects.all().order_by('surname', 'given_name')
    
    # Get all locations for the filter dropdown
    locations = Location.objects.all().order_by('name')
    
    context = {
        "user": request.user,
        "start_date": start_date,
        "end_date": end_date,
        "employees": employees,
        "locations": locations,
        "report_url": f"{reverse('generate_marimo_report', args=['attendance'])}?start={start_date}&end={end_date}",
    }
    return render(request, "reports/attendance.html", context)


@login_required
@extend_schema(exclude=True)
def employee_report(request, id):
    """
    Display detailed report for a specific employee.
    """
    employee = get_object_or_404(Employee.objects.select_related('card_number'), id=id)
    
    # Get filter parameters
    start_date = request.GET.get('start_date', (timezone.now() - timedelta(days=30)).date().isoformat())
    end_date = request.GET.get('end_date', timezone.now().date().isoformat())
    
    context = {
        "user": request.user,
        "employee": employee,
        "start_date": start_date,
        "end_date": end_date,
        "report_url": f"{reverse('generate_employee_marimo_report', args=[id])}?start={start_date}&end={end_date}",
    }
    return render(request, "reports/employee_report.html", context)


@login_required
@extend_schema(exclude=True)
def location_report(request):
    """
    Display report for attendance by location.
    """
    # Get filter parameters
    start_date = request.GET.get('start_date', (timezone.now() - timedelta(days=30)).date().isoformat())
    end_date = request.GET.get('end_date', timezone.now().date().isoformat())
    
    # Get all locations
    locations = Location.objects.all().order_by('name')
    
    context = {
        "user": request.user,
        "locations": locations,
        "start_date": start_date,
        "end_date": end_date,
        "report_url": f"{reverse('generate_marimo_report', args=['locations'])}?start={start_date}&end={end_date}",
    }
    return render(request, "reports/location_report.html", context)


@login_required
@extend_schema(exclude=True)
@xframe_options_sameorigin
def generate_marimo_report(request, report_type):
    """
    Generate and serve a Marimo report.
    """
    try:
        # Import marimo to check if it's installed
        import marimo
        # We'll use our custom HTML report instead of marimo directly
        print(f"Marimo is installed (version {marimo.__version__}), but we'll use custom HTML reports")
    except ImportError:
        print("Marimo not installed, using fallback HTML report")
    
    # Get filter parameters
    start_date = request.GET.get('start', (timezone.now() - timedelta(days=30)).date().isoformat())
    end_date = request.GET.get('end', timezone.now().date().isoformat())
    
    # Add logging to debug
    print(f"Generating {report_type} report for dates {start_date} to {end_date}")
    
    try:
        # Convert string dates to datetime objects
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        # Add one day to end_date to include the entire end day
        end_dt = end_dt + timedelta(days=1)
    except ValueError as e:
        return HttpResponse(f"Invalid date format: {str(e)}", status=400)
    
    # Use our fallback HTML reports which work reliably
    return generate_fallback_html_report(request, report_type, start_dt, end_dt)

@login_required
@extend_schema(exclude=True)
@xframe_options_sameorigin
def generate_employee_marimo_report(request, employee_id):
    """
    Generate and serve a Marimo report for a specific employee.
    """
    try:
        # Import marimo to check if it's installed
        import marimo
        # We'll use our custom HTML report instead of marimo directly
        print(f"Marimo is installed (version {marimo.__version__}), but we'll use custom HTML reports")
    except ImportError:
        print("Marimo not installed, using fallback HTML report")
    
    # Get filter parameters
    start_date = request.GET.get('start', (timezone.now() - timedelta(days=30)).date().isoformat())
    end_date = request.GET.get('end', timezone.now().date().isoformat())
    
    # Add logging to debug
    print(f"Generating employee report for employee ID {employee_id}, dates {start_date} to {end_date}")
    
    try:
        # Convert string dates to datetime objects
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        # Add one day to end_date to include the entire end day
        end_dt = end_dt + timedelta(days=1)
    except ValueError as e:
        return HttpResponse(f"Invalid date format: {str(e)}", status=400)
    
    # Use our fallback HTML reports which work reliably
    return generate_employee_fallback_html_report(request, employee_id, start_dt, end_dt)

# Helper function for fallback HTML reports
def generate_fallback_html_report(request, report_type, start_dt, end_dt):
    """Generate a simple HTML report without marimo"""
    try:
        # Import needed libraries
        from django.utils.html import escape
        
        # Create a basic HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                h1 {{ color: #333; }}
            </style>
        </head>
        <body>
            <h1>{escape(report_type.title())} Report</h1>
            <p>Period: {escape(start_dt.date().isoformat())} to {escape((end_dt - timedelta(days=1)).date().isoformat())}</p>
        """
        
        if report_type == "attendance":
            events = Event.objects.filter(
                timestamp__gte=start_dt,
                timestamp__lt=end_dt
            ).select_related('employee', 'event_type', 'location').order_by('-timestamp')
            
            # Create a simple table
            html += "<h2>Attendance Events</h2>"
            html += "<table>"
            html += "<tr><th>Employee</th><th>Event Type</th><th>Location</th><th>Date</th><th>Time</th></tr>"
            
            for event in events[:100]:  # Limit to 100 events for performance
                html += f"""<tr>
                    <td>{escape(f"{event.employee.given_name} {event.employee.surname}")}</td>
                    <td>{escape(event.event_type.name)}</td>
                    <td>{escape(event.location.name)}</td>
                    <td>{escape(event.timestamp.date().isoformat())}</td>
                    <td>{escape(event.timestamp.time().isoformat(timespec='minutes'))}</td>
                </tr>"""
            
            html += "</table>"
            
            if len(events) > 100:
                html += f"<p>Showing first 100 events out of {len(events)}.</p>"
            
        elif report_type == "locations":
            # Get location-based events
            events = Event.objects.filter(
                timestamp__gte=start_dt,
                timestamp__lt=end_dt
            ).select_related('employee', 'event_type', 'location')
            
            # Group by location
            location_data = {}
            for event in events:
                loc_name = event.location.name
                if loc_name not in location_data:
                    location_data[loc_name] = {'Clock In': 0, 'Clock Out': 0}
                
                event_type = event.event_type.name
                if event_type in ['Clock In', 'Clock Out']:
                    location_data[loc_name][event_type] += 1
            
            # Create a simple table
            html += "<h2>Location Summary</h2>"
            html += "<table>"
            html += "<tr><th>Location</th><th>Clock In Events</th><th>Clock Out Events</th><th>Total</th></tr>"
            
            for loc_name, counts in location_data.items():
                total = counts['Clock In'] + counts['Clock Out']
                html += f"""<tr>
                    <td>{escape(loc_name)}</td>
                    <td>{counts['Clock In']}</td>
                    <td>{counts['Clock Out']}</td>
                    <td>{total}</td>
                </tr>"""
            
            html += "</table>"
        
        html += """
        </body>
        </html>
        """
        
        return HttpResponse(html, content_type='text/html')
    
    except Exception as e:
        return HttpResponse(f"Error generating report: {str(e)}", status=500)

# Helper function for employee fallback HTML reports
def generate_employee_fallback_html_report(request, employee_id, start_dt, end_dt):
    """Generate a simple HTML report for an employee without marimo"""
    try:
        # Import required libraries
        from django.utils.html import escape
        
        # Get employee info
        employee = get_object_or_404(Employee.objects.select_related('card_number'), id=employee_id)
        
        # Get events for this employee
        events = Event.objects.filter(
            employee=employee,
            timestamp__gte=start_dt,
            timestamp__lt=end_dt
        ).select_related('event_type', 'location').order_by('-timestamp')
        
        # Create a basic HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Employee Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                h1, h2 {{ color: #333; }}
            </style>
        </head>
        <body>
            <h1>Report for {escape(employee.given_name)} {escape(employee.surname)}</h1>
            <p>Card Number: {escape(employee.card_number.designation if employee.card_number else 'None')}</p>
            <p>Period: {escape(start_dt.date().isoformat())} to {escape((end_dt - timedelta(days=1)).date().isoformat())}</p>
            
            <h2>Employee Events</h2>
        """
        
        if events.exists():
            html += "<table>"
            html += "<tr><th>Event Type</th><th>Location</th><th>Date</th><th>Time</th></tr>"
            
            for event in events:
                html += f"""<tr>
                    <td>{escape(event.event_type.name)}</td>
                    <td>{escape(event.location.name)}</td>
                    <td>{escape(event.timestamp.date().isoformat())}</td>
                    <td>{escape(event.timestamp.time().isoformat(timespec='minutes'))}</td>
                </tr>"""
            
            html += "</table>"
        else:
            html += "<p>No events recorded for this employee in the selected period.</p>"
        
        html += """
        </body>
        </html>
        """
        
        return HttpResponse(html, content_type='text/html')
        
    except Exception as e:
        return HttpResponse(f"Error generating employee report: {str(e)}", status=500)


# --- Health Check Views ---
# No login required, no permissions needed for a basic health check
# Exclude from schema if using drf-spectacular


@extend_schema(exclude=True)
def health_check(request):
    """
    Basic health check endpoint. Returns HTTP 200 OK if the app is running.
    """
    try:
        connections["default"].cursor()
    except Exception as e:
        return HttpResponse("Database unavailable", status=503)

    return HttpResponse("OK", status=200)
