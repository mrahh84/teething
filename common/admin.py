from django.contrib import admin

from common.models import Card, Employee, Event, EventType, Location

# Register your models here.

admin.site.register(Event)
admin.site.register(Location)
admin.site.register(EventType)
admin.site.register(Employee)
admin.site.register(Card)
