from django.urls import path
from common.views import (
    # Security views
    main_security,
    employee_events,
    main_security_clocked_in_status_flip,
    update_event,
    delete_event,
    
    # Attendance views
    attendance_list,
    attendance_analytics,
    progressive_entry,
    historical_progressive_entry,
    historical_progressive_results,
    attendance_export_csv,
    comprehensive_attendance_export_csv,
    attendance_entry,
    attendance_edit,
    attendance_delete,
    bulk_historical_update,
    debug_view,
    
    # Reporting views
    reports_dashboard,
    comprehensive_reports,
    comprehensive_attendance_report,
    daily_dashboard_report,
    employee_history_report,
    employee_history_report_csv,
    period_summary_report,
    period_summary_report_csv,
    performance_dashboard,
    generate_marimo_report,
    
    # Location views
    location_dashboard,
    location_assignment_list,
    location_assignment_create,
    location_assignment_edit,
    location_assignment_delete,
    location_assignment_complete,
    bulk_location_assignment,
    
    # API views
    ListEventsView,
    SingleEventView,
    SingleLocationView,
    SingleEmployeeView,
    ListDepartmentsView,
    SingleDepartmentView,
    location_analytics_api,
    employee_locations_api,
    location_summary_api,
    ListAnalyticsCacheView,
    SingleAnalyticsCacheView,
    ListReportConfigurationsView,
    SingleReportConfigurationView,
    ListEmployeeAnalyticsView,
    SingleEmployeeAnalyticsView,
    ListDepartmentAnalyticsView,
    SingleDepartmentAnalyticsView,
    ListSystemPerformanceView,
    SingleSystemPerformanceView,
    RealTimeEmployeeStatusView,
    LiveAttendanceCounterView,
    PatternRecognitionView,
    AnomalyDetectionView,
    PredictiveAnalyticsView,
    
    # System views
    health_check,
    
    # Dashboard views
    pattern_recognition_dashboard,
    predictive_analytics_dashboard,
)

# URLs organized by section for easier permission implementation in the future

# Clock-in dashboard section
clock_in_urls = [
    # Main dashboard view
    path("main_security/", main_security, name="main_security"),
    # Detailed event view for a single employee
    path("employee_events/<int:id>/", employee_events, name="employee_events"),
    # Action URL to clock an employee in/out from the main view
    path(
        "main_security/flip_clocked_in_status/<int:id>/",
        main_security_clocked_in_status_flip,
        name="main_security_clocked_in_status_flip",
    ),
    # Event editing URLs
    path(
        "employee_events/<int:employee_id>/update_event/",
        update_event,
        name="update_event",
    ),
    path(
        "employee_events/<int:employee_id>/delete_event/",
        delete_event,
        name="delete_event",
    ),
]

# Attendance section
attendance_urls = [
    path("attendance/", attendance_list, name="attendance_list"),
    path("attendance/analytics/", attendance_analytics, name="attendance_analytics"),
    path("attendance/progressive_entry/", progressive_entry, name="progressive_entry"),
    path("attendance/historical_progressive_entry/", historical_progressive_entry, name="historical_progressive_entry"),
    path("attendance/historical_progressive_results/", historical_progressive_results, name="historical_progressive_results"),
                    path("attendance/export_csv/", attendance_export_csv, name="attendance_export_csv"),
                path("reports/comprehensive/export_csv/", comprehensive_attendance_export_csv, name="comprehensive_attendance_export_csv"),
    path("attendance/entry/", attendance_entry, name="attendance_entry"),
    path("attendance/edit/<int:record_id>/", attendance_edit, name="attendance_edit"),
    path("attendance/delete/<int:record_id>/", attendance_delete, name="attendance_delete"),
    path("attendance/bulk_historical_update/", bulk_historical_update, name="bulk_historical_update"),
    path("attendance/debug/", debug_view, name="debug_view"),
]

# Reports section
report_urls = [
    path("reports/", reports_dashboard, name="reports_dashboard"),
    path("reports/comprehensive/", comprehensive_reports, name="comprehensive_reports"),
    path("reports/comprehensive-attendance/", comprehensive_attendance_report, name="comprehensive_attendance_report"),
    path("reports/daily_dashboard/", daily_dashboard_report, name="daily_dashboard_report"),
    path("reports/employee_history/", employee_history_report, name="employee_history_report"),
    path("reports/employee_history/csv/", employee_history_report_csv, name="employee_history_report_csv"),
    path("reports/period_summary/", period_summary_report, name="period_summary_report"),
    path("reports/period_summary/csv/", period_summary_report_csv, name="period_summary_report_csv"),

    path("reports/performance/", performance_dashboard, name="performance_dashboard"),
    path(
        "reports/generate/<str:report_type>/",
        generate_marimo_report,
        name="generate_marimo_report",
    ),
]

# Location tracking section
location_urls = [
    path("location-dashboard/", location_dashboard, name="location_dashboard"),
    path("location-assignments/", location_assignment_list, name="location_assignment_list"),
    path("location-assignments/create/", location_assignment_create, name="location_assignment_create"),
    path("location-assignments/<int:assignment_id>/edit/", location_assignment_edit, name="location_assignment_edit"),
    path("location-assignments/<int:assignment_id>/delete/", location_assignment_delete, name="location_assignment_delete"),
    path("location-assignments/<int:assignment_id>/complete/", location_assignment_complete, name="location_assignment_complete"),
    path("location-assignments/bulk/", bulk_location_assignment, name="bulk_location_assignment"),
]

# API endpoints
api_urls = [
    # List all events (GET)
    path(
        "api/events/", ListEventsView.as_view(), name="api_event_list"
    ),
    # Retrieve, Update, Delete single event (GET, PUT, PATCH, DELETE)
    path(
        "api/events/<int:id>/", SingleEventView.as_view(), name="api_single_event"
    ),
    # Retrieve, Update, Delete single employee (GET, PUT, PATCH, DELETE)
    path(
        "api/employees/<int:id>/",
        SingleEmployeeView.as_view(),
        name="api_single_employee",
    ),
    # Retrieve, Update, Delete single location (GET, PUT, PATCH, DELETE)
    path(
        "api/locations/<int:id>/",
        SingleLocationView.as_view(),
        name="api_single_location",
    ),
    
    # Location tracking API endpoints
    path(
        "api/location-analytics/<int:location_id>/", 
        location_analytics_api, 
        name="api_location_analytics"
    ),
    path(
        "api/employee-locations/", 
        employee_locations_api, 
        name="api_employee_locations"
    ),
    path(
        "api/location-summary/", 
        location_summary_api, 
        name="api_location_summary"
    ),
    
    # Analytics API endpoints
    # Departments
    path(
        "api/departments/", ListDepartmentsView.as_view(), name="api_department_list"
    ),
    path(
        "api/departments/<int:id>/", SingleDepartmentView.as_view(), name="api_single_department"
    ),
    
    # Analytics Cache
    path(
        "api/analytics-cache/", ListAnalyticsCacheView.as_view(), name="api_analytics_cache_list"
    ),
    path(
        "api/analytics-cache/<int:id>/", SingleAnalyticsCacheView.as_view(), name="api_single_analytics_cache"
    ),
    
    # Report Configurations
    path(
        "api/report-configurations/", ListReportConfigurationsView.as_view(), name="api_report_configuration_list"
    ),
    path(
        "api/report-configurations/<int:id>/", SingleReportConfigurationView.as_view(), name="api_single_report_configuration"
    ),
    
    # Employee Analytics
    path(
        "api/employee-analytics/", ListEmployeeAnalyticsView.as_view(), name="api_employee_analytics_list"
    ),
    path(
        "api/employee-analytics/<int:id>/", SingleEmployeeAnalyticsView.as_view(), name="api_single_employee_analytics"
    ),
    
    # Department Analytics
    path(
        "api/department-analytics/", ListDepartmentAnalyticsView.as_view(), name="api_department_analytics_list"
    ),
    path(
        "api/department-analytics/<int:id>/", SingleDepartmentAnalyticsView.as_view(), name="api_single_department_analytics"
    ),
    
    # System Performance
    path(
        "api/system-performance/", ListSystemPerformanceView.as_view(), name="api_system_performance_list"
    ),
    path(
        "api/system-performance/<int:id>/", SingleSystemPerformanceView.as_view(), name="api_single_system_performance"
    ),
    
                    # Real-time Analytics API endpoints
                path("api/realtime/employees/", RealTimeEmployeeStatusView.as_view(), name="api_realtime_employees"),
                path("api/realtime/attendance-counter/", LiveAttendanceCounterView.as_view(), name="api_attendance_counter"),
                
                # Phase 3: Advanced Analytics API endpoints
                path("api/pattern-recognition/", PatternRecognitionView.as_view(), name="api_pattern_recognition"),
                path("api/anomaly-detection/", AnomalyDetectionView.as_view(), name="api_anomaly_detection"),
                path("api/predictive-analytics/", PredictiveAnalyticsView.as_view(), name="api_predictive_analytics"),
]

# System URLs
system_urls = [
    # Health check endpoint
    path("health/", health_check, name="health_check"),
]

# Combine all URL patterns
urlpatterns = clock_in_urls + attendance_urls + report_urls + location_urls + api_urls + system_urls

# Real-time Analytics Dashboard


# Phase 3: Advanced Analytics Dashboards
urlpatterns.append(path("pattern-recognition/", pattern_recognition_dashboard, name="pattern_recognition_dashboard"))
urlpatterns.append(path("predictive-analytics/", predictive_analytics_dashboard, name="predictive_analytics_dashboard"))
