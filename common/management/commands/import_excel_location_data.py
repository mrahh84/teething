from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
import pandas as pd
import os
from datetime import datetime
from common.models import Employee, Location, TaskAssignment, LocationMovement, EventType

class Command(BaseCommand):
    help = 'Import location tracking data from Excel file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='Garbage/Task Splitting Sheet June 2025.xlsx',
            help='Path to the Excel file'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for import (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for import (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        start_date = options.get('start_date')
        end_date = options.get('end_date')
        dry_run = options['dry_run']

        if not os.path.exists(file_path):
            raise CommandError(f'Excel file not found: {file_path}')

        self.stdout.write(
            self.style.SUCCESS(f'Starting Excel location data import from: {file_path}')
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be imported'))

        try:
            # Read Excel file
            excel_file = pd.ExcelFile(file_path)
            self.stdout.write(f'Found {len(excel_file.sheet_names)} sheets')

            # Process each sheet
            total_assignments = 0
            total_movements = 0
            total_employees = 0
            processed_sheets = 0

            for sheet_name in excel_file.sheet_names:
                # Skip non-date sheets
                if not self._is_date_sheet(sheet_name):
                    continue

                try:
                    sheet_data = self._process_sheet(file_path, sheet_name, start_date, end_date)
                    if sheet_data:
                        if not dry_run:
                            assignments, movements, employees = self._import_sheet_data(sheet_data)
                            total_assignments += assignments
                            total_movements += movements
                            total_employees += employees
                        else:
                            # Count what would be imported
                            assignments, movements, employees = self._count_sheet_data(sheet_data)
                            total_assignments += assignments
                            total_movements += movements
                            total_employees += employees

                        processed_sheets += 1
                        self.stdout.write(
                            f'Processed {sheet_name}: {assignments} assignments, {movements} movements, {employees} employees'
                        )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error processing sheet {sheet_name}: {e}')
                    )

            # Summary
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nImport Summary:\n'
                    f'  Processed sheets: {processed_sheets}\n'
                    f'  Total assignments: {total_assignments}\n'
                    f'  Total movements: {total_movements}\n'
                    f'  Total employees: {total_employees}'
                )
            )

        except Exception as e:
            raise CommandError(f'Import failed: {e}')

    def _is_date_sheet(self, sheet_name):
        """Check if sheet name represents a date."""
        try:
            # Try to parse as date (e.g., "June 20", "July 1")
            datetime.strptime(sheet_name, '%B %d')
            return True
        except ValueError:
            return False

    def _process_sheet(self, file_path, sheet_name, start_date, end_date):
        """Process a single sheet and extract location data."""
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        
        # Check if sheet has required columns
        required_columns = ['Name', 'Assignment', 'Room']
        if not all(col in df.columns for col in required_columns):
            return None

        # Parse date from sheet name
        try:
            sheet_date = datetime.strptime(sheet_name, '%B %d')
            sheet_date = sheet_date.replace(year=2025)  # Based on file name
        except ValueError:
            return None

        # Apply date filters if specified
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            if sheet_date < start_dt:
                return None

        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            if sheet_date > end_dt:
                return None

        # Extract data
        data = []
        for _, row in df.iterrows():
            if pd.notna(row['Name']) and pd.notna(row['Assignment']):
                data.append({
                    'employee_name': str(row['Name']).strip(),
                    'assignment': str(row['Assignment']).strip(),
                    'room': str(row['Room']).strip() if pd.notna(row['Room']) else None,
                    'date': sheet_date.date(),
                    'sheet_name': sheet_name
                })

        return data

    def _import_sheet_data(self, sheet_data):
        """Import sheet data into database."""
        assignments_created = 0
        movements_created = 0
        employees_processed = set()

        with transaction.atomic():
            for record in sheet_data:
                # Find or create employee
                employee = self._find_employee(record['employee_name'])
                if not employee:
                    continue

                employees_processed.add(employee.id)

                # Find location
                location = self._find_location(record['assignment'])
                if not location:
                    continue

                # Create task assignment
                assignment, created = TaskAssignment.objects.get_or_create(
                    employee=employee,
                    location=location,
                    assigned_date=record['date'],
                    defaults={
                        'task_type': record['assignment'],
                        'is_completed': False
                    }
                )

                if created:
                    assignments_created += 1

                # Create location movement (entry)
                movement, created = LocationMovement.objects.get_or_create(
                    employee=employee,
                    to_location=location,
                    movement_type='TASK_ASSIGNMENT',
                    timestamp__date=record['date'],
                    defaults={
                        'from_location': None,  # Initial entry
                        'notes': f'Imported from {record["sheet_name"]}'
                    }
                )

                if created:
                    movements_created += 1

        return assignments_created, movements_created, len(employees_processed)

    def _count_sheet_data(self, sheet_data):
        """Count what would be imported (dry run)."""
        assignments_count = 0
        movements_count = 0
        employees_processed = set()

        for record in sheet_data:
            employee = self._find_employee(record['employee_name'])
            if not employee:
                continue

            employees_processed.add(employee.id)

            location = self._find_location(record['assignment'])
            if not location:
                continue

            # Count potential assignments
            if not TaskAssignment.objects.filter(
                employee=employee,
                location=location,
                assigned_date=record['date']
            ).exists():
                assignments_count += 1

            # Count potential movements
            if not LocationMovement.objects.filter(
                employee=employee,
                to_location=location,
                movement_type='TASK_ASSIGNMENT',
                timestamp__date=record['date']
            ).exists():
                movements_count += 1

        return assignments_count, movements_count, len(employees_processed)

    def _find_employee(self, employee_name):
        """Find employee by name (fuzzy matching)."""
        # Try exact match first
        try:
            # Split name into parts
            name_parts = employee_name.split()
            if len(name_parts) >= 2:
                given_name = name_parts[0]
                surname = ' '.join(name_parts[1:])
                
                employee = Employee.objects.filter(
                    given_name__iexact=given_name,
                    surname__iexact=surname
                ).first()
                
                if employee:
                    return employee
        except:
            pass

        # Try partial matching
        employees = Employee.objects.filter(
            given_name__icontains=employee_name.split()[0]
        )
        
        if employees.count() == 1:
            return employees.first()
        
        return None

    def _find_location(self, assignment_name):
        """Find location by assignment name."""
        # Map assignment names to location names
        assignment_mapping = {
            'Goobi': 'Goobi',
            'OCR4All': 'OCR4All',
            'OCR4ALL': 'OCR4All',
            'Transkribus': 'Transkribus',
            'Research': 'Research',
            'VERSA': 'VERSA',
            'MetaData': 'MetaData',
            'MetaData ': 'MetaData',
            'IT Suite': 'IT Suite',
            'BC100': 'BC100',
            'Meeting Room': 'Meeting Room',
        }

        location_name = assignment_mapping.get(assignment_name, assignment_name)
        return Location.objects.filter(name=location_name).first() 