"""
Caching utilities for the attendance system to improve performance.
"""

from django.core.cache import cache
from django.conf import settings
from django.db.models import Q
from typing import Optional, Dict, Any
import hashlib
from django.db.models import OuterRef, Subquery


def get_cache_key(prefix: str, *args) -> str:
    """Generate a cache key from prefix and arguments."""
    key_parts = [str(arg) for arg in args]
    key_data = f"{prefix}:{':'.join(key_parts)}"
    # Hash long keys to avoid cache key length limits
    if len(key_data) > 200:
        key_data = f"{prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"
    return key_data


def get_employee_clock_status_cache_key(employee_id: int) -> str:
    """Get cache key for employee clock status."""
    return get_cache_key("employee_status", employee_id)


def get_employee_last_event_cache_key(employee_id: int) -> str:
    """Get cache key for employee last event."""
    return get_cache_key("employee_last_event", employee_id)


def cache_employee_status(employee_id: int, is_clocked_in: bool, last_event_time: Optional[Any] = None):
    """Cache employee clock status and last event time."""
    timeout = getattr(settings, 'CACHE_TIMEOUTS', {}).get('employee_status', 60)
    
    # Cache clock status
    status_key = get_employee_clock_status_cache_key(employee_id)
    cache.set(status_key, is_clocked_in, timeout)
    
    # Cache last event time if provided
    if last_event_time is not None:
        event_key = get_employee_last_event_cache_key(employee_id)
        cache.set(event_key, last_event_time, timeout)


def get_cached_employee_status(employee_id: int) -> Optional[bool]:
    """Get cached employee clock status."""
    cache_key = get_employee_clock_status_cache_key(employee_id)
    return cache.get(cache_key)


def get_cached_employee_last_event(employee_id: int) -> Optional[Any]:
    """Get cached employee last event time."""
    cache_key = get_employee_last_event_cache_key(employee_id)
    return cache.get(cache_key)


def invalidate_employee_cache(employee_id: int):
    """Invalidate all cached data for an employee."""
    status_key = get_employee_clock_status_cache_key(employee_id)
    event_key = get_employee_last_event_cache_key(employee_id)
    
    cache.delete(status_key)
    cache.delete(event_key)


def get_cached_event_types():
    """Get cached event types."""
    cache_key = "event_types:all"
    cached_types = cache.get(cache_key)
    
    if cached_types is None:
        from common.models import EventType
        cached_types = {et.name: et for et in EventType.objects.all()}
        timeout = getattr(settings, 'CACHE_TIMEOUTS', {}).get('event_types', 3600)
        cache.set(cache_key, cached_types, timeout)
    
    return cached_types


def get_cached_locations():
    """Get cached locations."""
    cache_key = "locations:all"
    cached_locations = cache.get(cache_key)
    
    if cached_locations is None:
        from common.models import Location
        cached_locations = {loc.name: loc for loc in Location.objects.all()}
        timeout = getattr(settings, 'CACHE_TIMEOUTS', {}).get('locations', 3600)
        cache.set(cache_key, cached_locations, timeout)
    
    return cached_locations


def bulk_cache_employee_statuses(employee_ids: list):
    """
    Bulk cache employee statuses to reduce database queries.
    This is more efficient than caching one by one.
    """
    from common.models import Employee, Event
    
    # Get employees that aren't already cached
    uncached_ids = []
    for emp_id in employee_ids:
        if get_cached_employee_status(emp_id) is None:
            uncached_ids.append(emp_id)
    
    if not uncached_ids:
        return  # All already cached
    
    # Get last clock events for uncached employees 
    # Use a subquery to get the latest event for each employee
    
    # Get the latest event timestamp for each employee
    latest_event_subquery = Event.objects.filter(
        employee_id=OuterRef('employee_id'),
        event_type__name__in=["Clock In", "Clock Out"]
    ).order_by('-timestamp').values('id')[:1]
    
    # Get the actual latest events
    latest_events = Event.objects.filter(
        id__in=Subquery(latest_event_subquery),
        employee_id__in=uncached_ids
    ).select_related('event_type')
    
    # Build a map of employee_id -> event data
    last_events = {}
    for event in latest_events:
        last_events[event.employee_id] = {
            'is_clocked_in': event.event_type.name == "Clock In",
            'last_event_time': event.timestamp
        }
    
    # Cache the results
    timeout = getattr(settings, 'CACHE_TIMEOUTS', {}).get('employee_status', 60)
    for emp_id in uncached_ids:
        if emp_id in last_events:
            event_data = last_events[emp_id]
            cache_employee_status(
                emp_id, 
                event_data['is_clocked_in'], 
                event_data['last_event_time']
            )
        else:
            # No clock events for this employee
            cache_employee_status(emp_id, False, None)


def get_main_security_cache_key(page: int, sort_by: str, sort_direction: str, status_filter: str, search: str) -> str:
    """Get cache key for main security page data."""
    return get_cache_key("main_security", page, sort_by, sort_direction, status_filter, search)


def cache_main_security_data(key: str, data: Dict[str, Any]):
    """Cache main security page data."""
    timeout = getattr(settings, 'CACHE_TIMEOUTS', {}).get('main_security_page', 30)
    cache.set(key, data, timeout)


def get_cached_main_security_data(key: str) -> Optional[Dict[str, Any]]:
    """Get cached main security page data."""
    return cache.get(key)


def invalidate_main_security_cache():
    """Invalidate main security page cache when employee data changes."""
    # Since we don't know all possible cache keys, we use a simple pattern
    # In production, consider using cache tags or a more sophisticated approach
    cache.clear()  # This is aggressive but ensures consistency 