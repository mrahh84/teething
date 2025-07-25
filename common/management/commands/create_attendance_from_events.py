from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, time
from common.models import Event, AttendanceRecord, Employee
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Create attendance records from existing clock events'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date to process (YYYY-MM-DD format, defaults to today)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all dates with clock events',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating records',
        )

    def handle(self, *args, **options):
        if options['date']:
            try:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
                dates_to_process = [target_date]
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Invalid date format. Use YYYY-MM-DD')
                )
                return
        elif options['all']:
            # Get all unique dates that have clock events
            clock_events = Event.objects.filter(
                event_type__name__in=['Clock In', 'Clock Out']
            ).values_list('timestamp__date', flat=True).distinct().order_by('timestamp__date')
            dates_to_process = list(clock_events)
        else:
            # Default to today
            dates_to_process = [timezone.now().date()]

        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write(
                self.style.WARNING('No superuser found. Creating records without created_by field.')
            )

        total_created = 0
        total_updated = 0

        for date in dates_to_process:
            self.stdout.write(f"Processing date: {date}")
            
            # Get all employees who clocked in on this date
            start_of_day = timezone.make_aware(datetime.combine(date, time.min))
            end_of_day = timezone.make_aware(datetime.combine(date, time.max))
            
            clocked_in_employees = Event.objects.filter(
                event_type__name='Clock In',
                timestamp__gte=start_of_day,
                timestamp__lte=end_of_day
            ).values_list('employee_id', flat=True).distinct()
            
            for employee_id in clocked_in_employees:
                employee = Employee.objects.get(id=employee_id)
                
                # Check if attendance record already exists
                existing_record = AttendanceRecord.objects.filter(
                    employee=employee,
                    date=date
                ).first()
                
                if existing_record:
                    if not options['dry_run']:
                        # Update existing record
                        existing_record.notes = f"Updated from existing clock events"
                        existing_record.save()
                        total_updated += 1
                    self.stdout.write(f"  {employee}: Record already exists (updated)")
                else:
                    if not options['dry_run']:
                        # Create new attendance record
                        AttendanceRecord.objects.create(
                            employee=employee,
                            date=date,
                            lunch_time=employee.assigned_lunch_time,
                            created_by=admin_user,
                            status='DRAFT',
                            notes=f"Created from existing clock events"
                        )
                        total_created += 1
                    self.stdout.write(f"  {employee}: Created new record")

        if options['dry_run']:
            self.stdout.write(
                self.style.SUCCESS(f"DRY RUN: Would create {total_created} records and update {total_updated} records")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully created {total_created} records and updated {total_updated} records")
            ) 