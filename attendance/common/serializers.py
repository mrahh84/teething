from rest_framework import serializers
from rest_framework.fields import SerializerMethodField,IntegerField,CharField
from .models import *
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample,extend_schema_field
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q



class EmployeeSerializer(serializers.ModelSerializer):
	is_clocked_in=serializers.SerializerMethodField()
	last_clockinout_time=serializers.SerializerMethodField()
	
	def get_is_clocked_in(self,instance) -> serializers.BooleanField():
		employee=instance
		
		employee_events=Event.objects.all().filter(employee=employee)
		
		if employee_events.count()==0:
			return False
		
		employee_clock_inout_events=employee_events.filter(
			Q(event_type__name="Clock In") | Q(event_type__name="Clock Out")
		)
		
		current_status=employee_clock_inout_events.order_by("-timestamp").first().event_type.name
		
		if current_status=="Clock In":
			return True
		else:
			return False
	
	def get_last_clockinout_time(self,instance) -> serializers.DateTimeField():
		employee=instance
		
		employee_events=Event.objects.all().filter(employee=employee)
		
		if employee_events.count()==0:
			return None
		
		employee_clock_inout_events=employee_events.filter(
			Q(event_type__name="Clock In") | Q(event_type__name="Clock Out")
		)
		
		current_status=employee_clock_inout_events.order_by("-timestamp").first()
		
		return current_status.timestamp 

	class Meta:
		model=Employee
		fields='__all__'

class LocationSerializer(serializers.ModelSerializer):
	class Meta:
		model=Location
		fields='__all__'

class EventTypeSerializer(serializers.ModelSerializer):
	class Meta:
		model=EventType
		fields='__all__'

class EventSerializer(serializers.ModelSerializer):
	event_type=EventTypeSerializer(many=False)
	employee=EmployeeSerializer(many=False)
	location=LocationSerializer(many=False)
	
	class Meta:
		model=Event
		fields='__all__'


class SingleEventSerializer(serializers.ModelSerializer):	
	class Meta:
		model=Event
		fields='__all__'