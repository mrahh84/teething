from django.urls import path
from common import views

# URLs organized by section for easier permission implementation in the future

# Clock-in dashboard section
clock_in_urls = [
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
    # Event editing URLs
    path(
        "employee_events/<int:employee_id>/update_event/",
        views.update_event,
        name="update_event",
    ),
    path(
        "employee_events/<int:employee_id>/delete_event/",
        views.delete_event,
        name="delete_event",
    ),
]

# Attendance section
attendance_urls = [
    path("attendance/", views.attendance_list, name="attendance_list"),
    path("attendance/analytics/", views.attendance_analytics, name="attendance_analytics"),
    path("attendance/progressive_entry/", views.progressive_entry, name="progressive_entry"),
    path("attendance/historical_progressive_entry/", views.historical_progressive_entry, name="historical_progressive_entry"),
    path("attendance/historical_progressive_results/", views.historical_progressive_results, name="historical_progressive_results"),
                    path("attendance/export_csv/", views.attendance_export_csv, name="attendance_export_csv"),
                path("reports/comprehensive/export_csv/", views.comprehensive_attendance_export_csv, name="comprehensive_attendance_export_csv"),
    path("attendance/entry/", views.attendance_entry, name="attendance_entry"),
    path("attendance/edit/<int:record_id>/", views.attendance_edit, name="attendance_edit"),
    path("attendance/delete/<int:record_id>/", views.attendance_delete, name="attendance_delete"),
    path("attendance/bulk_historical_update/", views.bulk_historical_update, name="bulk_historical_update"),
    path("attendance/debug/", views.debug_view, name="debug_view"),
]

# Reports section
report_urls = [
    path("reports/", views.reports_dashboard, name="reports_dashboard"),
    path("reports/comprehensive/", views.comprehensive_reports, name="comprehensive_reports"),
    path("reports/comprehensive-attendance/", views.comprehensive_attendance_report, name="comprehensive_attendance_report"),
    path("reports/daily_dashboard/", views.daily_dashboard_report, name="daily_dashboard_report"),
    path("reports/employee_history/", views.employee_history_report, name="employee_history_report"),
    path("reports/employee_history/csv/", views.employee_history_report_csv, name="employee_history_report_csv"),
    path("reports/period_summary/", views.period_summary_report, name="period_summary_report"),
    path("reports/period_summary/csv/", views.period_summary_report_csv, name="period_summary_report_csv"),

    path("reports/performance/", views.performance_dashboard, name="performance_dashboard"),
    path(
        "reports/generate/<str:report_type>/",
        views.generate_marimo_report,
        name="generate_marimo_report",
    ),
]

# Location tracking section
location_urls = [
    path("location-dashboard/", views.location_dashboard, name="location_dashboard"),
    path("location-assignments/", views.location_assignment_list, name="location_assignment_list"),
    path("location-assignments/create/", views.location_assignment_create, name="location_assignment_create"),
    path("location-assignments/<int:assignment_id>/edit/", views.location_assignment_edit, name="location_assignment_edit"),
    path("location-assignments/<int:assignment_id>/delete/", views.location_assignment_delete, name="location_assignment_delete"),
    path("location-assignments/<int:assignment_id>/complete/", views.location_assignment_complete, name="location_assignment_complete"),
    path("location-assignments/bulk/", views.bulk_location_assignment, name="bulk_location_assignment"),
]

# API endpoints
api_urls = [
    # List all events (GET)
    path(
        "api/events/", views.ListEventsView.as_view(), name="api_event_list"
    ),
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
    
    # Location tracking API endpoints
    path(
        "api/location-analytics/<int:location_id>/", 
        views.location_analytics_api, 
        name="api_location_analytics"
    ),
    path(
        "api/employee-locations/", 
        views.employee_locations_api, 
        name="api_employee_locations"
    ),
    path(
        "api/location-summary/", 
        views.location_summary_api, 
        name="api_location_summary"
    ),
    
    # Analytics API endpoints
    # Departments
    path(
        "api/departments/", views.ListDepartmentsView.as_view(), name="api_department_list"
    ),
    path(
        "api/departments/<int:id>/", views.SingleDepartmentView.as_view(), name="api_single_department"
    ),
    
    # Analytics Cache
    path(
        "api/analytics-cache/", views.ListAnalyticsCacheView.as_view(), name="api_analytics_cache_list"
    ),
    path(
        "api/analytics-cache/<int:id>/", views.SingleAnalyticsCacheView.as_view(), name="api_single_analytics_cache"
    ),
    
    # Report Configurations
    path(
        "api/report-configurations/", views.ListReportConfigurationsView.as_view(), name="api_report_configuration_list"
    ),
    path(
        "api/report-configurations/<int:id>/", views.SingleReportConfigurationView.as_view(), name="api_single_report_configuration"
    ),
    
    # Employee Analytics
    path(
        "api/employee-analytics/", views.ListEmployeeAnalyticsView.as_view(), name="api_employee_analytics_list"
    ),
    path(
        "api/employee-analytics/<int:id>/", views.SingleEmployeeAnalyticsView.as_view(), name="api_single_employee_analytics"
    ),
    
    # Department Analytics
    path(
        "api/department-analytics/", views.ListDepartmentAnalyticsView.as_view(), name="api_department_analytics_list"
    ),
    path(
        "api/department-analytics/<int:id>/", views.SingleDepartmentAnalyticsView.as_view(), name="api_single_department_analytics"
    ),
    
    # System Performance
    path(
        "api/system-performance/", views.ListSystemPerformanceView.as_view(), name="api_system_performance_list"
    ),
    path(
        "api/system-performance/<int:id>/", views.SingleSystemPerformanceView.as_view(), name="api_single_system_performance"
    ),
    
                    # Real-time Analytics API endpoints
                path("api/realtime/employees/", views.RealTimeEmployeeStatusView.as_view(), name="api_realtime_employees"),
                path("api/realtime/attendance-counter/", views.LiveAttendanceCounterView.as_view(), name="api_attendance_counter"),
                
                # Phase 3: Advanced Analytics API endpoints
                path("api/pattern-recognition/", views.PatternRecognitionView.as_view(), name="api_pattern_recognition"),
                path("api/anomaly-detection/", views.AnomalyDetectionView.as_view(), name="api_anomaly_detection"),
                path("api/predictive-analytics/", views.PredictiveAnalyticsView.as_view(), name="api_predictive_analytics"),
]

# System URLs
system_urls = [
    # Health check endpoint
    path("health/", views.health_check, name="health_check"),
]

# Combine all URL patterns
urlpatterns = clock_in_urls + attendance_urls + report_urls + location_urls + api_urls + system_urls

# Real-time Analytics Dashboard


# Phase 3: Advanced Analytics Dashboards
urlpatterns.append(path("pattern-recognition/", views.pattern_recognition_dashboard, name="pattern_recognition_dashboard"))
urlpatterns.append(path("predictive-analytics/", views.predictive_analytics_dashboard, name="predictive_analytics_dashboard"))
