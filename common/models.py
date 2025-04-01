import uuid

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Card(models.Model):
    designation = models.TextField(null=False, unique=True)

    def __unicode__(self):
        return f"{self.designation}"

    def __str__(self):
        return f"{self.designation}"


class Employee(models.Model):
    given_name = models.TextField(null=False)
    surname = models.TextField(null=False)
    assigned_locations = models.ManyToManyField("Location")
    card_number = models.ForeignKey(Card, null=True, on_delete=models.CASCADE)

    class Meta:
        unique_together = [["given_name", "surname"]]

    def __unicode__(self):
        return f"{self.given_name} {self.surname}"

    def __str__(self):
        return f"{self.given_name} {self.surname}"

    def is_clocked_in(self):
        employee = self

        employee_events = Event.objects.all().filter(employee=employee)

        if employee_events.count() == 0:
            return False

        employee_clock_inout_events = employee_events.filter(
            Q(event_type__name="Clock In") | Q(event_type__name="Clock Out")
        )

        current_status = (
            employee_clock_inout_events.order_by("-timestamp").first().event_type.name
        )

        if current_status == "Clock In":
            return True
        else:
            return False

    def last_clockinout_time(self):
        employee = self

        employee_events = Event.objects.all().filter(employee=employee)

        if employee_events.count() == 0:
            return None

        employee_clock_inout_events = employee_events.filter(
            Q(event_type__name="Clock In") | Q(event_type__name="Clock Out")
        )

        current_status = employee_clock_inout_events.order_by("-timestamp").first()

        return current_status.timestamp


class Location(models.Model):
    name = models.TextField(null=False, unique=True)

    def __unicode__(self):
        return f"{self.name}"

    def __str__(self):
        return f"{self.name}"


class EventType(models.Model):
    name = models.TextField(null=False, unique=True)

    def __unicode__(self):
        return f"{self.name}"

    def __str__(self):
        return f"{self.name}"


class Event(models.Model):
    event_type = models.ForeignKey(EventType, null=False, on_delete=models.CASCADE)
    employee = models.ForeignKey(
        Employee, related_name="employee_events", null=False, on_delete=models.CASCADE
    )
    location = models.ForeignKey(Location, null=False, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.event_type.name} {self.employee.given_name} {self.timestamp}"

    @property
    def __unicode__(self):
        return f"{self.event_type.name} {self.employee.given_name} {self.timestamp}"
