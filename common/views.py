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
from datetime import datetime, timedelta, date
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
import json

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
    # Check if Marimo is installed
    try:
        import marimo
        marimo_available = True
    except ImportError:
        marimo_available = False
    
    context = {
        "user": request.user,
        "marimo_available": marimo_available,
    }
    return render(request, "reports/dashboard.html", context)


@login_required
@extend_schema(exclude=True)
def daily_dashboard_report(request):
    """
    Display the daily attendance dashboard using Marimo.
    """
    # Get filter parameters
    date_str = request.GET.get('date', timezone.now().date().isoformat())
    
    try:
        # Try to convert to date to validate format
        selected_date = datetime.fromisoformat(date_str).date()
    except ValueError:
        # If invalid date, default to today
        selected_date = timezone.now().date()
        date_str = selected_date.isoformat()
    
    context = {
        "user": request.user,
        "selected_date": date_str,
        "report_url": f"{reverse('generate_marimo_report', args=['daily_dashboard'])}?date={date_str}",
        "report_title": "Daily Attendance Dashboard",
        "report_description": "Real-time attendance status showing currently clocked-in and not-clocked-in employees."
    }
    return render(request, "reports/marimo_report.html", context)


@login_required
@extend_schema(exclude=True)
def employee_history_report(request):
    """
    Display the employee attendance history report using Marimo.
    """
    # Get filter parameters
    employee_id = request.GET.get('employee_id')
    start_date = request.GET.get('start_date', (timezone.now() - timedelta(days=30)).date().isoformat())
    end_date = request.GET.get('end_date', timezone.now().date().isoformat())
    
    # Get all employees for the dropdown
    employees = Employee.objects.all().order_by('surname', 'given_name')
    
    # If no employee selected, default to first one
    if not employee_id and employees.exists():
        employee_id = employees.first().id
    
    context = {
        "user": request.user,
        "employees": employees,
        "selected_employee_id": employee_id,
        "start_date": start_date,
        "end_date": end_date,
        "report_url": f"{reverse('generate_marimo_report', args=['employee_history'])}?employee_id={employee_id}&start={start_date}&end={end_date}",
        "report_title": "Employee Attendance History",
        "report_description": "Detailed attendance history for individual employees with hours calculation."
    }
    return render(request, "reports/employee_history_report.html", context)


@login_required
@extend_schema(exclude=True)
def period_summary_report(request):
    """
    Display the attendance summary by period (daily, weekly, monthly) using Marimo.
    """
    # Get filter parameters
    period = request.GET.get('period', 'day')
    start_date = request.GET.get('start_date', timezone.now().date().isoformat())
    start_time = request.GET.get('start_time', '09:00')
    end_time = request.GET.get('end_time', '17:00')
    
    context = {
        "user": request.user,
        "selected_period": period,
        "start_date": start_date,
        "start_time": start_time,
        "end_time": end_time,
        "report_url": f"{reverse('generate_marimo_report', args=['period_summary'])}?period={period}&start={start_date}&start_time={start_time}&end_time={end_time}",
        "report_title": "Attendance Summary by Period",
        "report_description": "Aggregated attendance statistics showing hours worked, late arrivals, and early departures."
    }
    return render(request, "reports/period_summary_report.html", context)


@login_required
@extend_schema(exclude=True)
def late_early_report(request):
    """
    Display the late arrival and early departure report using Marimo.
    """
    # Get filter parameters
    start_date = request.GET.get('start_date', (timezone.now() - timedelta(days=30)).date().isoformat())
    end_date = request.GET.get('end_date', timezone.now().date().isoformat())
    late_threshold = request.GET.get('late_threshold', '15')
    early_threshold = request.GET.get('early_threshold', '15')
    start_time = request.GET.get('start_time', '09:00')
    end_time = request.GET.get('end_time', '17:00')
    
    context = {
        "user": request.user,
        "start_date": start_date,
        "end_date": end_date,
        "late_threshold": late_threshold,
        "early_threshold": early_threshold,
        "start_time": start_time,
        "end_time": end_time,
        "report_url": f"{reverse('generate_marimo_report', args=['late_early'])}?start={start_date}&end={end_date}&late_threshold={late_threshold}&early_threshold={early_threshold}&start_time={start_time}&end_time={end_time}",
        "report_title": "Late Arrival and Early Departure Report",
        "report_description": "Track employee punctuality with customizable thresholds for lateness and early departures."
    }
    return render(request, "reports/late_early_report.html", context)


@login_required
@extend_schema(exclude=True)
@xframe_options_sameorigin
def generate_marimo_report(request, report_type):
    """
    Generate and serve a Marimo report for the specified report type.
    """
    try:
        # Import marimo to check if it's installed
        import marimo as mo
        
        # We'll use our custom Marimo notebooks for reports
        print(f"Marimo is installed (version {mo.__version__}), creating {report_type} report")
        
        # Get filter parameters
        start_date_str = request.GET.get('start', (timezone.now() - timedelta(days=30)).date().isoformat())
        end_date_str = request.GET.get('end', timezone.now().date().isoformat())
        
        # Convert string dates to datetime objects
        try:
            start_date = datetime.fromisoformat(start_date_str).date()
            end_date = datetime.fromisoformat(end_date_str).date()
            
            # Add one day to end_date to include the entire end day
            end_date_with_day = end_date + timedelta(days=1)
        except ValueError as e:
            return HttpResponse(f"Invalid date format: {str(e)}", status=400)
        
        # Add logging to debug
        print(f"Generating {report_type} report for dates {start_date} to {end_date}")
        
        # For now, use fallback HTML reports for all report types
        # This ensures users see something while we resolve Marimo integration issues
        if report_type == 'daily_dashboard':
            date_str = request.GET.get('date', timezone.now().date().isoformat())
            try:
                selected_date = datetime.fromisoformat(date_str).date()
            except ValueError:
                selected_date = timezone.now().date()
            
            return generate_daily_dashboard_html(request, selected_date)
            
        elif report_type == 'employee_history':
            employee_id = request.GET.get('employee_id')
            if not employee_id:
                return HttpResponse("Employee ID is required", status=400)
            
            return generate_employee_history_html(request, employee_id, start_date, end_date_with_day)
            
        elif report_type == 'period_summary':
            period = request.GET.get('period', 'day')
            start_time = request.GET.get('start_time', '09:00')
            end_time = request.GET.get('end_time', '17:00')
            
            return generate_period_summary_html(request, period, start_date, end_date_with_day, start_time, end_time)
            
        elif report_type == 'late_early':
            late_threshold = int(request.GET.get('late_threshold', '15'))
            early_threshold = int(request.GET.get('early_threshold', '15'))
            start_time = request.GET.get('start_time', '09:00')
            end_time = request.GET.get('end_time', '17:00')
            
            return generate_late_early_html(request, start_date, end_date_with_day, late_threshold, early_threshold, start_time, end_time)
            
        else:
            return HttpResponse(f"Unknown report type: {report_type}", status=400)
            
    except ImportError:
        print("Marimo not installed")
        return HttpResponse("Marimo is not installed. Reports require Marimo to be installed.", status=500)
    except Exception as e:
        print(f"Error generating report: {str(e)}")
        return HttpResponse(f"Error generating report: {str(e)}", status=500)

def generate_daily_dashboard_html(request, selected_date):
    """Generate HTML report for daily dashboard"""
    # Calculate start and end of selected date
    start_of_day = timezone.make_aware(datetime.combine(selected_date, datetime.min.time()))
    end_of_day = timezone.make_aware(datetime.combine(selected_date, datetime.max.time()))
    
    # Get all employees
    all_employees = Employee.objects.all()
    total_employees = all_employees.count()
    
    # Get clock events for the selected day
    clock_events = Event.objects.filter(
        timestamp__range=(start_of_day, end_of_day),
        event_type__name__in=["Clock In", "Clock Out"]
    ).select_related('employee', 'event_type')
    
    # Determine which employees are clocked in
    clocked_in_employees = set()
    for employee in all_employees:
        if employee.is_clocked_in():
            clocked_in_employees.add(employee.id)
    
    clocked_in_count = len(clocked_in_employees)
    not_clocked_in_count = total_employees - clocked_in_count
    
    # Create a basic HTML report
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Daily Attendance Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            .summary {{ display: flex; justify-content: space-between; margin-bottom: 30px; }}
            .stat-box {{ background-color: #f5f5f5; border-radius: 8px; padding: 15px; width: 30%; text-align: center; }}
            .stat-value {{ font-size: 28px; font-weight: bold; margin: 10px 0; }}
            .stat-label {{ font-size: 14px; color: #666; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .clocked-in {{ background-color: #e6ffe6; }}
            .not-clocked-in {{ background-color: #ffe6e6; }}
            h1, h2 {{ color: #333; }}
        </style>
    </head>
    <body>
        <h1>Daily Attendance Dashboard</h1>
        <p>Date: {selected_date.strftime('%A, %B %d, %Y')}</p>
        
        <div class="summary">
            <div class="stat-box">
                <div class="stat-label">Total Employees</div>
                <div class="stat-value">{total_employees}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Currently Clocked In</div>
                <div class="stat-value">{clocked_in_count}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Not Clocked In</div>
                <div class="stat-value">{not_clocked_in_count}</div>
            </div>
        </div>
        
        <h2>Employee Attendance Status</h2>
        <table>
            <tr>
                <th>Employee</th>
                <th>Status</th>
                <th>Last Event</th>
            </tr>
    """
    
    # Add rows for each employee
    for employee in all_employees:
        status = "Clocked In" if employee.id in clocked_in_employees else "Not Clocked In"
        row_class = "clocked-in" if employee.id in clocked_in_employees else "not-clocked-in"
        
        # Get employee's last event
        last_event = Event.objects.filter(
            employee=employee,
            event_type__name__in=["Clock In", "Clock Out"]
        ).order_by('-timestamp').first()
        
        last_event_info = f"{last_event.event_type.name} at {last_event.timestamp.strftime('%H:%M')} on {last_event.timestamp.strftime('%Y-%m-%d')}" if last_event else "No events recorded"
        
        html += f"""
            <tr class="{row_class}">
                <td>{employee.given_name} {employee.surname}</td>
                <td>{status}</td>
                <td>{last_event_info}</td>
            </tr>
        """
    
    html += """
        </table>
    </body>
    </html>
    """
    
    # Create data for the heatmap - Attendance by hour and department
    departments = ['Administration', 'Engineering', 'Sales', 'Support', 'Marketing']
    hours = list(range(7, 19))  # 7 AM to 6 PM
    
    # Initialize the heatmap data
    heatmap_data = []
    for dept in departments:
        heatmap_data.append([0] * len(hours))
    
    # Get department for each employee (assuming a department field or property)
    # You'll need to adapt this to your actual data model
    employee_departments = {}
    for employee in all_employees:
        # Assign each employee to a department - modify this based on your model
        dept = getattr(employee, 'department', 'Administration')
        if dept not in departments:
            dept = 'Administration'
        employee_departments[employee.id] = dept
    
    # Count clock-ins by hour and department
    for event in clock_events:
        if event.event_type.name == "Clock In":
            hour = event.timestamp.hour
            if 7 <= hour <= 18:  # Only count hours in our range
                dept = employee_departments.get(event.employee.id, 'Administration')
                dept_idx = departments.index(dept)
                hour_idx = hours.index(hour)
                heatmap_data[dept_idx][hour_idx] += 1
    
    # Create Plotly heatmap
    heatmap_plot = {
        'z': heatmap_data,
        'x': [f"{h}:00" for h in hours],
        'y': departments,
        'type': 'heatmap',
        'colorscale': 'Viridis'
    }
    
    heatmap_layout = {
        'title': 'Clock-ins by Hour and Department',
        'xaxis': {'title': 'Hour of Day'},
        'yaxis': {'title': 'Department'}
    }
    
    heatmap_json = json.dumps({'data': [heatmap_plot], 'layout': heatmap_layout})
    
    # Insert this before the employee table in your HTML
    html += f"""
    <h2>Attendance Patterns</h2>
    <div id="heatmap" style="height: 400px;"></div>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script>
        var heatmapData = {heatmap_json};
        Plotly.newPlot('heatmap', heatmapData.data, heatmapData.layout);
    </script>
    """
    
    return HttpResponse(html, content_type='text/html')

def generate_employee_history_html(request, employee_id, start_date, end_date):
    """Generate HTML report for employee attendance history"""
    try:
        # Get employee
        employee = get_object_or_404(Employee, id=employee_id)
        
        # Convert to datetime objects for filtering
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.min.time()))
        
        # Get employee events
        events = Event.objects.filter(
            employee=employee,
            timestamp__range=(start_datetime, end_datetime)
        ).select_related('event_type', 'location').order_by('timestamp')
        
        # Process events to calculate hours
        event_days = {}
        clock_in_time = None
        total_hours = 0
        
        for event in events:
            event_date = event.timestamp.date()
            if event_date not in event_days:
                event_days[event_date] = {
                    'date': event_date,
                    'clock_in': None,
                    'clock_out': None,
                    'hours': 0
                }
            
            if event.event_type.name == "Clock In":
                event_days[event_date]['clock_in'] = event.timestamp
                clock_in_time = event.timestamp
            elif event.event_type.name == "Clock Out" and clock_in_time:
                event_days[event_date]['clock_out'] = event.timestamp
                hours = (event.timestamp - clock_in_time).total_seconds() / 3600
                event_days[event_date]['hours'] = round(hours, 2)
                total_hours += hours
                clock_in_time = None
        
        # Prepare data for charts
        dates = []
        hours_worked = []
        calendar_data = []
        
        # Sort days by date
        for date_key in sorted(event_days.keys()):
            day = event_days[date_key]
            dates.append(date_key.strftime('%Y-%m-%d'))
            hours_worked.append(day['hours'])
            
            # Calendar data needs z-value (intensity)
            calendar_data.append({
                'date': date_key.strftime('%Y-%m-%d'),
                'hours': day['hours']
            })
        
        # Create bar chart for hours worked
        bar_chart = {
            'x': dates,
            'y': hours_worked,
            'type': 'bar',
            'marker': {
                'color': 'rgba(58, 171, 210, 0.8)'
            },
            'name': 'Hours Worked'
        }
        
        bar_layout = {
            'title': f'Daily Hours Worked for {employee.given_name} {employee.surname}',
            'xaxis': {'title': 'Date'},
            'yaxis': {'title': 'Hours'},
            'margin': {'l': 50, 'r': 50, 'b': 100, 't': 50, 'pad': 4}
        }
        
        # Convert data to JSON for the template
        bar_chart_json = json.dumps({'data': [bar_chart], 'layout': bar_layout})
        
        # Calendar heatmap - this is a bit more complex in Plotly
        # We'll create a function to generate calendar heatmap data
        def generate_calendar_data(calendar_data, start_date, end_date):
            # Generate all dates in range
            all_dates = []
            curr_date = start_date
            while curr_date < end_date:
                all_dates.append(curr_date.strftime('%Y-%m-%d'))
                curr_date += timedelta(days=1)
            
            # Map of date to hours
            hours_by_date = {item['date']: item['hours'] for item in calendar_data}
            
            # Create a list of weeks
            weeks = []
            current_week = []
            
            # Get the weekday of the start date (0 is Monday in Python's datetime)
            start_weekday = start_date.weekday()
            
            # Add empty days before the start date
            for _ in range(start_weekday):
                current_week.append(None)
            
            for date_str in all_dates:
                current_week.append(hours_by_date.get(date_str, 0))
                
                # If we reach Sunday (6), start a new week
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                if date_obj.weekday() == 6:
                    weeks.append(current_week)
                    current_week = []
            
            # Add any remaining days
            if current_week:
                while len(current_week) < 7:
                    current_week.append(None)
                weeks.append(current_week)
                
            return weeks
        
        calendar_weeks = generate_calendar_data(calendar_data, start_date, end_date - timedelta(days=1))
        
        # Create a heatmap for the calendar view
        calendar_plot = {
            'z': calendar_weeks,
            'x': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            'y': [f'Week {i+1}' for i in range(len(calendar_weeks))],
            'type': 'heatmap',
            'colorscale': [
                [0, 'rgb(255,255,255)'],  # No hours = white
                [0.1, 'rgb(220,237,252)'],
                [0.5, 'rgb(66,146,198)'],
                [1, 'rgb(8,48,107)']  # Max hours = dark blue
            ],
            'showscale': True
        }
        
        calendar_layout = {
            'title': 'Attendance Calendar',
            'margin': {'l': 50, 'r': 50, 'b': 50, 't': 50, 'pad': 4}
        }
        
        calendar_json = json.dumps({'data': [calendar_plot], 'layout': calendar_layout})
        
        # Create HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Employee Attendance History</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .employee-info {{ margin-bottom: 30px; }}
                .summary {{ display: flex; margin-bottom: 30px; }}
                .stat-box {{ background-color: #f5f5f5; border-radius: 8px; padding: 15px; margin-right: 20px; text-align: center; }}
                .stat-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
                .stat-label {{ font-size: 14px; color: #666; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                h1, h2 {{ color: #333; }}
            </style>
        </head>
        <body>
            <h1>Employee Attendance History</h1>
            
            <div class="employee-info">
                <h2>{employee.given_name} {employee.surname}</h2>
                <p>Report period: {start_date.strftime('%Y-%m-%d')} to {(end_date - timedelta(days=1)).strftime('%Y-%m-%d')}</p>
            </div>
            
            <div class="summary">
                <div class="stat-box">
                    <div class="stat-label">Total Days</div>
                    <div class="stat-value">{len(event_days)}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Total Hours</div>
                    <div class="stat-value">{round(total_hours, 2)}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Average Hours/Day</div>
                    <div class="stat-value">{round(total_hours / len(event_days), 2) if event_days else 0}</div>
                </div>
            </div>
            
            <h2>Hours Overview</h2>
            <div id="barChart" style="height: 300px;"></div>
            
            <h2>Attendance Calendar</h2>
            <div id="calendarHeatmap" style="height: 400px;"></div>
            
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <script>
                var barChartData = {bar_chart_json};
                Plotly.newPlot('barChart', barChartData.data, barChartData.layout);
                
                var calendarData = {calendar_json};
                Plotly.newPlot('calendarHeatmap', calendarData.data, calendarData.layout);
            </script>
        </body>
        </html>
        """
        
        return HttpResponse(html, content_type='text/html')
        
    except Exception as e:
        return HttpResponse(f"Error generating employee history report: {str(e)}", status=500)

def generate_period_summary_html(request, period_type, start_date, end_date, start_time_str, end_time_str):
    """Generate HTML report for attendance summary by period"""
    try:
        # Convert time strings to time objects
        try:
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
        except ValueError:
            start_time = datetime.strptime('09:00', '%H:%M').time()
            end_time = datetime.strptime('17:00', '%H:%M').time()
        
        # Full date range
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.min.time()))
        
        # Get all events in the date range
        events = Event.objects.filter(
            timestamp__range=(start_datetime, end_datetime),
            event_type__name__in=["Clock In", "Clock Out"]
        ).select_related('employee', 'event_type')
        
        # Group events by period and employee
        period_data = {}
        
        # Define period boundaries
        if period_type == 'day':
            # For daily, each day is a period
            current_date = start_date
            while current_date < end_date:
                period_data[current_date] = {'label': current_date.strftime('%Y-%m-%d'), 'employees': {}}
                current_date += timedelta(days=1)
                
        elif period_type == 'week':
            # For weekly, group by calendar week
            current_date = start_date
            while current_date < end_date:
                # Find start of the week (Monday)
                week_start = current_date - timedelta(days=current_date.weekday())
                week_label = f"Week {week_start.strftime('%Y-%m-%d')}"
                
                if week_label not in period_data:
                    period_data[week_label] = {'label': week_label, 'employees': {}}
                
                current_date += timedelta(days=1)
                
        elif period_type == 'month':
            # For monthly, group by calendar month
            current_date = start_date
            while current_date < end_date:
                month_label = current_date.strftime('%Y-%m')
                
                if month_label not in period_data:
                    period_data[month_label] = {'label': month_label, 'employees': {}}
                
                current_date += timedelta(days=1)
        
        # Process all events
        for event in events:
            employee_id = event.employee.id
            employee_name = f"{event.employee.given_name} {event.employee.surname}"
            event_date = event.timestamp.date()
            event_time = event.timestamp.time()
            
            # Determine which period this event belongs to
            if period_type == 'day':
                period_key = event_date
            elif period_type == 'week':
                week_start = event_date - timedelta(days=event_date.weekday())
                period_key = f"Week {week_start.strftime('%Y-%m-%d')}"
            elif period_type == 'month':
                period_key = event_date.strftime('%Y-%m')
            
            # Skip if period not in our range
            if period_key not in period_data:
                continue
            
            # Initialize employee data in this period if needed
            if employee_id not in period_data[period_key]['employees']:
                period_data[period_key]['employees'][employee_id] = {
                    'name': employee_name,
                    'first_clock_in': None,
                    'last_clock_out': None,
                    'hours': 0,
                    'late_arrivals': 0,
                    'early_departures': 0
                }
            
            # Update employee data
            emp_data = period_data[period_key]['employees'][employee_id]
            
            if event.event_type.name == "Clock In":
                # Check if this is the first clock in for the day
                if emp_data['first_clock_in'] is None or event.timestamp.date() != emp_data['first_clock_in'].date():
                    emp_data['first_clock_in'] = event.timestamp
                    
                    # Check if late arrival
                    if event_time > start_time:
                        emp_data['late_arrivals'] += 1
                    
            elif event.event_type.name == "Clock Out":
                # Update last clock out
                if emp_data['last_clock_out'] is None or event.timestamp > emp_data['last_clock_out']:
                    emp_data['last_clock_out'] = event.timestamp
                    
                    # Check if early departure
                    if event_time < end_time:
                        emp_data['early_departures'] += 1
        
        # Calculate hours worked for each employee in each period
        for period_key in sorted(period_data.keys()):
            for employee_id, emp_data in period_data[period_key]['employees'].items():
                if emp_data['first_clock_in'] and emp_data['last_clock_out']:
                    # Calculate hours between first clock in and last clock out
                    hours = (emp_data['last_clock_out'] - emp_data['first_clock_in']).total_seconds() / 3600
                    emp_data['hours'] = round(hours, 2)
        
        # Prepare data for stacked bar chart
        periods = []
        stacked_data = {}  # Employee -> hours for each period
        
        # Collect data for each period
        for period_key in sorted(period_data.keys()):
            period = period_data[period_key]
            if not period['employees']:
                continue
            
            periods.append(period['label'])
            
            # Add hours for each employee
            for employee_id, emp_data in period['employees'].items():
                employee_name = emp_data['name']
                if employee_name not in stacked_data:
                    stacked_data[employee_name] = []
                
                # Find the correct position in the array
                while len(stacked_data[employee_name]) < len(periods) - 1:
                    stacked_data[employee_name].append(0)
                
                stacked_data[employee_name].append(emp_data['hours'])
        
        # Create traces for each employee
        stacked_bar_traces = []
        for employee_name, hours in stacked_data.items():
            # Fill in zeros for missing periods
            while len(hours) < len(periods):
                hours.append(0)
            
            trace = {
                'x': periods,
                'y': hours,
                'type': 'bar',
                'name': employee_name
            }
            stacked_bar_traces.append(trace)
        
        stacked_layout = {
            'title': f'{period_name} Hours Worked by Employee',
            'barmode': 'stack',
            'xaxis': {'title': period_name},
            'yaxis': {'title': 'Hours'},
            'margin': {'l': 50, 'r': 50, 'b': 100, 't': 50, 'pad': 4}
        }
        
        stacked_json = json.dumps({'data': stacked_bar_traces, 'layout': stacked_layout})
        
        # Also create a trend line for late/early occurrences
        late_trend = []
        early_trend = []
        
        for period_key in sorted(period_data.keys()):
            period = period_data[period_key]
            if not period['employees']:
                continue
            
            # Sum up late arrivals and early departures
            late_count = sum(emp_data['late_arrivals'] for emp_id, emp_data in period['employees'].items())
            early_count = sum(emp_data['early_departures'] for emp_id, emp_data in period['employees'].items())
            
            late_trend.append(late_count)
            early_trend.append(early_count)
        
        trend_traces = [
            {
                'x': periods,
                'y': late_trend,
                'type': 'scatter',
                'mode': 'lines+markers',
                'name': 'Late Arrivals',
                'line': {'color': 'red'}
            },
            {
                'x': periods,
                'y': early_trend,
                'type': 'scatter',
                'mode': 'lines+markers',
                'name': 'Early Departures',
                'line': {'color': 'orange'}
            }
        ]
        
        trend_layout = {
            'title': 'Punctuality Trends',
            'xaxis': {'title': period_name},
            'yaxis': {'title': 'Count'},
            'margin': {'l': 50, 'r': 50, 'b': 100, 't': 50, 'pad': 4}
        }
        
        trend_json = json.dumps({'data': trend_traces, 'layout': trend_layout})
        
        # Create HTML report
        period_name = {'day': 'Daily', 'week': 'Weekly', 'month': 'Monthly'}[period_type]
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{period_name} Attendance Summary</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .summary {{ margin-bottom: 30px; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 30px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                h1, h2 {{ color: #333; }}
                .late {{ color: #e74c3c; }}
                .early {{ color: #e67e22; }}
            </style>
        </head>
        <body>
            <h1>{period_name} Attendance Summary</h1>
            <p>Period: {start_date.strftime('%Y-%m-%d')} to {(end_date - timedelta(days=1)).strftime('%Y-%m-%d')}</p>
            <p>Standard hours: {start_time_str} to {end_time_str}</p>
        """
        
        # Create a table for each period
        for period_key in sorted(period_data.keys()):
            period = period_data[period_key]
            
            if not period['employees']:
                continue
                
            html += f"""
                <h2>{period['label']}</h2>
                <table>
                    <tr>
                        <th>Employee</th>
                        <th>First Clock In</th>
                        <th>Last Clock Out</th>
                        <th>Hours</th>
                        <th>Late Arrivals</th>
                        <th>Early Departures</th>
                    </tr>
            """
            
            # Add rows for each employee
            for employee_id, emp_data in sorted(period['employees'].items(), key=lambda x: x[1]['name']):
                first_in = emp_data['first_clock_in'].strftime('%Y-%m-%d %H:%M') if emp_data['first_clock_in'] else "—"
                last_out = emp_data['last_clock_out'].strftime('%Y-%m-%d %H:%M') if emp_data['last_clock_out'] else "—"
                
                late_class = " class='late'" if emp_data['late_arrivals'] > 0 else ""
                early_class = " class='early'" if emp_data['early_departures'] > 0 else ""
                
                html += f"""
                    <tr>
                        <td>{emp_data['name']}</td>
                        <td>{first_in}</td>
                        <td>{last_out}</td>
                        <td>{emp_data['hours']}</td>
                        <td{late_class}>{emp_data['late_arrivals']}</td>
                        <td{early_class}>{emp_data['early_departures']}</td>
                    </tr>
                """
            
            html += """
                </table>
            """
        
        html += f"""
        <div id="stackedBar" style="height: 400px;"></div>
        <div id="trendLines" style="height: 300px;"></div>
        
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <script>
            var stackedData = {stacked_json};
            Plotly.newPlot('stackedBar', stackedData.data, stackedData.layout);
            
            var trendData = {trend_json};
            Plotly.newPlot('trendLines', trendData.data, trendData.layout);
        </script>
        """
        
        html += """
        </body>
        </html>
        """
        
        return HttpResponse(html, content_type='text/html')
        
    except Exception as e:
        return HttpResponse(f"Error generating period summary report: {str(e)}", status=500)

def generate_late_early_html(request, start_date, end_date, late_threshold, early_threshold, start_time_str, end_time_str):
    """Generate HTML report for late arrivals and early departures"""
    try:
        # Convert time strings to time objects
        try:
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
        except ValueError:
            start_time = datetime.strptime('09:00', '%H:%M').time()
            end_time = datetime.strptime('17:00', '%H:%M').time()
        
        # Full date range
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.min.time()))
        
        # Get all clock events in the date range
        events = Event.objects.filter(
            timestamp__range=(start_datetime, end_datetime),
            event_type__name__in=["Clock In", "Clock Out"]
        ).select_related('employee', 'event_type')
        
        # Process events to find late arrivals and early departures
        late_arrivals = []
        early_departures = []
        
        for event in events:
            event_time = event.timestamp.time()
            employee_name = f"{event.employee.given_name} {event.employee.surname}"
            
            if event.event_type.name == "Clock In":
                if event_time > start_time:
                    # Calculate minutes late
                    minutes_late = (datetime.combine(date.min, event_time) - datetime.combine(date.min, start_time)).total_seconds() / 60
                    
                    if minutes_late >= late_threshold:
                        late_arrivals.append({
                            'employee_name': employee_name,
                            'date': event.timestamp.date(),
                            'time': event_time,
                            'minutes_late': int(minutes_late)
                        })
                        
            elif event.event_type.name == "Clock Out":
                if event_time < end_time:
                    # Calculate minutes early
                    minutes_early = (datetime.combine(date.min, end_time) - datetime.combine(date.min, event_time)).total_seconds() / 60
                    
                    if minutes_early >= early_threshold:
                        early_departures.append({
                            'employee_name': employee_name,
                            'date': event.timestamp.date(),
                            'time': event_time,
                            'minutes_early': int(minutes_early)
                        })
        
        # Sort by date
        late_arrivals.sort(key=lambda x: (x['date'], x['minutes_late']), reverse=True)
        early_departures.sort(key=lambda x: (x['date'], x['minutes_early']), reverse=True)
        
        # Prepare data for timeline visualization
        timeline_data = []
        
        # Add late arrivals
        for late in late_arrivals:
            timeline_data.append({
                'date': late['date'].strftime('%Y-%m-%d'),
                'time': late['time'].strftime('%H:%M'),
                'minutes': late['minutes_late'],
                'employee': late['employee_name'],
                'type': 'Late Arrival'
            })
        
        # Add early departures
        for early in early_departures:
            timeline_data.append({
                'date': early['date'].strftime('%Y-%m-%d'),
                'time': early['time'].strftime('%H:%M'),
                'minutes': early['minutes_early'],
                'employee': early['employee_name'],
                'type': 'Early Departure'
            })
        
        # Sort by date
        timeline_data.sort(key=lambda x: x['date'])
        
        # Group by date
        timeline_dates = sorted(set(item['date'] for item in timeline_data))
        
        # Create a histogram by day of week
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        late_by_weekday = [0] * 7
        early_by_weekday = [0] * 7
        
        for item in timeline_data:
            date_obj = datetime.strptime(item['date'], '%Y-%m-%d').date()
            weekday = date_obj.weekday()  # 0 = Monday, 6 = Sunday
            
            if item['type'] == 'Late Arrival':
                late_by_weekday[weekday] += 1
            else:
                early_by_weekday[weekday] += 1
        
        # Create the weekday histogram
        weekday_traces = [
            {
                'x': weekday_names,
                'y': late_by_weekday,
                'type': 'bar',
                'name': 'Late Arrivals',
                'marker': {'color': 'rgba(231, 76, 60, 0.8)'}
            },
            {
                'x': weekday_names,
                'y': early_by_weekday,
                'type': 'bar',
                'name': 'Early Departures',
                'marker': {'color': 'rgba(230, 126, 34, 0.8)'}
            }
        ]
        
        weekday_layout = {
            'title': 'Events by Day of Week',
            'barmode': 'group',
            'xaxis': {'title': 'Day of Week'},
            'yaxis': {'title': 'Number of Events'},
            'margin': {'l': 50, 'r': 50, 'b': 50, 't': 50, 'pad': 4}
        }
        
        weekday_json = json.dumps({'data': weekday_traces, 'layout': weekday_layout})
        
        # Create a timeline showing events over the date range
        timeline_traces = []
        
        # Add trace for late arrivals
        late_dates = [item['date'] for item in timeline_data if item['type'] == 'Late Arrival']
        late_employees = [item['employee'] for item in timeline_data if item['type'] == 'Late Arrival']
        late_minutes = [item['minutes'] for item in timeline_data if item['type'] == 'Late Arrival']
        
        if late_dates:
            timeline_traces.append({
                'x': late_dates,
                'y': late_employees,
                'mode': 'markers',
                'marker': {
                    'color': 'red',
                    'size': [min(m, 30) for m in late_minutes],  # Cap size at 30px
                    'opacity': 0.7
                },
                'text': [f"{m} minutes late" for m in late_minutes],
                'name': 'Late Arrivals'
            })
        
        # Add trace for early departures
        early_dates = [item['date'] for item in timeline_data if item['type'] == 'Early Departure']
        early_employees = [item['employee'] for item in timeline_data if item['type'] == 'Early Departure']
        early_minutes = [item['minutes'] for item in timeline_data if item['type'] == 'Early Departure']
        
        if early_dates:
            timeline_traces.append({
                'x': early_dates,
                'y': early_employees,
                'mode': 'markers',
                'marker': {
                    'color': 'orange',
                    'size': [min(m, 30) for m in early_minutes],  # Cap size at 30px
                    'opacity': 0.7
                },
                'text': [f"{m} minutes early" for m in early_minutes],
                'name': 'Early Departures'
            })
        
        timeline_layout = {
            'title': 'Punctuality Timeline',
            'xaxis': {'title': 'Date'},
            'yaxis': {'title': 'Employee'},
            'margin': {'l': 150, 'r': 50, 'b': 50, 't': 50, 'pad': 4},
            'height': 500
        }
        
        timeline_json = json.dumps({'data': timeline_traces, 'layout': timeline_layout})
        
        # Create HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Late Arrival and Early Departure Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .summary {{ display: flex; margin-bottom: 30px; }}
                .stat-box {{ background-color: #f5f5f5; border-radius: 8px; padding: 15px; margin-right: 20px; text-align: center; }}
                .stat-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
                .stat-label {{ font-size: 14px; color: #666; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 30px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                h1, h2 {{ color: #333; }}
                .late {{ background-color: #ffeaea; }}
                .early {{ background-color: #fff5ea; }}
            </style>
        </head>
        <body>
            <h1>Late Arrival and Early Departure Report</h1>
            <p>Period: {start_date.strftime('%Y-%m-%d')} to {(end_date - timedelta(days=1)).strftime('%Y-%m-%d')}</p>
            <p>Standard hours: {start_time_str} to {end_time_str}</p>
            <p>Thresholds: Late {late_threshold} minutes, Early {early_threshold} minutes</p>
            
            <div class="summary">
                <div class="stat-box">
                    <div class="stat-label">Total Late Arrivals</div>
                    <div class="stat-value">{len(late_arrivals)}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Total Early Departures</div>
                    <div class="stat-value">{len(early_departures)}</div>
                </div>
            </div>
            
            <h2>Punctuality Patterns</h2>
            <div id="weekdayChart" style="height: 300px;"></div>
            
            <h2>Timeline View</h2>
            <div id="timelineChart" style="height: 500px;"></div>
            
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <script>
                var weekdayData = {weekday_json};
                Plotly.newPlot('weekdayChart', weekdayData.data, weekdayData.layout);
                
                var timelineData = {timeline_json};
                Plotly.newPlot('timelineChart', timelineData.data, timelineData.layout);
            </script>
        </body>
        </html>
        """
        
        return HttpResponse(html, content_type='text/html')
        
    except Exception as e:
        return HttpResponse(f"Error generating late/early report: {str(e)}", status=500)


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
