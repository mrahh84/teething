"""
Create initial required data for the attendance system.
Run this script with: python manage.py shell < scripts/initial_data.py
"""

from common.models import EventType, Location

print("Creating initial data...")

# Create EventTypes
clock_in, created = EventType.objects.get_or_create(name="Clock In")
print(f"EventType 'Clock In': {'Created' if created else 'Already exists'}")

clock_out, created = EventType.objects.get_or_create(name="Clock Out")
print(f"EventType 'Clock Out': {'Created' if created else 'Already exists'}")

# Create Location
main_security, created = Location.objects.get_or_create(name="Main Security")
print(f"Location 'Main Security': {'Created' if created else 'Already exists'}")

print("Initial data setup complete.") 