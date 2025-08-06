"""
Clock an employee in or out by their card number.
Usage: python manage.py shell
>>> exec(open('scripts/clock_employee.py').read())
>>> clock_employee('CARD-1001', 'in')  # or 'out'
"""

import sys
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.models import User
from common.models import Card, Employee, EventType, Location, Event


def clock_employee(card_designation, action='in'):
    """
    Clock an employee in or out by their card number.
    
    Args:
        card_designation: The card designation (e.g., 'CARD-1001')
        action: Either 'in' or 'out'
        
    Returns:
        True if successful, False otherwise
    """
    # Validate action
    if action.lower() not in ['in', 'out']:
        print(f"Invalid action: {action}. Must be 'in' or 'out'.")
        return False
    
    # Get the event type
    event_type_name = "Clock In" if action.lower() == 'in' else "Clock Out"
    try:
        event_type = EventType.objects.get(name=event_type_name)
    except EventType.DoesNotExist:
        print(f"Event type '{event_type_name}' not found.")
        return False
    
    # Get the location
    try:
        location = Location.objects.get(name="Main Security")
    except Location.DoesNotExist:
        print("Location 'Main Security' not found.")
        return False
    
    # Get the card
    try:
        card = Card.objects.get(designation=card_designation)
    except Card.DoesNotExist:
        print(f"Card '{card_designation}' not found.")
        return False
    
    # Get the employee
    try:
        employee = Employee.objects.get(card_number=card)
    except Employee.DoesNotExist:
        print(f"No employee found with card '{card_designation}'.")
        return False
    
    # Check if employee is already in the desired state
    is_clocked_in = employee.is_clocked_in()
    if (action.lower() == 'in' and is_clocked_in) or (action.lower() == 'out' and not is_clocked_in):
        current_status = "clocked in" if is_clocked_in else "clocked out"
        print(f"Employee {employee.given_name} {employee.surname} is already {current_status}.")
        return False
    
    # Get admin user for created_by field
    admin_user = User.objects.filter(is_superuser=True).first()
    
    # Create the event
    event = Event.objects.create(
        employee=employee,
        event_type=event_type,
        location=location,
        timestamp=timezone.now(),
        created_by=admin_user
    )
    
    print(f"Successfully {event_type_name.lower()}ed {employee.given_name} {employee.surname} at {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}.")
    return True


# Example usage if run directly
if __name__ == "__main__":
    print("\nClock Employee Tool")
    print("=" * 40)
    print("This script is designed to be imported and used.")
    print("Example usage:")
    print("  >>> exec(open('scripts/clock_employee.py').read())")
    print("  >>> clock_employee('CARD-1001', 'in')  # or 'out'")
    print("=" * 40) 