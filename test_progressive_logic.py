#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance.settings')
django.setup()

from django.utils import timezone
from datetime import datetime, time, date
from common.models import Employee, Event, EventType, AttendanceRecord

def test_progressive_logic():
    print("Testing Progressive Entry Logic...")
    
    # Test with July 24 data
    test_date = date(2025, 7, 24)
    print(f"Test date: {test_date}")
    
    # Get all active employees
    employees = Employee.objects.filter(is_active=True).order_by('surname', 'given_name')
    print(f"Total active employees: {employees.count()}")
    
    # Get attendance records for test date
    test_records = AttendanceRecord.objects.filter(date=test_date).select_related('employee')
    print(f"Attendance records for {test_date}: {test_records.count()}")
    
    # Get employees who have clocked in on test date
    start_of_day = timezone.make_aware(datetime.combine(test_date, time.min))
    end_of_day = timezone.make_aware(datetime.combine(test_date, time.max))
    
    clocked_in_employees = Event.objects.filter(
        event_type__name='Clock In',
        timestamp__gte=start_of_day,
        timestamp__lte=end_of_day
    ).values_list('employee_id', flat=True).distinct()
    
    print(f"Employees who clocked in on {test_date}: {len(clocked_in_employees)}")
    
    # Test arrival and departure time properties
    print("\nTesting Arrival and Departure Times:")
    for record in test_records[:5]:  # Test first 5 records
        print(f"\nEmployee: {record.employee}")
        print(f"  Arrival Time: {record.arrival_time}")
        print(f"  Departure Time: {record.departure_time}")
        print(f"  Worked Hours: {record.worked_hours}")
        
        # Check if employee is clocked in
        is_clocked_in = record.employee.id in clocked_in_employees
        print(f"  Is Clocked In: {is_clocked_in}")
    
    # Test clock events for test date
    print(f"\nClock Events for {test_date}:")
    clock_events = Event.objects.filter(
        timestamp__gte=start_of_day,
        timestamp__lte=end_of_day,
        event_type__name__in=['Clock In', 'Clock Out']
    ).select_related('employee', 'event_type').order_by('timestamp')
    
    for event in clock_events[:10]:  # Show first 10 events
        print(f"  {event.employee}: {event.event_type.name} at {event.timestamp.strftime('%H:%M')}")

if __name__ == "__main__":
    test_progressive_logic() 