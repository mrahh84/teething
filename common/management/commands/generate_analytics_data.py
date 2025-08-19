from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta, time
from decimal import Decimal
import random

from common.models import Employee, EmployeeAnalytics, Department, Event, EventType, Location


class Command(BaseCommand):
    help = 'Generate sample analytics data for testing Phase 3 features'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days of data to generate (default: 30)'
        )
        parser.add_argument(
            '--employees',
            type=int,
            default=10,
            help='Number of employees to generate data for (default: 10)'
        )

    def handle(self, *args, **options):
        days = options['days']
        num_employees = options['employees']
        
        self.stdout.write(f"Generating {days} days of analytics data for {num_employees} employees...")
        
        # Get or create required objects
        employees = list(Employee.objects.filter(is_active=True)[:num_employees])
        if not employees:
            self.stdout.write(self.style.ERROR('No active employees found. Please create some employees first.'))
            return
        
        departments = list(Department.objects.filter(is_active=True))
        if not departments:
            self.stdout.write(self.style.ERROR('No departments found. Please create some departments first.'))
            return
        
        event_types = list(EventType.objects.all())
        if not event_types:
            self.stdout.write(self.style.ERROR('No event types found. Please create some event types first.'))
            return
        
        locations = list(Location.objects.filter(is_active=True))
        if not locations:
            self.stdout.write(self.style.ERROR('No locations found. Please create some locations first.'))
            return
        
        # Generate analytics data for each employee
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        analytics_created = 0
        
        for employee in employees:
            # Assign random department if not already assigned
            if not employee.department:
                employee.department = random.choice(departments)
                employee.save()
            
            # Generate analytics for each day
            current_date = start_date
            while current_date <= end_date:
                # Skip weekends (Saturday=5, Sunday=6)
                if current_date.weekday() < 5:  # Monday to Friday
                    analytics = self.generate_daily_analytics(employee, current_date, event_types, locations)
                    if analytics:
                        analytics_created += 1
                
                current_date += timedelta(days=1)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully generated {analytics_created} analytics records for {len(employees)} employees'
            )
        )

    def generate_daily_analytics(self, employee, date, event_types, locations):
        """Generate analytics data for a specific employee and date"""
        
        # Check if analytics already exists for this employee and date
        if EmployeeAnalytics.objects.filter(employee=employee, date=date).exists():
            return None
        
        # Generate random attendance metrics
        total_events = random.randint(2, 8)  # Clock in/out events
        clock_in_count = random.randint(1, 2)
        clock_out_count = random.randint(1, 2)
        
        # Generate random hours worked (6-10 hours)
        total_hours_worked = Decimal(str(random.uniform(6.0, 10.0)))
        
        # Generate random arrival and departure times
        arrival_hour = random.randint(7, 9)  # 7 AM to 9 AM
        arrival_minute = random.randint(0, 59)
        departure_hour = random.randint(16, 18)  # 4 PM to 6 PM
        departure_minute = random.randint(0, 59)
        
        average_arrival_time = time(arrival_hour, arrival_minute)
        average_departure_time = time(departure_hour, departure_minute)
        
        # Generate location data
        locations_visited = random.sample([loc.name for loc in locations], min(3, len(locations)))
        movement_count = random.randint(2, 8)
        
        # Calculate performance metrics
        is_late_arrival = arrival_hour > 8 or (arrival_hour == 8 and arrival_minute > 30)
        is_early_departure = departure_hour < 17
        attendance_score = self.calculate_attendance_score(
            is_late_arrival, is_early_departure, total_hours_worked
        )
        
        # Determine if this is an anomaly
        is_anomaly = self.determine_anomaly(
            is_late_arrival, is_early_departure, attendance_score, movement_count
        )
        anomaly_reason = self.get_anomaly_reason(is_late_arrival, is_early_departure, attendance_score, movement_count) if is_anomaly else ""
        
        # Create analytics record
        analytics = EmployeeAnalytics.objects.create(
            employee=employee,
            date=date,
            total_events=total_events,
            clock_in_count=clock_in_count,
            clock_out_count=clock_out_count,
            total_hours_worked=total_hours_worked,
            average_arrival_time=average_arrival_time,
            average_departure_time=average_departure_time,
            locations_visited=locations_visited,
            movement_count=movement_count,
            is_late_arrival=is_late_arrival,
            is_early_departure=is_early_departure,
            attendance_score=attendance_score,
            is_anomaly=is_anomaly,
            anomaly_reason=anomaly_reason,
        )
        
        return analytics

    def calculate_attendance_score(self, is_late_arrival, is_early_departure, hours_worked):
        """Calculate attendance score based on various factors"""
        score = 100.0
        
        # Deduct points for late arrival
        if is_late_arrival:
            score -= 15
        
        # Deduct points for early departure
        if is_early_departure:
            score -= 10
        
        # Deduct points for insufficient hours
        if hours_worked < Decimal('7.5'):
            score -= (7.5 - float(hours_worked)) * 5
        
        # Bonus for good attendance
        if not is_late_arrival and not is_early_departure and hours_worked >= Decimal('8.0'):
            score += 5
        
        return max(0, min(100, score))

    def determine_anomaly(self, is_late_arrival, is_early_departure, attendance_score, movement_count):
        """Determine if this day represents anomalous behavior"""
        anomaly_flags = 0
        
        if is_late_arrival:
            anomaly_flags += 1
        
        if is_early_departure:
            anomaly_flags += 1
        
        if attendance_score < 70:
            anomaly_flags += 2
        
        if movement_count > 10:
            anomaly_flags += 1
        
        # Consider it an anomaly if there are 2 or more flags
        return anomaly_flags >= 2

    def get_anomaly_reason(self, is_late_arrival, is_early_departure, attendance_score, movement_count):
        """Generate a reason for the anomaly"""
        reasons = []
        
        if is_late_arrival:
            reasons.append("Late arrival")
        
        if is_early_departure:
            reasons.append("Early departure")
        
        if attendance_score < 70:
            reasons.append("Low attendance score")
        
        if movement_count > 10:
            reasons.append("Unusual movement pattern")
        
        return "; ".join(reasons) 