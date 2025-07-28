from typing import Optional

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Card(models.Model):
    """Represents a physical access card."""

    designation = models.CharField(
        max_length=255,
        null=False,
        unique=True,
        help_text="Unique identifier for the card (i.e., number printed on it).",
    )

    def __str__(self):
        """Return the card's designation."""
        return f"{self.designation}"


# NOTE: Seems to be used only for "Main Security" currently; Will this be expanded in the future?
class Location(models.Model):
    """Represents a physical location where events can occur."""

    name = models.CharField(
        max_length=255,
        null=False,
        unique=True,
        help_text="Name of the location (e.g., 'Main Security', 'Repository and Conservation').",
    )

    def __str__(self):
        """Return the location's name."""
        return f"{self.name}"


class EventType(models.Model):
    """Represents the type of an event (e.g., 'Clock In', 'Clock Out', etc)."""

    name = models.CharField(
        max_length=255,
        null=False, unique=True, help_text="The name describing the event type."
    )

    def __str__(self):
        """Return the event type's name."""
        return f"{self.name}"


class Employee(models.Model):
    """Represents an employee who can be associated with events and cards."""

    given_name = models.CharField(max_length=255, null=False)
    surname = models.CharField(max_length=255, null=False)
    assigned_locations = models.ManyToManyField(
        Location,
        blank=True,
        help_text="Locations this employee is typically associated with (informational).",
    )
    card_number = models.ForeignKey(
        Card,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="The access card currently assigned to the employee.",
    )
    
    # New fields for attendance tracking
    assigned_lunch_time = models.TimeField(
        null=True, 
        blank=True, 
        help_text="Employee's assigned lunch time"
    )
    assigned_departure_time = models.TimeField(
        null=True, 
        blank=True, 
        help_text="Employee's assigned departure time"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this employee is currently active"
    )

    class Meta:
        unique_together = [["given_name", "surname"]]
        ordering = ["surname", "given_name"]
        indexes = [
            models.Index(fields=['is_active', 'surname', 'given_name']),
            models.Index(fields=['card_number', 'is_active']),
        ]

    def __str__(self):
        """Return the employee's full name."""
        return f"{self.given_name} {self.surname}"

    def _get_clock_in_out_events(self):
        """Helper method to retrieve clock in/out events efficiently."""
        # Use related_name 'employee_events' for efficiency
        return self.employee_events.filter(
            Q(event_type__name="Clock In") | Q(event_type__name="Clock Out")
        ).order_by("-timestamp")

    def is_clocked_in(self) -> bool:
        """
        Checks if the employee's last clock event was 'Clock In'.
        Returns False if there are no clock events.
        Uses caching to improve performance.
        """
        # Try to get cached status first
        try:
            from common.cache_utils import get_cached_employee_status, cache_employee_status
            cached_status = get_cached_employee_status(self.id)
            if cached_status is not None:
                return cached_status
        except ImportError:
            pass  # Fall back to non-cached version if cache utils not available
        
        # Not cached, query database
        last_clock_event = self._get_clock_in_out_events().first()

        if not last_clock_event:
            # NOTE: This handles our last known/stated bug on never clocked in individuals
            is_clocked_in = False  # No clock events means not clocked in, ever
        else:
            is_clocked_in = last_clock_event.event_type.name == "Clock In"
        
        # Cache the result
        try:
            cache_employee_status(self.id, is_clocked_in, 
                                last_clock_event.timestamp if last_clock_event else None)
        except (ImportError, NameError):
            pass  # Ignore caching errors
        
        return is_clocked_in

    @property  # Make it behave like a property in templates/serializers
    def last_clockinout_time(self) -> Optional[timezone.datetime]:
        """
        Returns the timestamp of the employee's last clock in or out event.
        Returns None if there are no clock events.
        Uses caching to improve performance.
        """
        # Try to get cached last event time first
        try:
            from common.cache_utils import get_cached_employee_last_event, cache_employee_status
            cached_time = get_cached_employee_last_event(self.id)
            if cached_time is not None:
                return cached_time
        except ImportError:
            pass  # Fall back to non-cached version if cache utils not available
        
        # Not cached, query database
        last_clock_event = self._get_clock_in_out_events().first()

        if not last_clock_event:
            last_time = None  # No clock events
        else:
            last_time = last_clock_event.timestamp
        
        # Cache the result along with clock status
        try:
            is_clocked_in = last_clock_event.event_type.name == "Clock In" if last_clock_event else False
            cache_employee_status(self.id, is_clocked_in, last_time)
        except (ImportError, NameError):
            pass  # Ignore caching errors

        return last_time

    def get_attendance_records(self, start_date=None, end_date=None):
        """Get attendance records for this employee within a date range"""
        records = self.attendance_records.all()
        if start_date:
            records = records.filter(date__gte=start_date)
        if end_date:
            records = records.filter(date__lte=end_date)
        return records.order_by('date')

    def get_problematic_days(self, start_date=None, end_date=None):
        """Get problematic attendance days for this employee"""
        records = self.get_attendance_records(start_date, end_date)
        return [record for record in records if record.is_problematic_day()]

    def get_attendance_percentage(self, start_date=None, end_date=None):
        """Calculate attendance percentage for this employee"""
        records = self.get_attendance_records(start_date, end_date)
        if not records:
            return 0.0
        
        problematic_days = len(self.get_problematic_days(start_date, end_date))
        total_days = len(records)
        
        if total_days == 0:
            return 0.0
        
        return ((total_days - problematic_days) / total_days) * 100


class AttendanceRecord(models.Model):
    """Comprehensive attendance record replacing Excel data"""
    
    ATTENDANCE_CHOICES = [
        ('YES', 'Yes'),
        ('NO', 'No'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late'),
        ('APPOINTMENT', 'Appointment'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    
    # Lunch tracking
    lunch_time = models.TimeField(null=True, blank=True, help_text="Time employee took lunch")
    left_lunch_on_time = models.CharField(
        max_length=11, 
        choices=ATTENDANCE_CHOICES, 
        null=True, 
        blank=True,
        help_text="Did employee leave for lunch at assigned time?"
    )
    returned_on_time_after_lunch = models.CharField(
        max_length=11, 
        choices=ATTENDANCE_CHOICES, 
        null=True, 
        blank=True,
        help_text="Did employee return to workstation on time after lunch?"
    )
    returned_after_lunch = models.CharField(
        max_length=11, 
        choices=ATTENDANCE_CHOICES, 
        null=True, 
        blank=True,
        help_text="Did employee return after lunch?"
    )
    
    # Stand-up meeting
    standup_attendance = models.CharField(
        max_length=11, 
        choices=ATTENDANCE_CHOICES, 
        null=True, 
        blank=True,
        help_text="Did employee attend stand-up meeting?"
    )
    
    # Departure - will be pulled from clock-in system
    # departure_time = models.TimeField(null=True, blank=True, help_text="Time employee left work")
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, help_text="Additional notes or comments")
    
    # Progressive entry tracking
    STATUS_CHOICES = [
        ('DRAFT', 'Draft - In Progress'),
        ('PARTIAL', 'Partial - Some data entered'),
        ('COMPLETE', 'Complete - All data entered'),
        ('REVIEWED', 'Reviewed - Supervisor approved'),
    ]
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='DRAFT',
        help_text="Current status of this attendance record"
    )
    last_updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='updated_attendance_records',
        help_text="Last user who updated this record"
    )

    class Meta:
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee__surname', 'employee__given_name']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['employee', 'date']),
            models.Index(fields=['status', 'date']),
            models.Index(fields=['employee', 'status']),
        ]

    def __str__(self):
        """Return a description of the attendance record."""
        return f"{self.employee} - {self.date}"

    def is_problematic_day(self):
        """Check if this day had problematic attendance patterns (excluding absences)"""
        # Only count actual attendance violations, not absences
        # This logic is based on the Garbage/analyze_attendance.py valuemap
        problematic_values = ['NO', 'LATE']  # Removed 'ABSENT' from problematic values
        
        issues = 0
        if self.standup_attendance in problematic_values:
            issues += 1
        if self.left_lunch_on_time in problematic_values:
            issues += 1
        if self.returned_on_time_after_lunch in problematic_values:
            issues += 1
        if self.returned_after_lunch in problematic_values:
            issues += 1
        
        return issues >= 2  # Multiple issues on same day

    @property
    def total_issues(self):
        """Count total attendance issues for this day (excluding absences)"""
        # Only count actual attendance violations, not absences
        # This logic is based on the Garbage/analyze_attendance.py valuemap
        problematic_values = ['NO', 'LATE']  # Removed 'ABSENT' from problematic values
        issues = 0
        
        for field in ['standup_attendance', 'left_lunch_on_time', 
                     'returned_on_time_after_lunch', 'returned_after_lunch']:
            if getattr(self, field) in problematic_values:
                issues += 1
        
        return issues

    @property
    def arrival_time(self):
        """Get the arrival time from clock-in events (in local timezone)"""
        from datetime import datetime, time
        
        # Use timezone-aware range queries to handle timezone boundaries
        # Create range for the entire day in local timezone
        start_of_day_local = datetime.combine(self.date, time.min)
        end_of_day_local = datetime.combine(self.date, time.max)
        
        # Convert to UTC for database query
        start_of_day_utc = timezone.make_aware(start_of_day_local)
        end_of_day_utc = timezone.make_aware(end_of_day_local)
        
        # Query for events within the UTC range
        clock_in_events = Event.objects.filter(
            employee=self.employee,
            event_type__name='Clock In',
            timestamp__gte=start_of_day_utc,
            timestamp__lte=end_of_day_utc
        ).order_by('timestamp')
        
        if clock_in_events.exists():
            # Get the earliest clock-in event (first arrival of the day)
            earliest_event = clock_in_events.first()
            local_timestamp = timezone.localtime(earliest_event.timestamp)
            return local_timestamp.time()
        return None

    @property
    def arrival_datetime(self):
        """Get the arrival datetime from clock-in events"""
        from datetime import datetime, time
        
        # Use timezone-aware range queries to handle timezone boundaries
        # Create range for the entire day in local timezone
        start_of_day_local = datetime.combine(self.date, time.min)
        end_of_day_local = datetime.combine(self.date, time.max)
        
        # Convert to UTC for database query
        start_of_day_utc = timezone.make_aware(start_of_day_local)
        end_of_day_utc = timezone.make_aware(end_of_day_local)
        
        # Query for events within the UTC range
        clock_in_events = Event.objects.filter(
            employee=self.employee,
            event_type__name='Clock In',
            timestamp__gte=start_of_day_utc,
            timestamp__lte=end_of_day_utc
        ).order_by('timestamp')
        
        if clock_in_events.exists():
            # Get the earliest clock-in event (first arrival of the day)
            earliest_event = clock_in_events.first()
            return earliest_event.timestamp
        return None

    @property
    def departure_time(self):
        """Get the departure time from clock-out events (in local timezone)"""
        from datetime import datetime, time
        
        # Use timezone-aware range queries to handle timezone boundaries
        # Create range for the entire day in local timezone
        start_of_day_local = datetime.combine(self.date, time.min)
        end_of_day_local = datetime.combine(self.date, time.max)
        
        # Convert to UTC for database query
        start_of_day_utc = timezone.make_aware(start_of_day_local)
        end_of_day_utc = timezone.make_aware(end_of_day_local)
        
        # Query for events within the UTC range
        clock_out_events = Event.objects.filter(
            employee=self.employee,
            event_type__name='Clock Out',
            timestamp__gte=start_of_day_utc,
            timestamp__lte=end_of_day_utc
        ).order_by('timestamp')
        
        if clock_out_events.exists():
            # Get the most recent clock-out event
            latest_event = clock_out_events.last()
            local_timestamp = timezone.localtime(latest_event.timestamp)
            return local_timestamp.time()
        return None

    @property
    def worked_hours(self):
        """Calculate total hours worked for this day"""
        from datetime import datetime
        
        if not self.arrival_datetime or not self.departure_time:
            return None
        
        # Combine date with departure time
        departure_datetime = timezone.make_aware(
            datetime.combine(self.date, self.departure_time)
        )
        
        # Calculate duration
        duration = departure_datetime - self.arrival_datetime
        return duration.total_seconds() / 3600  # Convert to hours

    @property
    def is_late_arrival(self):
        """Check if employee arrived late (after 9:00 AM)"""
        if not self.arrival_time:
            return False
        
        from datetime import time
        return self.arrival_time > time(9, 0)

    @property
    def is_early_departure(self):
        """Check if employee left early (before 5:00 PM)"""
        if not self.departure_time:
            return False
        
        from datetime import time
        return self.departure_time < time(17, 0)

    @property
    def completion_percentage(self):
        """Calculate completion percentage of this attendance record"""
        fields_to_check = [
            'standup_attendance', 'left_lunch_on_time', 
            'returned_on_time_after_lunch', 'returned_after_lunch'
        ]
        
        completed_fields = 0
        for field in fields_to_check:
            if getattr(self, field):
                completed_fields += 1
        
        return (completed_fields / len(fields_to_check)) * 100

    def auto_update_status(self):
        """Automatically update status based on completion"""
        completion = self.completion_percentage
        
        new_status = 'DRAFT'
        if completion == 0:
            new_status = 'DRAFT'
        elif completion < 100:
            new_status = 'PARTIAL'
        else:
            new_status = 'COMPLETE'
        
        # Use update to avoid recursion
        if self.status != new_status:
            AttendanceRecord.objects.filter(id=self.id).update(status=new_status)
            self.status = new_status

    def save(self, *args, **kwargs):
        """Override save to auto-update status"""
        super().save(*args, **kwargs)
        self.auto_update_status()


class Event(models.Model):
    """Represents an event recorded in the system (e.g., clock in/out, access)."""

    event_type = models.ForeignKey(EventType, null=False, on_delete=models.CASCADE)
    employee = models.ForeignKey(
        Employee,
        related_name="employee_events",  # Important for reverse lookups (employee.employee_events.all())
        null=False,
        on_delete=models.CASCADE,
    )
    location = models.ForeignKey(Location, null=False, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(
        default=timezone.now, help_text="When the event occurred."
    )
    # Track which logged-in user created the event (e.g., security guard)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="The system user who recorded this event, if applicable.",
    )

    class Meta:
        ordering = ["-timestamp"]  # Show newest events first by default
        indexes = [
            models.Index(fields=['employee', '-timestamp'], name='idx_emp_events_emp_time'),
            models.Index(fields=['event_type', 'timestamp'], name='idx_event_type_time'),
            models.Index(fields=['location', 'timestamp'], name='idx_location_time'),
        ]

    def __str__(self):
        """Return a description of the event."""
        return f"{self.event_type.name} by {self.employee} at {timezone.localtime(self.timestamp).strftime('%d-%b-%Y %I:%M %p')}"

    def save(self, *args, **kwargs):
        """Override save to invalidate employee cache when events are created."""
        # Check if this is a new clock event
        is_new_clock_in = (
            self.pk is None and  # New record
            self.event_type.name == "Clock In"  # Clock In event
        )
        is_new_clock_out = (
            self.pk is None and  # New record
            self.event_type.name == "Clock Out"  # Clock Out event
        )
        
        super().save(*args, **kwargs)
        
        # If this is a new clock-in event, automatically create attendance record
        if is_new_clock_in:
            self._create_attendance_record()
        elif is_new_clock_out:
            self._update_attendance_record()
        
        # Invalidate cache for this employee when a new event is created
        try:
            from common.cache_utils import invalidate_employee_cache, invalidate_main_security_cache
            invalidate_employee_cache(self.employee_id)
            invalidate_main_security_cache()  # Also invalidate main security page cache
        except ImportError:
            # Fallback: clear Django's default cache for this employee
            from django.core.cache import cache
            cache.delete(f"employee_status_{self.employee_id}")
            cache.delete(f"employee_last_event_{self.employee_id}")
            pass  # Ignore if cache utils not available
    
    def _create_attendance_record(self):
        """Automatically create attendance record when employee clocks in"""
        from django.contrib.auth.models import User
        
        # Get the local date of the clock-in event (not UTC date)
        event_local_time = timezone.localtime(self.timestamp)
        event_date = event_local_time.date()
        
        # Check if attendance record already exists for this employee and date
        existing_record = AttendanceRecord.objects.filter(
            employee=self.employee,
            date=event_date
        ).first()
        
        if existing_record:
            # Update existing record with arrival time (in local timezone)
            local_time = event_local_time.time()
            existing_record.notes = f"Updated arrival time: {local_time}"
            existing_record.save()
            return
        
        # Create new attendance record
        admin_user = User.objects.filter(is_superuser=True).first()
        
        # Get local time for the note
        local_time = event_local_time.time()
        
        attendance_record = AttendanceRecord.objects.create(
            employee=self.employee,
            date=event_date,
            lunch_time=self.employee.assigned_lunch_time,
            created_by=admin_user,
            status='DRAFT',
            notes=f"Auto-created from clock-in at {local_time}"
        )
    
    def _update_attendance_record(self):
        """Update attendance record when employee clocks out"""
        # Get the local date of the clock-out event (not UTC date)
        event_local_time = timezone.localtime(self.timestamp)
        event_date = event_local_time.date()
        
        # Find existing attendance record for this employee and date
        existing_record = AttendanceRecord.objects.filter(
            employee=self.employee,
            date=event_date
        ).first()
        
        if existing_record:
            # Update the record with departure time info (in local timezone)
            current_notes = existing_record.notes or ""
            local_time = event_local_time.time()
            departure_note = f"Clock-out at {local_time}"
            
            if current_notes:
                updated_notes = f"{current_notes}; {departure_note}"
            else:
                updated_notes = departure_note
            
            existing_record.notes = updated_notes
            existing_record.save()


# NOTE:
# See: https://django.readthedocs.io/en/1.11.x/ref/unicode.html#choosing-between-str-and-unicode
# See above as to why I switched from __unicode__ to __str__
