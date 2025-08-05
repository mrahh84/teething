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

    LOCATION_TYPE_CHOICES = [
        ('SECURITY', 'Security Checkpoint'),
        ('WORKSTATION', 'Workstation Area'),
        ('LUNCH', 'Lunch Area'),
        ('MEETING', 'Meeting Room'),
        ('STORAGE', 'Storage Area'),
        ('TASK', 'Task Assignment Area'),
        ('ROOM', 'Physical Room'),
    ]

    name = models.CharField(
        max_length=255,
        null=False,
        unique=True,
        help_text="Name of the location (e.g., 'Main Security', 'Repository and Conservation').",
    )
    
    # Enhanced location tracking fields
    location_type = models.CharField(
        max_length=20,
        choices=LOCATION_TYPE_CHOICES,
        default='WORKSTATION',
        help_text="Type of location"
    )
    
    capacity = models.IntegerField(
        default=0,
        help_text="Maximum number of employees that can be at this location"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this location is currently active"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Additional description of the location"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['location_type', 'is_active']),
            models.Index(fields=['is_active', 'name']),
        ]

    def __str__(self):
        """Return the location's name."""
        return f"{self.name} ({self.get_location_type_display()})"
    
    @property
    def current_occupancy(self):
        """Get current number of employees at this location."""
        from django.utils import timezone
        today = timezone.now().date()
        return Event.objects.filter(
            location=self,
            timestamp__date=today,
            event_type__name__in=['Clock In', 'Task Assignment']
        ).values('employee').distinct().count()
    
    @property
    def utilization_rate(self):
        """Calculate utilization rate as percentage."""
        if self.capacity == 0:
            return 0
        return (self.current_occupancy / self.capacity) * 100


class EventType(models.Model):
    """Represents the type of an event (e.g., 'Clock In', 'Clock Out', etc)."""

    name = models.CharField(
        max_length=255,
        null=False, unique=True, help_text="The name describing the event type."
    )

    def __str__(self):
        """Return the event type's name."""
        return f"{self.name}"


class Department(models.Model):
    """Department classification for employees"""
    
    name = models.CharField(max_length=255, unique=True, help_text="Department name")
    code = models.CharField(max_length=10, unique=True, help_text="Short department code")
    description = models.TextField(blank=True, help_text="Department description")
    is_active = models.BooleanField(default=True, help_text="Whether this department is active")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


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
    
    # Department classification
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Employee's department",
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
        return self.employee_events.filter(
            event_type__name__in=["Clock In", "Clock Out"]
        ).order_by("-timestamp")

    def is_clocked_in(self) -> bool:
        """Check if the employee is currently clocked in."""
        latest_event = self._get_clock_in_out_events().first()
        if not latest_event:
            return False
        return latest_event.event_type.name == "Clock In"

    @property  # Make it behave like a property in templates/serializers
    def last_clockinout_time(self) -> Optional[timezone.datetime]:
        """Get the timestamp of the employee's last clock in/out event."""
        latest_event = self._get_clock_in_out_events().first()
        return latest_event.timestamp if latest_event else None

    def get_attendance_records(self, start_date=None, end_date=None):
        """Get attendance records for this employee within a date range."""
        records = self.attendance_records.all()
        if start_date:
            records = records.filter(date__gte=start_date)
        if end_date:
            records = records.filter(date__lte=end_date)
        return records.order_by('-date')

    def get_problematic_days(self, start_date=None, end_date=None):
        """Get problematic attendance days for this employee."""
        records = self.get_attendance_records(start_date, end_date)
        return [record for record in records if record.is_problematic_day()]

    def get_attendance_percentage(self, start_date=None, end_date=None):
        """Calculate attendance percentage for this employee."""
        records = self.get_attendance_records(start_date, end_date)
        if not records:
            return 0.0
        
        total_days = records.count()
        non_problematic_days = sum(1 for record in records if not record.is_problematic_day())
        return (non_problematic_days / total_days) * 100 if total_days > 0 else 0.0


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
        help_text="User who last updated this record"
    )

    class Meta:
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee__surname', 'employee__given_name']
        indexes = [
            models.Index(fields=['employee', 'date']),
            models.Index(fields=['date', 'status']),
            models.Index(fields=['created_by', 'created_at']),
        ]

    def __str__(self):
        """Return string representation."""
        return f"{self.employee} - {self.date} ({self.status})"

    def is_problematic_day(self):
        """Check if this day has multiple attendance issues."""
        problematic_values = ['NO', 'LATE']
        issues = 0
        
        # Check lunch-related issues
        if self.left_lunch_on_time in problematic_values:
            issues += 1
        if self.returned_on_time_after_lunch in problematic_values:
            issues += 1
        if self.returned_after_lunch in problematic_values:
            issues += 1
        
        # Check stand-up meeting attendance
        if self.standup_attendance in problematic_values:
            issues += 1
        
        # Day is problematic if there are 2 or more issues
        return issues >= 2

    @property
    def total_issues(self):
        """Count total issues for this attendance record."""
        problematic_values = ['NO', 'LATE']
        issues = 0
        
        # Check lunch-related issues
        if self.left_lunch_on_time in problematic_values:
            issues += 1
        if self.returned_on_time_after_lunch in problematic_values:
            issues += 1
        if self.returned_after_lunch in problematic_values:
            issues += 1
        
        # Check stand-up meeting attendance
        if self.standup_attendance in problematic_values:
            issues += 1
        
        return issues

    @property
    def arrival_time(self):
        """Get employee's arrival time from clock-in events."""
        clock_in_event = self.employee.employee_events.filter(
            event_type__name="Clock In",
            timestamp__date=self.date
        ).order_by('timestamp').first()
        
        if clock_in_event:
            # Convert UTC timestamp to local timezone before extracting time
            local_timestamp = timezone.localtime(clock_in_event.timestamp)
            return local_timestamp.time()
        return None

    @property
    def arrival_datetime(self):
        """Get employee's arrival datetime from clock-in events."""
        clock_in_event = self.employee.employee_events.filter(
            event_type__name="Clock In",
            timestamp__date=self.date
        ).order_by('timestamp').first()
        
        return clock_in_event.timestamp if clock_in_event else None

    @property
    def departure_time(self):
        """Get employee's departure time from clock-out events."""
        clock_out_event = self.employee.employee_events.filter(
            event_type__name="Clock Out",
            timestamp__date=self.date
        ).order_by('timestamp').last()
        
        if clock_out_event:
            # Convert UTC timestamp to local timezone before extracting time
            local_timestamp = timezone.localtime(clock_out_event.timestamp)
            return local_timestamp.time()
        return None

    @property
    def worked_hours(self):
        """Calculate total hours worked for this day."""
        arrival = self.arrival_datetime
        departure = self.departure_time
        
        if arrival and departure:
            # Convert departure time to datetime for calculation
            departure_datetime = timezone.make_aware(
                timezone.datetime.combine(self.date, departure)
            )
            duration = departure_datetime - arrival
            return duration.total_seconds() / 3600  # Convert to hours
        return 0

    @property
    def is_late_arrival(self):
        """Check if employee arrived late (after 9:00 AM)."""
        arrival_time = self.arrival_time
        if arrival_time:
            return arrival_time > timezone.datetime.strptime('09:00', '%H:%M').time()
        return False

    @property
    def is_early_departure(self):
        """Check if employee left early (before 5:00 PM)."""
        departure_time = self.departure_time
        if departure_time:
            return departure_time < timezone.datetime.strptime('17:00', '%H:%M').time()
        return False

    @property
    def completion_percentage(self):
        """Calculate completion percentage of this attendance record."""
        total_fields = 4  # lunch_time, left_lunch_on_time, returned_after_lunch, standup_attendance
        filled_fields = 0
        
        if self.lunch_time:
            filled_fields += 1
        if self.left_lunch_on_time:
            filled_fields += 1
        if self.returned_after_lunch:
            filled_fields += 1
        if self.standup_attendance:
            filled_fields += 1
        
        return (filled_fields / total_fields) * 100 if total_fields > 0 else 0

    def auto_update_status(self):
        """Automatically update status based on completion."""
        completion = self.completion_percentage
        
        if completion == 0:
            self.status = 'DRAFT'
        elif completion < 100:
            self.status = 'PARTIAL'
        else:
            self.status = 'COMPLETE'

    def save(self, *args, **kwargs):
        """Override save to auto-update status."""
        # Update status before saving
        self.auto_update_status()
        super().save(*args, **kwargs)


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
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="User who recorded this event.",
    )

    class Meta:
        ordering = ["-timestamp"]  # Show newest events first by default
        indexes = [
            models.Index(fields=['employee', 'timestamp']),
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['location', 'timestamp']),
            models.Index(fields=['created_by', 'timestamp']),
        ]

    def __str__(self):
        """Return string representation."""
        return f"{self.employee} - {self.event_type} at {self.location} ({self.timestamp})"

    def save(self, *args, **kwargs):
        """Override save to create/update attendance records."""
        # Check if this is a new event
        is_new = self.pk is None
        
        # Save the event first
        super().save(*args, **kwargs)
        
        # Only process clock in/out events for attendance records
        if self.event_type.name in ["Clock In", "Clock Out"]:
            if is_new:
                self._create_attendance_record()
            else:
                self._update_attendance_record()

    def _create_attendance_record(self):
        """Create a new attendance record for this event's date."""
        # Check if attendance record already exists for this employee and date
        attendance_record, created = AttendanceRecord.objects.get_or_create(
            employee=self.employee,
            date=self.timestamp.date(),
            defaults={
                'created_by': self.created_by,
                'status': 'DRAFT'
            }
        )
        
        if created:
            # Log the creation
            print(f"Created attendance record for {self.employee} on {self.timestamp.date()}")
        else:
            # Update the existing record
            attendance_record.last_updated_by = self.created_by
            attendance_record.save()

    def _update_attendance_record(self):
        """Update existing attendance record for this event's date."""
        try:
            attendance_record = AttendanceRecord.objects.get(
                employee=self.employee,
                date=self.timestamp.date()
            )
            attendance_record.last_updated_by = self.created_by
            attendance_record.save()
        except AttendanceRecord.DoesNotExist:
            # Create if doesn't exist
            self._create_attendance_record()


class UserRole(models.Model):
    """User roles for access control"""
    
    ROLE_CHOICES = [
        ('security', 'Security'),
        ('attendance', 'Attendance Management'),
        ('reporting', 'Reporting'),
        ('admin', 'Administrator'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Role"
        verbose_name_plural = "User Roles"
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


# Add role methods to User model
def User_get_role(self):
    """Get user's role"""
    try:
        return self.userrole.role
    except UserRole.DoesNotExist:
        return None

def User_has_role(self, role):
    """Check if user has specific role"""
    return self.get_role() == role

def User_has_any_role(self, roles):
    """Check if user has any of the specified roles"""
    user_role = self.get_role()
    return user_role in roles if user_role else False

# Add methods to User model
User.get_role = User_get_role
User.has_role = User_has_role
User.has_any_role = User_has_any_role


class AnalyticsCache(models.Model):
    """Cache for analytics data to improve report performance"""
    
    cache_key = models.CharField(max_length=255, unique=True, help_text="Unique identifier for cached data")
    data = models.JSONField(help_text="Cached analytics data")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(help_text="When this cache entry expires")
    cache_type = models.CharField(
        max_length=50, 
        choices=[
            ('daily_summary', 'Daily Summary'),
            ('employee_analytics', 'Employee Analytics'),
            ('department_analytics', 'Department Analytics'),
            ('attendance_heatmap', 'Attendance Heatmap'),
            ('movement_patterns', 'Movement Patterns'),
            ('anomaly_detection', 'Anomaly Detection'),
        ],
        help_text="Type of cached analytics data"
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['cache_type', 'expires_at']),
            models.Index(fields=['cache_key']),
        ]
    
    def __str__(self):
        return f"{self.cache_type}: {self.cache_key}"
    
    def is_expired(self):
        """Check if cache entry has expired"""
        return timezone.now() > self.expires_at


class ReportConfiguration(models.Model):
    """User-specific report configurations and preferences"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='report_configurations')
    report_type = models.CharField(
        max_length=50,
        choices=[
            ('daily_dashboard', 'Daily Dashboard'),
            ('employee_history', 'Employee History'),
            ('period_summary', 'Period Summary'),
            ('comprehensive_attendance', 'Comprehensive Attendance'),
            ('real_time_analytics', 'Real-Time Analytics'),
            ('department_performance', 'Department Performance'),
            ('compliance_audit', 'Compliance & Audit'),
        ],
        help_text="Type of report"
    )
    configuration = models.JSONField(
        default=dict,
        help_text="User-specific configuration for this report type"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'report_type']
        indexes = [
            models.Index(fields=['user', 'report_type']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.report_type}"


class EmployeeAnalytics(models.Model):
    """Aggregated analytics data for employees"""
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='analytics')
    date = models.DateField(help_text="Date of analytics data")
    
    # Attendance metrics
    total_events = models.IntegerField(default=0, help_text="Total events for the day")
    clock_in_count = models.IntegerField(default=0, help_text="Number of clock-in events")
    clock_out_count = models.IntegerField(default=0, help_text="Number of clock-out events")
    total_hours_worked = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0, 
        help_text="Total hours worked"
    )
    average_arrival_time = models.TimeField(null=True, blank=True, help_text="Average arrival time")
    average_departure_time = models.TimeField(null=True, blank=True, help_text="Average departure time")
    
    # Location metrics
    locations_visited = models.JSONField(default=list, help_text="List of locations visited")
    movement_count = models.IntegerField(default=0, help_text="Number of location movements")
    
    # Performance metrics
    is_late_arrival = models.BooleanField(default=False, help_text="Was arrival late?")
    is_early_departure = models.BooleanField(default=False, help_text="Was departure early?")
    attendance_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0, 
        help_text="Attendance performance score (0-100)"
    )
    
    # Anomaly detection
    is_anomaly = models.BooleanField(default=False, help_text="Flagged as anomalous behavior")
    anomaly_reason = models.TextField(blank=True, help_text="Reason for anomaly flag")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['employee', 'date']
        indexes = [
            models.Index(fields=['employee', 'date']),
            models.Index(fields=['date', 'is_anomaly']),
            models.Index(fields=['employee', 'is_late_arrival']),
        ]
    
    def __str__(self):
        return f"{self.employee} - {self.date}"


class DepartmentAnalytics(models.Model):
    """Aggregated analytics data for departments"""
    
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='analytics')
    date = models.DateField(help_text="Date of analytics data")
    
    # Attendance metrics
    total_employees = models.IntegerField(default=0, help_text="Total employees in department")
    present_employees = models.IntegerField(default=0, help_text="Employees present today")
    absent_employees = models.IntegerField(default=0, help_text="Employees absent today")
    late_employees = models.IntegerField(default=0, help_text="Employees who arrived late")
    
    # Performance metrics
    average_attendance_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0, 
        help_text="Average attendance rate percentage"
    )
    average_hours_worked = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0, 
        help_text="Average hours worked per employee"
    )
    total_hours_worked = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=0, 
        help_text="Total hours worked by department"
    )
    
    # Location utilization
    location_utilization = models.JSONField(default=dict, help_text="Location utilization data")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['department', 'date']
        indexes = [
            models.Index(fields=['department', 'date']),
            models.Index(fields=['date', 'average_attendance_rate']),
        ]
    
    def __str__(self):
        return f"{self.department} - {self.date}"


class SystemPerformance(models.Model):
    """System performance metrics for monitoring"""
    
    date = models.DateField(help_text="Date of performance data")
    timestamp = models.DateTimeField(auto_now_add=True, help_text="When this record was created")
    
    # System metrics
    total_events_processed = models.IntegerField(default=0, help_text="Total events processed today")
    active_users = models.IntegerField(default=0, help_text="Number of active users today")
    api_requests = models.IntegerField(default=0, help_text="Number of API requests today")
    average_response_time = models.DecimalField(
        max_digits=6, 
        decimal_places=3, 
        default=0, 
        help_text="Average API response time in seconds"
    )
    
    # Database metrics
    database_queries = models.IntegerField(default=0, help_text="Number of database queries today")
    slow_queries = models.IntegerField(default=0, help_text="Number of slow queries (>1s)")
    
    # Cache metrics
    cache_hit_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0, 
        help_text="Cache hit rate percentage"
    )
    cache_misses = models.IntegerField(default=0, help_text="Number of cache misses")
    
    class Meta:
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"System Performance - {self.date}"


class TaskAssignment(models.Model):
    """Represents task assignments for employees at specific locations"""
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='task_assignments')
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='task_assignments')
    task_type = models.CharField(max_length=100, help_text="Type of task (e.g., Goobi, OCR4All, Transkribus)")
    assigned_date = models.DateField(help_text="Date of assignment")
    start_time = models.TimeField(null=True, blank=True, help_text="Scheduled start time")
    end_time = models.TimeField(null=True, blank=True, help_text="Scheduled end time")
    is_completed = models.BooleanField(default=False, help_text="Whether the task is completed")
    notes = models.TextField(blank=True, help_text="Additional notes about the assignment")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['employee', 'location', 'assigned_date']
        ordering = ['-assigned_date', 'employee__surname', 'employee__given_name']
        indexes = [
            models.Index(fields=['employee', 'assigned_date']),
            models.Index(fields=['location', 'assigned_date']),
            models.Index(fields=['task_type', 'assigned_date']),
            models.Index(fields=['is_completed', 'assigned_date']),
        ]

    def __str__(self):
        return f"{self.employee} - {self.task_type} at {self.location} ({self.assigned_date})"


class LocationMovement(models.Model):
    """Tracks employee movements between locations"""
    
    MOVEMENT_TYPE_CHOICES = [
        ('TASK_ASSIGNMENT', 'Task Assignment'),
        ('BREAK', 'Break Time'),
        ('LUNCH', 'Lunch Break'),
        ('MEETING', 'Meeting'),
        ('SECURITY_CHECK', 'Security Check'),
        ('CLOCK_IN', 'Clock In'),
        ('CLOCK_OUT', 'Clock Out'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='location_movements')
    from_location = models.ForeignKey(
        Location, 
        on_delete=models.CASCADE, 
        related_name='departures',
        null=True,
        blank=True,
        help_text="Location employee moved from (null for initial entry)"
    )
    to_location = models.ForeignKey(
        Location, 
        on_delete=models.CASCADE, 
        related_name='arrivals',
        help_text="Location employee moved to"
    )
    timestamp = models.DateTimeField(auto_now_add=True, help_text="When the movement occurred")
    movement_type = models.CharField(
        max_length=20,
        choices=MOVEMENT_TYPE_CHOICES,
        default='TASK_ASSIGNMENT',
        help_text="Type of movement"
    )
    duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Duration at previous location in minutes"
    )
    notes = models.TextField(blank=True, help_text="Additional notes about the movement")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['employee', 'timestamp']),
            models.Index(fields=['from_location', 'timestamp']),
            models.Index(fields=['to_location', 'timestamp']),
            models.Index(fields=['movement_type', 'timestamp']),
        ]

    def __str__(self):
        if self.from_location:
            return f"{self.employee}: {self.from_location} → {self.to_location} ({self.timestamp})"
        else:
            return f"{self.employee}: → {self.to_location} ({self.timestamp})"


class LocationAnalytics(models.Model):
    """Aggregated analytics data for locations"""
    
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='analytics')
    date = models.DateField(help_text="Date of analytics data")
    
    # Occupancy metrics
    current_occupancy = models.IntegerField(default=0, help_text="Current number of employees at location")
    peak_occupancy = models.IntegerField(default=0, help_text="Peak occupancy during the day")
    average_occupancy = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0, 
        help_text="Average occupancy throughout the day"
    )
    utilization_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0, 
        help_text="Utilization rate as percentage"
    )
    
    # Movement metrics
    total_movements = models.IntegerField(default=0, help_text="Total movements in/out of location")
    arrivals = models.IntegerField(default=0, help_text="Number of arrivals")
    departures = models.IntegerField(default=0, help_text="Number of departures")
    
    # Task metrics
    active_tasks = models.IntegerField(default=0, help_text="Number of active tasks")
    completed_tasks = models.IntegerField(default=0, help_text="Number of completed tasks")
    
    # Performance metrics
    average_stay_duration = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        default=0, 
        help_text="Average duration employees stay at location (minutes)"
    )
    
    # Peak hours analysis
    peak_hours = models.JSONField(default=dict, help_text="Peak usage hours and occupancy")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['location', 'date']
        indexes = [
            models.Index(fields=['location', 'date']),
            models.Index(fields=['date', 'utilization_rate']),
            models.Index(fields=['location', 'utilization_rate']),
        ]

    def __str__(self):
        return f"{self.location} - {self.date} (Utilization: {self.utilization_rate}%)"
