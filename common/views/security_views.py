"""
Security-related views (clock-in/out operations).

This module contains all security dashboard and clock management functionality.
Migrated from legacy_views.py as part of Phase 2 modularization.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as django_timezone
from drf_spectacular.utils import extend_schema
from django.db.models import Q, Prefetch
from datetime import datetime, timedelta
import logging

from ..models import Employee, Event, EventType, Location
from ..decorators import security_required


@security_required  # Security role and above
@extend_schema(exclude=True)
def main_security(request):
    """
    Displays the main security dashboard, listing all employees
    and their current clock-in/out status. Requires login.
    Optimized with caching for better performance.
    """
    # Get request parameters for sorting and filtering
    search_query = request.GET.get("search", "")
    status_filter = request.GET.get("status", "all")
    sort_by = request.GET.get("sort", "surname")
    sort_direction = request.GET.get("direction", "asc")
    page_number = request.GET.get("page", "1")
    server_items_per_page = request.GET.get("items", "100")
    start_letter = request.GET.get("letter", "")

    try:
        server_items_per_page = int(server_items_per_page)
        if server_items_per_page not in [25, 50, 100, 200]:
            server_items_per_page = 100
    except ValueError:
        server_items_per_page = 100
    
    # Try to get cached data first
    try:
        from common.cache_utils import (
            get_main_security_cache_key, 
            get_cached_main_security_data,
            cache_main_security_data,
            bulk_cache_employee_statuses
        )
        
        cache_key = get_main_security_cache_key(
            int(page_number), sort_by, sort_direction, status_filter, search_query, start_letter
        )
        cached_data = get_cached_main_security_data(cache_key)
        
        if cached_data:
            return render(request, "main_security.html", cached_data)
    except ImportError:
        pass  # Fall back to non-cached version
        
    # Start with all employees, using optimized queries
    employees_query = Employee.objects.select_related("card_number").all()

    # Count stats for the dashboard before applying filters
    total_employees = employees_query.count()

    # Apply search if provided
    if search_query:
        employees_query = employees_query.filter(
            Q(given_name__icontains=search_query)
            | Q(surname__icontains=search_query)
            | Q(card_number__designation__icontains=search_query)
        )

    # Prefetch related events with only the latest clock in/out events to improve performance
    # This optimizes the is_clocked_in calculation
    one_month_ago = django_timezone.now() - timedelta(days=30)
    latest_events = (
        Event.objects.filter(
            timestamp__gte=one_month_ago, event_type__name__in=["Clock In", "Clock Out"]
        )
        .select_related("event_type")
        .order_by("-timestamp")
    )

    employees_query = employees_query.prefetch_related(
        Prefetch("employee_events", queryset=latest_events, to_attr="recent_events")
    )

    # Apply sorting
    if sort_by in ["given_name", "surname"]:
        order_by = sort_by
        if sort_direction == "desc":
            order_by = f"-{order_by}"
        employees_query = employees_query.order_by(order_by)

    # Get the employee list - we need to materialize the queryset here
    # because we need to apply status filtering and card sorting in Python
    all_employees = list(employees_query)
    
    # Bulk cache employee statuses to improve performance
    try:
        employee_ids = [emp.id for emp in all_employees]
        bulk_cache_employee_statuses(employee_ids)
    except (ImportError, NameError):
        pass  # Ignore if caching not available

    # Apply status filtering in Python since it's a calculated property
    if status_filter == "in":
        all_employees = [
            employee for employee in all_employees if employee.is_clocked_in()
        ]
    elif status_filter == "out":
        all_employees = [
            employee for employee in all_employees if not employee.is_clocked_in()
        ]

    # Sort by card number if requested (also needs to be done in Python)
    if sort_by == "card":
        reverse = sort_direction == "desc"
        all_employees.sort(
            key=lambda emp: emp.card_number.designation if emp.card_number else "",
            reverse=reverse,
        )
    
    # Apply letter filter if provided (after all other filtering)
    if start_letter and start_letter != 'all' and len(start_letter) == 1:
        all_employees = [
            employee for employee in all_employees 
            if employee.surname.upper().startswith(start_letter.upper())
        ]

    # Server-side pagination
    paginator = Paginator(all_employees, server_items_per_page)
    try:
        employees = paginator.page(page_number)
    except Exception:
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
        "total_employees": len(all_employees),  # Use filtered count
        "clocked_in_count": clocked_in_count,
        "clocked_out_count": clocked_out_count,
        "start_letter": start_letter,
        "current_page": int(page_number),
        "total_pages": paginator.num_pages,
        "items_per_page": server_items_per_page,
    }
    
    # Cache the result for future requests
    try:
        cache_main_security_data(cache_key, context)
    except (ImportError, NameError):
        pass  # Ignore if caching not available
    
    return render(request, "main_security.html", context)


@security_required  # Security role and above
@extend_schema(exclude=True)
def main_security_clocked_in_status_flip(request, id):
    """
    Handles the clock-in/clock-out action for an employee from the main security view.
    Creates a new 'Clock In' or 'Clock Out' event. Requires login.
    Includes a basic debounce mechanism.
    Optimized with caching for better performance.
    """
    # Check if we need to clear cache (for testing purposes)
    if request.GET.get('clear_cache') == 'true':
        try:
            from django.core.cache import cache
            cache.delete(f"employee_status_{id}")
            cache.delete(f"employee_last_event_{id}")
            messages.info(request, "Employee cache cleared for testing.")
        except Exception:
            pass
    
    employee = get_object_or_404(Employee, id=id)

    # Determine the *opposite* action to take
    currently_clocked_in = employee.is_clocked_in()
    target_event_type_name = "Clock Out" if currently_clocked_in else "Clock In"

    # Basic Debounce: Prevent accidental double-clicks/rapid toggling
    debounce_seconds = 2  # Reduced from 5 to 2 seconds for better UX
    
    # More robust debounce check - also check recent events directly from database
    recent_events = Event.objects.filter(
        employee=employee,
        event_type__name__in=['Clock In', 'Clock Out']
    ).order_by('-timestamp')[:1]
    
    if recent_events.exists():
        most_recent_event = recent_events.first()
        current_time = django_timezone.now()
        event_time = most_recent_event.timestamp
        
        # Simple time difference calculation
        time_since_last_event = (current_time - event_time).total_seconds()
        
        # Safety check: if event is in the future or more than 1 hour ago, skip debounce
        if time_since_last_event < -3600 or time_since_last_event > 3600:
            pass
        elif time_since_last_event < debounce_seconds:
            messages.warning(
                request, f"Please wait {debounce_seconds} seconds before clocking again."
            )
            logging.info(
                f"Clock action for {employee} blocked by debounce ({debounce_seconds}s) - last event was {time_since_last_event:.1f}s ago"
            )
            return redirect("main_security")

    try:
        # Try to get cached event types and locations first for better performance
        try:
            from common.cache_utils import get_cached_event_types, get_cached_locations
            event_types = get_cached_event_types()
            locations = get_cached_locations()
            
            event_type = event_types.get(target_event_type_name)
            location = locations.get("Main Security")
            
            if not event_type:
                raise EventType.DoesNotExist(f"Event type '{target_event_type_name}' not found in cache")
            if not location:
                raise Location.DoesNotExist("Location 'Main Security' not found in cache")
                
        except ImportError:
            # Fall back to database queries if caching not available
            event_type = EventType.objects.get(name=target_event_type_name)
            location = Location.objects.get(name="Main Security")
            
    except (EventType.DoesNotExist, Location.DoesNotExist) as e:
        # Handle case where required EventType or Location is missing
        logging.error(f"Required EventType or Location missing: {e}")
        messages.error(request, "System configuration error. Cannot process request.")
        return HttpResponseBadRequest("System configuration error.")

    # Create the new clock event with local timezone timestamp
    event = Event.objects.create(
        employee=employee,
        event_type=event_type,
        location=location,
        created_by=request.user,
        timestamp=django_timezone.localtime(django_timezone.now())
    )

    # Clear relevant caches to ensure real-time updates
    try:
        from django.core.cache import cache
        cache.delete(f"employee_status_{employee.id}")
        cache.delete(f"employee_last_event_{employee.id}")
        cache.delete_pattern("main_security_*")
        cache.delete_pattern("employee_status_*")
    except Exception:
        pass

    # Add success message
    event_time = str(event)
    messages.success(request, event_time)

    # Preserve the filter parameters when redirecting
    query_params = request.GET.copy()
    redirect_url = "main_security"

    if query_params:
        query_string = query_params.urlencode()
        return redirect(f"{redirect_url}?{query_string}")
    else:
        return redirect(redirect_url)


@security_required  # Security role and above (read-only)
@extend_schema(exclude=True)
def employee_events(request, id):
    """
    Displays a detailed list of all events for a specific employee.
    Requires login.
    """
    employee = get_object_or_404(Employee.objects.select_related("card_number"), id=id)

    # Get filter parameters
    date_filter = request.GET.get("date", "")
    event_type_filter = request.GET.get("event_type", "")

    # Get all events for this employee
    employee_events_query = employee.employee_events.select_related(
        "event_type", "location", "created_by"
    )

    # Apply date filter if provided
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
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
    event_types = EventType.objects.values_list("name", flat=True).distinct()

    # Get all locations for the location dropdown in the edit form
    locations = Location.objects.all()

    # Get some statistics for the employee
    today = django_timezone.now().date()
    week_ago = today - timedelta(days=7)

    today_events_count = Event.objects.filter(
        employee=employee, timestamp__date=today
    ).count()

    week_events_count = Event.objects.filter(
        employee=employee, timestamp__date__gte=week_ago
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


@security_required  # Security role and above
@extend_schema(exclude=True)
def update_event(request, employee_id):
    """
    Handle updating an event from the frontend.
    """
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("employee_events", id=employee_id)

    employee = get_object_or_404(Employee, id=employee_id)
    event_id = request.POST.get("event_id")

    if not event_id:
        messages.error(request, "No event specified.")
        return redirect("employee_events", id=employee_id)

    try:
        event = Event.objects.get(id=event_id, employee=employee)
    except Event.DoesNotExist:
        messages.error(request, "Event not found.")
        return redirect("employee_events", id=employee_id)

    # Get form data
    event_type_name = request.POST.get("event_type")
    location_id = request.POST.get("location")
    date_str = request.POST.get("date")
    time_str = request.POST.get("time")

    # Validate data
    if not all([event_type_name, location_id, date_str, time_str]):
        messages.error(request, "All fields are required.")
        return redirect("employee_events", id=employee_id)

    try:
        # Get event type and location
        event_type = EventType.objects.get(name=event_type_name)
        location = Location.objects.get(id=location_id)

        # Parse date and time
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        time_obj = datetime.strptime(time_str, "%H:%M:%S").time()
        timestamp = django_timezone.make_aware(datetime.combine(date_obj, time_obj))

        # Update event
        event.event_type = event_type
        event.location = location
        event.timestamp = timestamp
        event.save()

        messages.success(request, f"Event successfully updated.")
    except (EventType.DoesNotExist, Location.DoesNotExist, ValueError) as e:
        messages.error(request, f"Error updating event: {str(e)}")

    return redirect("employee_events", id=employee_id)


@security_required  # Security role and above
@extend_schema(exclude=True)
def delete_event(request, employee_id):
    """
    Handle deleting an event from the frontend.
    """
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("employee_events", id=employee_id)

    employee = get_object_or_404(Employee, id=employee_id)
    event_id = request.POST.get("event_id")

    if not event_id:
        messages.error(request, "No event specified.")
        return redirect("employee_events", id=employee_id)

    try:
        event = Event.objects.get(id=event_id, employee=employee)
        event_type_name = event.event_type.name
        event.delete()
        messages.success(request, f"'{event_type_name}' event successfully deleted.")
    except Event.DoesNotExist:
        messages.error(request, "Event not found.")

    return redirect("employee_events", id=employee_id)


def main_security_clock_out(request, employee_id):
    """Placeholder - implement clock out functionality."""
    pass


def main_security_clock_in(request, employee_id):
    """Placeholder - implement clock in functionality."""
    pass