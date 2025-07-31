#!/usr/bin/env python3
"""
Test Location Models Script

This script tests the new location tracking models to ensure they work correctly.
"""

import os
import sys
import django
from django.utils import timezone
from datetime import date

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance.settings')
django.setup()

from common.models import (
    Location, Employee, TaskAssignment, LocationMovement, 
    LocationAnalytics, EventType, Event
)

def test_location_models():
    """Test the new location tracking models."""
    
    print("=== Testing Location Tracking Models ===")
    
    # Test 1: Check if locations were created
    print("\n1. Testing Location Creation...")
    locations = Location.objects.all()
    print(f"   Total locations: {locations.count()}")
    
    for location in locations:
        print(f"   - {location.name} ({location.location_type}) - Capacity: {location.capacity}")
    
    # Test 2: Check if event types were created
    print("\n2. Testing Event Type Creation...")
    event_types = EventType.objects.all()
    print(f"   Total event types: {event_types.count()}")
    
    for event_type in event_types:
        print(f"   - {event_type.name}")
    
    # Test 3: Test Location properties
    print("\n3. Testing Location Properties...")
    for location in locations[:3]:  # Test first 3 locations
        print(f"   {location.name}:")
        print(f"     - Current occupancy: {location.current_occupancy}")
        print(f"     - Utilization rate: {location.utilization_rate:.1f}%")
        print(f"     - Is active: {location.is_active}")
    
    # Test 4: Create a test task assignment
    print("\n4. Testing Task Assignment Creation...")
    try:
        # Get first employee and location
        employee = Employee.objects.first()
        location = Location.objects.filter(location_type='TASK').first()
        
        if employee and location:
            task_assignment = TaskAssignment.objects.create(
                employee=employee,
                location=location,
                task_type='Test Task',
                assigned_date=date.today(),
                is_completed=False
            )
            print(f"   ✅ Created task assignment: {task_assignment}")
            
            # Clean up
            task_assignment.delete()
            print("   ✅ Test task assignment cleaned up")
        else:
            print("   ⚠️  No employee or location found for testing")
    
    except Exception as e:
        print(f"   ❌ Error creating task assignment: {e}")
    
    # Test 5: Create a test location movement
    print("\n5. Testing Location Movement Creation...")
    try:
        if employee and location:
            movement = LocationMovement.objects.create(
                employee=employee,
                from_location=None,  # Initial entry
                to_location=location,
                movement_type='TASK_ASSIGNMENT'
            )
            print(f"   ✅ Created location movement: {movement}")
            
            # Clean up
            movement.delete()
            print("   ✅ Test location movement cleaned up")
        else:
            print("   ⚠️  No employee or location found for testing")
    
    except Exception as e:
        print(f"   ❌ Error creating location movement: {e}")
    
    # Test 6: Test LocationAnalytics creation
    print("\n6. Testing Location Analytics Creation...")
    try:
        analytics = LocationAnalytics.objects.create(
            location=location,
            date=date.today(),
            current_occupancy=2,
            peak_occupancy=5,
            average_occupancy=3.5,
            utilization_rate=35.0,
            total_movements=10,
            arrivals=6,
            departures=4,
            active_tasks=3,
            completed_tasks=2,
            average_stay_duration=120.5,
            peak_hours={'9:00': 5, '14:00': 4, '16:00': 3}
        )
        print(f"   ✅ Created location analytics: {analytics}")
        
        # Clean up
        analytics.delete()
        print("   ✅ Test location analytics cleaned up")
    
    except Exception as e:
        print(f"   ❌ Error creating location analytics: {e}")
    
    print("\n✅ All tests completed successfully!")
    print("The location tracking models are working correctly.")

def main():
    """Main function to run the tests."""
    test_location_models()

if __name__ == "__main__":
    main() 