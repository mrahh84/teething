#!/usr/bin/env python3
"""
Create Location Event Types Script

This script creates the necessary event types for enhanced location tracking
based on the Excel data analysis.
"""

import os
import sys
import django
from django.utils import timezone

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance.settings')
django.setup()

from common.models import EventType, Location

def create_location_event_types():
    """Create event types for location tracking."""
    
    # Event types for location tracking
    event_types = [
        'Task Assignment',
        'Task Completion',
        'Location Entry',
        'Location Exit',
        'Break Start',
        'Break End',
        'Meeting Start',
        'Meeting End',
    ]
    
    created_types = []
    existing_types = []
    
    for event_type_name in event_types:
        event_type, created = EventType.objects.get_or_create(
            name=event_type_name,
            defaults={'name': event_type_name}
        )
        
        if created:
            created_types.append(event_type_name)
            print(f"✅ Created event type: {event_type_name}")
        else:
            existing_types.append(event_type_name)
            print(f"ℹ️  Event type already exists: {event_type_name}")
    
    print(f"\n📊 Summary:")
    print(f"  Created: {len(created_types)} new event types")
    print(f"  Existing: {len(existing_types)} event types")
    
    return created_types, existing_types

def create_location_types():
    """Create location types based on Excel analysis."""
    
    # Location types from Excel analysis
    location_types = [
        {
            'name': 'Goobi',
            'location_type': 'TASK',
            'capacity': 10,
            'description': 'Goobi digitization workstation area'
        },
        {
            'name': 'OCR4All',
            'location_type': 'TASK',
            'capacity': 8,
            'description': 'OCR4All processing workstation area'
        },
        {
            'name': 'Transkribus',
            'location_type': 'TASK',
            'capacity': 6,
            'description': 'Transkribus transcription workstation area'
        },
        {
            'name': 'Research',
            'location_type': 'TASK',
            'capacity': 4,
            'description': 'Research and analysis workstation area'
        },
        {
            'name': 'VERSA',
            'location_type': 'TASK',
            'capacity': 5,
            'description': 'VERSA processing workstation area'
        },
        {
            'name': 'MetaData',
            'location_type': 'ROOM',
            'capacity': 3,
            'description': 'Metadata processing room'
        },
        {
            'name': 'IT Suite',
            'location_type': 'ROOM',
            'capacity': 2,
            'description': 'IT support and technical services room'
        },
        {
            'name': 'BC100',
            'location_type': 'ROOM',
            'capacity': 4,
            'description': 'BC100 meeting and workspace'
        },
        {
            'name': 'Meeting Room',
            'location_type': 'MEETING',
            'capacity': 8,
            'description': 'General meeting room'
        },
    ]
    
    created_locations = []
    existing_locations = []
    
    for location_data in location_types:
        location, created = Location.objects.get_or_create(
            name=location_data['name'],
            defaults={
                'location_type': location_data['location_type'],
                'capacity': location_data['capacity'],
                'description': location_data['description'],
                'is_active': True
            }
        )
        
        if created:
            created_locations.append(location_data['name'])
            print(f"✅ Created location: {location_data['name']} ({location_data['location_type']})")
        else:
            existing_locations.append(location_data['name'])
            print(f"ℹ️  Location already exists: {location_data['name']}")
    
    print(f"\n📊 Location Summary:")
    print(f"  Created: {len(created_locations)} new locations")
    print(f"  Existing: {len(existing_locations)} locations")
    
    return created_locations, existing_locations

def main():
    """Main function to create location tracking data."""
    
    print("=== Location Tracking Setup ===")
    print("Creating event types and locations for enhanced location tracking...")
    
    # Create event types
    print("\n1. Creating Event Types...")
    created_types, existing_types = create_location_event_types()
    
    # Create location types
    print("\n2. Creating Location Types...")
    created_locations, existing_locations = create_location_types()
    
    # Summary
    print(f"\n🎉 Setup Complete!")
    print(f"  Event Types: {len(created_types)} created, {len(existing_types)} existing")
    print(f"  Locations: {len(created_locations)} created, {len(existing_locations)} existing")
    
    if created_types:
        print(f"\n📝 New Event Types:")
        for event_type in created_types:
            print(f"  - {event_type}")
    
    if created_locations:
        print(f"\n📍 New Locations:")
        for location in created_locations:
            print(f"  - {location}")
    
    print(f"\n✅ Location tracking setup complete!")
    print("You can now proceed with Phase 3: Data Import & Integration")

if __name__ == "__main__":
    main() 