#!/usr/bin/env python
"""
Batch update script to clock employees in or out.
Usage: python scripts/batch_clock_update.py [in|out] [all|card1,card2,...]

Examples:
  - Clock all employees in: python scripts/batch_clock_update.py in all
  - Clock specific employees out: python scripts/batch_clock_update.py out CARD-1001,CARD-1005
"""

import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance.settings')
django.setup()

from django.utils import timezone
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
        print(f"  Employee {employee.given_name} {employee.surname} is already {current_status}.")
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
    
    print(f"  Successfully {event_type_name.lower()}ed {employee.given_name} {employee.surname} at {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}.")
    return True


def print_employee_status():
    """Print the current status of all employees."""
    print("\nCurrent Employee Status:")
    print("=" * 70)
    print(f"{'Name':<30} {'Card':<15} {'Status':<15}")
    print("-" * 70)
    
    clocked_in = 0
    for employee in Employee.objects.all().order_by('surname', 'given_name'):
        name = f"{employee.given_name} {employee.surname}"
        card = employee.card_number.designation if employee.card_number else "No Card"
        is_clocked_in = employee.is_clocked_in()
        status = "Clocked In" if is_clocked_in else "Clocked Out"
        if is_clocked_in:
            clocked_in += 1
        print(f"{name:<30} {card:<15} {status:<15}")
    
    print("-" * 70)
    print(f"Total employees: {Employee.objects.count()}")
    print(f"Currently clocked in: {clocked_in}")
    print(f"Currently clocked out: {Employee.objects.count() - clocked_in}")
    print("=" * 70)


def main():
    """Main function to handle command-line arguments."""
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} [in|out] [all|card1,card2,...]")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    if action not in ['in', 'out']:
        print(f"Invalid action: {action}. Must be 'in' or 'out'.")
        sys.exit(1)
    
    cards_arg = sys.argv[2]
    
    print("\nBatch Clock Update")
    print("=" * 40)
    print(f"Action: Clock {action.upper()}")
    
    if cards_arg.lower() == 'all':
        # Get all cards
        cards = [card.designation for card in Card.objects.all()]
        print(f"Target: ALL employees ({len(cards)} cards)")
    else:
        # Parse comma-separated card designations
        cards = cards_arg.split(',')
        print(f"Target: {len(cards)} specific cards")
    
    print("=" * 40)
    
    # Clock employees in or out
    success_count = 0
    for card_designation in cards:
        if clock_employee(card_designation.strip(), action):
            success_count += 1
    
    print(f"\nOperation complete: {success_count} of {len(cards)} employees updated.")
    
    # Print current status
    print_employee_status()


if __name__ == "__main__":
    main() 