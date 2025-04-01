import time

import pandas as pd
from django.db.models import Q
from django.shortcuts import redirect, render
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.schemas.openapi import AutoSchema

from .models import *
from .serializers import *


class SingleEventView(generics.RetrieveUpdateDestroyAPIView):
    """
    The lookup field for sources is the pk (id)
    """

    serializer_class = SingleEventSerializer
    queryset = Event.objects.all()
    lookup_field = "id"


class SingleLocationView(generics.RetrieveUpdateDestroyAPIView):
    """
    The lookup field for sources is the pk (id)
    """

    serializer_class = LocationSerializer
    queryset = Location.objects.all()
    lookup_field = "id"


class SingleEmployeeView(generics.RetrieveUpdateDestroyAPIView):
    """
    The lookup field for sources is the pk (id)
    """

    serializer_class = EmployeeSerializer
    queryset = Employee.objects.all()
    lookup_field = "id"


class ListEventsView(generics.ListAPIView):
    serializer_class = EventSerializer
    queryset = Event.objects.all()


@extend_schema(exclude=True)
def main_security(request):
    if request.user.is_authenticated:
        employees = Employee.objects.all()
        employees = employees.order_by("surname", "given_name")

        return render(request, "main_security.html", {"employees": employees})

    else:
        return HttpResponseForbidden("Forbidden")


@extend_schema(exclude=True)
def main_security_clocked_in_status_flip(request, id):
    if request.user.is_authenticated:
        employee = Employee.objects.get(id=id)

        employee_events = employee.employee_events.all()

        employee_clock_inout_events = employee_events.filter(
            Q(event_type__name="Clock In") | Q(event_type__name="Clock Out")
        )

        statuses = employee_clock_inout_events.order_by("-timestamp")
        # for s in statuses:
        # 	print(s.event_type,s.timestamp)

        current_status = statuses.first()

        if time.time() - current_status.timestamp.timestamp() > 5:
            if current_status is None:
                newstatus = "Clock In"
                response_label = "Clocked In"

            else:
                current_status = current_status.event_type.name

            if current_status == "Clock In":
                newstatus = "Clock Out"
                response_label = "Clocked Out"
            else:
                newstatus = "Clock In"
                response_label = "Clocked In"

            event_type = EventType.objects.get(name=newstatus)

            location = Location.objects.get(name="Main Security")

            flip_event = Event.objects.create(
                employee=employee,
                event_type=event_type,
                location=location,
                created_by=request.user,
            )

            flip_event_time = flip_event.timestamp
        else:
            print("TOOSOON!")

        return redirect("main_security")
    else:
        return HttpResponseForbidden("Forbidden")


@extend_schema(exclude=True)
def employee_events(request, id):
    if request.user.is_authenticated:
        employee = Employee.objects.get(id=id)

        employee_events = employee.employee_events.all()

        print(employee_events.first().timestamp)

        return render(
            request,
            "employee_rollup.html",
            {"employee": employee, "employee_events": employee_events},
        )

    else:
        return HttpResponseForbidden("Forbidden")
