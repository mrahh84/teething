from typing import Optional

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Card(models.Model):
    """Represents a physical access card."""

    designation = models.TextField(
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

    name = models.TextField(
        null=False,
        unique=True,
        help_text="Name of the location (e.g., 'Main Security', 'Repository and Conservation').",
    )

    def __str__(self):
        """Return the location's name."""
        return f"{self.name}"


class EventType(models.Model):
    """Represents the type of an event (e.g., 'Clock In', 'Clock Out', etc)."""

    name = models.TextField(
        null=False, unique=True, help_text="The name describing the event type."
    )

    def __str__(self):
        """Return the event type's name."""
        return f"{self.name}"


class Employee(models.Model):
    """Represents an employee who can be associated with events and cards."""

    given_name = models.TextField(null=False)
    surname = models.TextField(null=False)
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

    # NOTE:
    # Consider changing assigned_locations to required if applicable: null=False, blank=False
    # Consider making card_number to required: null=False
    # Consider including a unique field instead of just depending on the combination of given_name and surname

    class Meta:
        unique_together = [["given_name", "surname"]]
        ordering = ["surname", "given_name"]

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
        """
        last_clock_event = self._get_clock_in_out_events().first()

        if not last_clock_event:
            # NOTE: This handles our last known/stated bug on never clocked in individuals
            return False  # No clock events means not clocked in, ever

        return last_clock_event.event_type.name == "Clock In"

    @property  # Make it behave like a property in templates/serializers
    def last_clockinout_time(self) -> Optional[timezone.datetime]:
        """
        Returns the timestamp of the employee's last clock in or out event.
        Returns None if there are no clock events.
        """
        last_clock_event = self._get_clock_in_out_events().first()

        if not last_clock_event:
            return None  # No clock events

        return last_clock_event.timestamp


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

    def __str__(self):
        """Return a description of the event."""
        return f"{self.event_type.name} by {self.employee} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


# NOTE:
# See: https://django.readthedocs.io/en/1.11.x/ref/unicode.html#choosing-between-str-and-unicode
# See above as to why I switched from __unicode__ to __str__
