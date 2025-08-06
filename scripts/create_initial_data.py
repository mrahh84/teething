#!/usr/bin/env python
"""
Create initial required data for the attendance system.
This script creates the required EventType and Location instances.
"""

import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance.settings')
django.setup()

from common.models import EventType, Location


def create_initial_data():
    """Create the required initial data."""
    print("Creating initial data...")
    
    # Create EventTypes
    clock_in, created = EventType.objects.get_or_create(name="Clock In")
    if created:
        print(f"Created EventType: {clock_in}")
    else:
        print(f"EventType already exists: {clock_in}")
    
    clock_out, created = EventType.objects.get_or_create(name="Clock Out")
    if created:
        print(f"Created EventType: {clock_out}")
    else:
        print(f"EventType already exists: {clock_out}")
    
    # Create Location
    main_security, created = Location.objects.get_or_create(name="Main Security")
    if created:
        print(f"Created Location: {main_security}")
    else:
        print(f"Location already exists: {main_security}")


if __name__ == "__main__":
    create_initial_data()
    print("Initial data setup complete.") 