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
    comprehensive_attendance_report,

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
    # pattern_recognition_dashboard,
    # predictive_analytics_dashboard,
    performance_monitoring_dashboard,
)

# URLs organized by section for easier permission implementation in the future

# Security URLs
urlpatterns = [
    path('', main_security, name='main_security'),
    path('employee-events/<int:id>/', employee_events, name='employee_events'),
    path('main-security-clocked-in-status-flip/<int:id>/', main_security_clocked_in_status_flip, name='main_security_clocked_in_status_flip'),
    path('update-event/<int:event_id>/', update_event, name='update_event'),
    path('delete-event/<int:event_id>/', delete_event, name='delete_event'),
    
    # Attendance URLs
    path('attendance/', attendance_list, name='attendance_list'),
    path('attendance/analytics/', attendance_analytics, name='attendance_analytics'),
    path('attendance/progressive-entry/', progressive_entry, name='progressive_entry'),
    path('attendance/historical-progressive-entry/', historical_progressive_entry, name='historical_progressive_entry'),
    path('attendance/historical-progressive-results/', historical_progressive_results, name='historical_progressive_results'),
    path('attendance/export-csv/', attendance_export_csv, name='attendance_export_csv'),
    path('attendance/comprehensive-export-csv/', comprehensive_attendance_export_csv, name='comprehensive_attendance_export_csv'),
    path('attendance/entry/', attendance_entry, name='attendance_entry'),
    path('attendance/edit/<int:record_id>/', attendance_edit, name='attendance_edit'),
    path('attendance/delete/<int:record_id>/', attendance_delete, name='attendance_delete'),
    path('attendance/bulk-historical-update/', bulk_historical_update, name='bulk_historical_update'),
    path('debug/', debug_view, name='debug_view'),
    
    # Reporting URLs
    path('reports/', reports_dashboard, name='reports_dashboard'),
    path('reports/comprehensive-attendance/', comprehensive_attendance_report, name='comprehensive_attendance_report'),

    path('reports/employee-history/', employee_history_report, name='employee_history_report'),
    path('reports/employee-history/<int:employee_id>/<str:start_date>/<str:end_date>/', employee_history_report, name='employee_history_report_detail'),
    path('reports/employee-history-csv/<int:employee_id>/<str:start_date>/<str:end_date>/', employee_history_report_csv, name='employee_history_report_csv'),
    path('reports/period-summary/', period_summary_report, name='period_summary_report'),
    path('reports/period-summary-csv/', period_summary_report_csv, name='period_summary_report_csv'),
    path('reports/performance-dashboard/', performance_dashboard, name='performance_dashboard'),
    path('reports/marimo/', generate_marimo_report, name='generate_marimo_report'),
    
    # Phase 3 & 4 Optimized Reporting URLs

    # Location URLs
    path('locations/', location_dashboard, name='location_dashboard'),
    path('locations/assignments/', location_assignment_list, name='location_assignment_list'),
    path('locations/assignments/create/', location_assignment_create, name='location_assignment_create'),
    path('locations/assignments/<int:assignment_id>/edit/', location_assignment_edit, name='location_assignment_edit'),
    path('locations/assignments/<int:assignment_id>/delete/', location_assignment_delete, name='location_assignment_delete'),
    path('locations/assignments/<int:assignment_id>/complete/', location_assignment_complete, name='location_assignment_complete'),
    path('locations/bulk-assignment/', bulk_location_assignment, name='bulk_location_assignment'),
    
    # API URLs
    path('api/events/', ListEventsView.as_view(), name='api_event_list'),
    path('api/events/<int:id>/', SingleEventView.as_view(), name='api_single_event'),
    path('api/employees/<int:id>/', SingleEmployeeView.as_view(), name='api_single_employee'),
    path('api/locations/<int:id>/', SingleLocationView.as_view(), name='api_single_location'),
    path('api/departments/', ListDepartmentsView.as_view(), name='api_department_list'),
    path('api/departments/<int:id>/', SingleDepartmentView.as_view(), name='api_single_department'),
    path('api/analytics-cache/', ListAnalyticsCacheView.as_view(), name='api_analytics_cache_list'),
    path('api/analytics-cache/<int:id>/', SingleAnalyticsCacheView.as_view(), name='api_single_analytics_cache'),
    path('api/report-configurations/', ListReportConfigurationsView.as_view(), name='api_report_configuration_list'),
    path('api/report-configurations/<int:id>/', SingleReportConfigurationView.as_view(), name='api_single_report_configuration'),
    path('api/employee-analytics/', ListEmployeeAnalyticsView.as_view(), name='api_employee_analytics_list'),
    path('api/employee-analytics/<int:id>/', SingleEmployeeAnalyticsView.as_view(), name='api_single_employee_analytics'),
    path('api/department-analytics/', ListDepartmentAnalyticsView.as_view(), name='api_department_analytics_list'),
    path('api/department-analytics/<int:id>/', SingleDepartmentAnalyticsView.as_view(), name='api_single_department_analytics'),
    path('api/system-performance/', ListSystemPerformanceView.as_view(), name='api_system_performance_list'),
    path('api/system-performance/<int:id>/', SingleSystemPerformanceView.as_view(), name='api_single_system_performance'),
    path('api/realtime/employees/', RealTimeEmployeeStatusView.as_view(), name='api_realtime_employees'),
    path('api/realtime/attendance-counter/', LiveAttendanceCounterView.as_view(), name='api_attendance_counter'),
    path('api/pattern-recognition/', PatternRecognitionView.as_view(), name='api_pattern_recognition'),
    path('api/anomaly-detection/', AnomalyDetectionView.as_view(), name='api_anomaly_detection'),
    path('api/predictive-analytics/', PredictiveAnalyticsView.as_view(), name='api_predictive_analytics'),
    
    # Location Analytics API
    path('api/location-analytics/<int:location_id>/', location_analytics_api, name='api_location_analytics'),
    path('api/employee-locations/', employee_locations_api, name='api_employee_locations'),
    path('api/location-summary/', location_summary_api, name='api_location_summary'),
]

# System URLs
system_urls = [
    # Health check endpoint
    path("health/", health_check, name="health_check"),
]

# Combine all URL patterns
urlpatterns = urlpatterns + system_urls

# Phase 3: Advanced Analytics Dashboards - REMOVED (nonsense functionality)
# urlpatterns.append(path("pattern-recognition/", pattern_recognition_dashboard, name="pattern_recognition_dashboard"))
# urlpatterns.append(path("predictive-analytics/", predictive_analytics_dashboard, name="predictive_analytics_dashboard"))
urlpatterns.append(path("performance-monitoring/", performance_monitoring_dashboard, name="performance_monitoring_dashboard"))

