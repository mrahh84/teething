from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.auth.models import User

from common.models import Card, Employee, EventType, Location, Event


class Command(BaseCommand):
    help = 'Clock employees in or out in batch'

    def add_arguments(self, parser):
        parser.add_argument('action', type=str, help='Action to perform: "in" or "out"')
        parser.add_argument('cards', type=str, help='Card designations (comma-separated) or "all"')

    def handle(self, *args, **options):
        action = options['action'].lower()
        cards_arg = options['cards']

        if action not in ['in', 'out']:
            raise CommandError(f'Invalid action: {action}. Must be "in" or "out"')

        self.stdout.write(self.style.SUCCESS(f'\nBatch Clock Update - {action.upper()}'))
        self.stdout.write('=' * 40)

        if cards_arg.lower() == 'all':
            # Get all cards
            cards = [card.designation for card in Card.objects.all()]
            self.stdout.write(f'Target: ALL employees ({len(cards)} cards)')
        else:
            # Parse comma-separated card designations
            cards = cards_arg.split(',')
            self.stdout.write(f'Target: {len(cards)} specific cards')

        self.stdout.write('=' * 40)

        # Clock employees in or out
        success_count = 0
        for card_designation in cards:
            if self.clock_employee(card_designation.strip(), action):
                success_count += 1

        self.stdout.write(self.style.SUCCESS(f'\nOperation complete: {success_count} of {len(cards)} employees updated.'))
        
        # Print current status
        self.print_employee_status()

    def clock_employee(self, card_designation, action='in'):
        """
        Clock an employee in or out by their card number.
        
        Args:
            card_designation: The card designation (e.g., 'CARD-1001')
            action: Either 'in' or 'out'
            
        Returns:
            True if successful, False otherwise
        """
        # Get the event type
        event_type_name = "Clock In" if action.lower() == 'in' else "Clock Out"
        try:
            event_type = EventType.objects.get(name=event_type_name)
        except EventType.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Event type '{event_type_name}' not found."))
            return False
        
        # Get the location
        try:
            location = Location.objects.get(name="Main Security")
        except Location.DoesNotExist:
            self.stdout.write(self.style.ERROR("Location 'Main Security' not found."))
            return False
        
        # Get the card
        try:
            card = Card.objects.get(designation=card_designation)
        except Card.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Card '{card_designation}' not found."))
            return False
        
        # Get the employee
        try:
            employee = Employee.objects.get(card_number=card)
        except Employee.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"No employee found with card '{card_designation}'."))
            return False
        
        # Check if employee is already in the desired state
        is_clocked_in = employee.is_clocked_in()
        if (action.lower() == 'in' and is_clocked_in) or (action.lower() == 'out' and not is_clocked_in):
            current_status = "clocked in" if is_clocked_in else "clocked out"
            self.stdout.write(f"  Employee {employee.given_name} {employee.surname} is already {current_status}.")
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
        
        self.stdout.write(self.style.SUCCESS(f"  Successfully {event_type_name.lower()}ed {employee.given_name} {employee.surname}"))
        return True

    def print_employee_status(self):
        """Print the current status of all employees."""
        self.stdout.write('\nCurrent Employee Status:')
        self.stdout.write('=' * 70)
        self.stdout.write(f"{'Name':<30} {'Card':<15} {'Status':<15}")
        self.stdout.write('-' * 70)
        
        clocked_in = 0
        for employee in Employee.objects.all().order_by('surname', 'given_name'):
            name = f"{employee.given_name} {employee.surname}"
            card = employee.card_number.designation if employee.card_number else "No Card"
            is_clocked_in = employee.is_clocked_in()
            status = "Clocked In" if is_clocked_in else "Clocked Out"
            if is_clocked_in:
                clocked_in += 1
            self.stdout.write(f"{name:<30} {card:<15} {status:<15}")
        
        self.stdout.write('-' * 70)
        self.stdout.write(f"Total employees: {Employee.objects.count()}")
        self.stdout.write(self.style.SUCCESS(f"Currently clocked in: {clocked_in}"))
        self.stdout.write(f"Currently clocked out: {Employee.objects.count() - clocked_in}")
        self.stdout.write('=' * 70) 