from django.urls import path

from . import views

urlpatterns = [
# 	path('single_event/<int:id>',views.SingleEventView.as_view()),
# 	path('single_employee/<int:id>',views.SingleEmployeeView.as_view()),
# 	path('single_location/<int:id>',views.SingleLocationView.as_view()),
	path('event_list/',views.ListEventsView.as_view()),
	path('main_security/',views.main_security,name="main_security"),
	path('employee_events/<int:id>',views.employee_events,name="employee_events"),
	path('main_security/flip_clocked_in_status/<int:id>',views.main_security_clocked_in_status_flip,name="main_security_clocked_in_status_flip")
]

