from django.urls import path
from common import views

urlpatterns = [
    # --- Template Views ---
    # Main dashboard view
    path("main_security/", views.main_security, name="main_security"),
    # Detailed event view for a single employee
    path("employee_events/<int:id>/", views.employee_events, name="employee_events"),
    # Action URL to clock an employee in/out from the main view
    path(
        "main_security/flip_clocked_in_status/<int:id>/",
        views.main_security_clocked_in_status_flip,
        name="main_security_clocked_in_status_flip",
    ),
    # --- API Views ---
    # List all events (GET)
    path(
        "api/events/", views.ListEventsView.as_view(), name="api_event_list"
    ),  # Changed URL for clarity
    # Retrieve, Update, Delete single event (GET, PUT, PATCH, DELETE)
    path(
        "api/events/<int:id>/", views.SingleEventView.as_view(), name="api_single_event"
    ),
    # Retrieve, Update, Delete single employee (GET, PUT, PATCH, DELETE)
    path(
        "api/employees/<int:id>/",
        views.SingleEmployeeView.as_view(),
        name="api_single_employee",
    ),
    # Retrieve, Update, Delete single location (GET, PUT, PATCH, DELETE)
    path(
        "api/locations/<int:id>/",
        views.SingleLocationView.as_view(),
        name="api_single_location",
    ),
    # --- Health Check Views ---
    # Health check endpoint
    path("health/", views.health_check, name="health_check"),
]
