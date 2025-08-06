"""
Create sample data for the attendance system with 20 employees and their cards.
Run this script with: python manage.py shell < scripts/create_sample_data.py
"""

import random
from django.utils import timezone
from common.models import Card, Employee, EventType, Location, Event
from django.contrib.auth.models import User

# First names and last names for random generation
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", 
    "William", "Elizabeth", "David", "Susan", "Richard", "Jessica", "Joseph", "Sarah",
    "Thomas", "Karen", "Charles", "Nancy", "Christopher", "Lisa", "Daniel", "Margaret",
    "Matthew", "Betty", "Anthony", "Sandra", "Mark", "Ashley", "Donald", "Dorothy"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Jones", "Brown", "Davis", "Miller", "Wilson",
    "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin",
    "Thompson", "Garcia", "Martinez", "Robinson", "Clark", "Rodriguez", "Lewis", "Lee",
    "Walker", "Hall", "Allen", "Young", "Hernandez", "King", "Wright", "Lopez"
]

print("Creating sample data...")

# Get or create event types
clock_in, _ = EventType.objects.get_or_create(name="Clock In")
clock_out, _ = EventType.objects.get_or_create(name="Clock Out")
print(f"Event types ready: {clock_in.name}, {clock_out.name}")

# Get or create main security location
main_security, _ = Location.objects.get_or_create(name="Main Security")
print(f"Location ready: {main_security.name}")

# Get existing admin user for event creation
admin_user = User.objects.filter(is_superuser=True).first()

# Create 20 employees with cards
created_employees = []
for i in range(1, 21):
    # Create a unique card with a numerical designation
    card_designation = f"CARD-{1000 + i}"
    card, card_created = Card.objects.get_or_create(
        designation=card_designation
    )
    
    # Generate a random name
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    
    # Make sure employee name combination is unique
    employee_exists = Employee.objects.filter(given_name=first_name, surname=last_name).exists()
    attempt = 0
    while employee_exists and attempt < 5:
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        employee_exists = Employee.objects.filter(given_name=first_name, surname=last_name).exists()
        attempt += 1
    
    if employee_exists:
        # If still not unique after attempts, use index to make unique
        first_name = f"{first_name}{i}"
    
    # Create employee
    employee, employee_created = Employee.objects.get_or_create(
        given_name=first_name,
        surname=last_name,
        defaults={'card_number': card}
    )
    
    if not employee_created and employee.card_number != card:
        employee.card_number = card
        employee.save()
    
    # Associate with location
    employee.assigned_locations.add(main_security)
    
    created_employees.append(employee)
    
    status = "Created" if employee_created else "Updated"
    print(f"{status} employee: {employee.given_name} {employee.surname} with card {card.designation}")
    
    # Create some random clock events for this employee
    # Let's generate a random number of clock events from the last week
    now = timezone.now()
    
    # 50% chance the employee has at least one clock event
    if random.random() > 0.5:
        # Create between 1 and 10 events per employee
        for j in range(random.randint(1, 10)):
            # Random time within the last week
            random_days = random.randint(0, 7)
            random_hours = random.randint(0, 23)
            random_minutes = random.randint(0, 59)
            
            event_time = now - timezone.timedelta(
                days=random_days,
                hours=random_hours,
                minutes=random_minutes
            )
            
            # Alternate between clock in and clock out
            event_type = clock_in if j % 2 == 0 else clock_out
            
            Event.objects.create(
                employee=employee,
                event_type=event_type,
                location=main_security,
                timestamp=event_time,
                created_by=admin_user
            )
            
            print(f"  Created {event_type.name} event for {employee.given_name} at {event_time.strftime('%Y-%m-%d %H:%M')}")

total_employees = Employee.objects.count()
total_cards = Card.objects.count()
total_events = Event.objects.count()

print(f"\nDatabase now contains:")
print(f"- {total_employees} employees")
print(f"- {total_cards} cards")
print(f"- {total_events} events")
print("\nSample data creation complete.") 