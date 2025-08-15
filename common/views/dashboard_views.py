"""
Dashboard and analytics views.

This module contains advanced analytics dashboards including
pattern recognition and predictive analytics.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as django_timezone
from drf_spectacular.utils import extend_schema
from django.db.models import Q, Count
from datetime import datetime, timedelta, date, time
import json

from ..models import (
    Employee, Event, EventType, Location, AttendanceRecord, Card, Department,
    AnalyticsCache, ReportConfiguration, EmployeeAnalytics, DepartmentAnalytics, SystemPerformance,
)
from ..services.attendance_service import (
    normalize_department_from_designation as svc_normalize_department_from_designation,
    list_available_departments as svc_list_available_departments,
    filter_employees_by_department as svc_filter_employees_by_department,
)
from ..decorators import security_required, attendance_required, reporting_required, admin_required


@reporting_required
@extend_schema(exclude=True)
def pattern_recognition_dashboard(request):
    """
    Pattern Recognition Dashboard for Phase 2 of the report enhancement roadmap.
    Provides comprehensive pattern analysis for attendance, arrival times, and location movements.
    """
    from django.db.models import Count, Avg, Q
    from datetime import timedelta
    
    today = django_timezone.localtime(django_timezone.now()).date()
    last_30_days = today - timedelta(days=30)
    last_7_days = today - timedelta(days=7)
    
    # Get employee data with analytics
    employees = Employee.objects.filter(is_active=True).select_related('department')
    
    # Calculate pattern data
    pattern_data = []
    for employee in employees:
        events = employee.employee_events.filter(
            timestamp__date__gte=last_30_days,
            timestamp__date__lte=today
        )
        
        if events.exists():
            # Arrival patterns
            clock_in_events = events.filter(event_type__name='Clock In')
            if clock_in_events.exists():
                # Calculate average arrival time manually for SQLite compatibility
                arrival_times = [e.timestamp.time() for e in clock_in_events]
                total_minutes = sum(t.hour * 60 + t.minute for t in arrival_times)
                avg_minutes = total_minutes / len(arrival_times)
                avg_hour = int(avg_minutes // 60)
                avg_minute = int(avg_minutes % 60)
                avg_arrival_time = time(avg_hour, avg_minute)
                
                # Calculate arrival consistency
                target_time = time(9, 0)  # 9:00 AM target
                arrival_deviations = [abs((t.hour * 60 + t.minute) - (target_time.hour * 60 + target_time.minute)) for t in arrival_times]
                avg_deviation = sum(arrival_deviations) / len(arrival_deviations) if arrival_deviations else 0
                consistency_score = max(0, 100 - (avg_deviation / 2))  # Higher score = more consistent
                
                # Determine arrival trend
                if len(clock_in_events) >= 7:
                    recent_events = clock_in_events.filter(timestamp__date__gte=last_7_days)
                    if recent_events.exists():
                        # Calculate recent average manually
                        recent_times = [e.timestamp.time() for e in recent_events]
                        recent_total_minutes = sum(t.hour * 60 + t.minute for t in recent_times)
                        recent_avg_minutes = recent_total_minutes / len(recent_times)
                        recent_avg_hour = int(recent_avg_minutes // 60)
                        recent_avg_minute = int(recent_avg_minutes % 60)
                        recent_avg = time(recent_avg_hour, recent_avg_minute)
                        
                        if recent_avg and avg_arrival_time:
                            if recent_avg < avg_arrival_time:
                                arrival_trend = 'improving'
                            elif recent_avg > avg_arrival_time:
                                arrival_trend = 'declining'
                            else:
                                arrival_trend = 'stable'
                        else:
                            arrival_trend = 'stable'
                    else:
                        arrival_trend = 'stable'
                else:
                    arrival_trend = 'insufficient_data'
            else:
                avg_arrival_time = None
                consistency_score = 0
                arrival_trend = 'no_data'
            
            # Departure patterns
            clock_out_events = events.filter(event_type__name='Clock Out')
            if clock_out_events.exists():
                # Calculate average departure time manually for SQLite compatibility
                departure_times = [e.timestamp.time() for e in clock_out_events]
                departure_total_minutes = sum(t.hour * 60 + t.minute for t in departure_times)
                departure_avg_minutes = departure_total_minutes / len(departure_times)
                departure_avg_hour = int(departure_avg_minutes // 60)
                departure_avg_minute = int(departure_avg_minutes % 60)
                avg_departure_time = time(departure_avg_hour, departure_avg_minute)
                
                # Calculate departure consistency
                target_departure = time(17, 0)  # 5:00 PM target
                departure_deviations = [abs((t.hour * 60 + t.minute) - (target_departure.hour * 60 + target_departure.minute)) for t in departure_times]
                avg_departure_deviation = sum(departure_deviations) / len(departure_deviations) if departure_deviations else 0
                departure_consistency = max(0, 100 - (avg_departure_deviation / 2))
                
                # Determine departure trend
                if len(clock_out_events) >= 7:
                    recent_departures = clock_out_events.filter(timestamp__date__gte=last_7_days)
                    if recent_departures.exists():
                        # Calculate recent departure average manually
                        recent_departure_times = [e.timestamp.time() for e in recent_departures]
                        recent_departure_total_minutes = sum(t.hour * 60 + t.minute for t in recent_departure_times)
                        recent_departure_avg_minutes = recent_departure_total_minutes / len(recent_departure_times)
                        recent_departure_avg_hour = int(recent_departure_avg_minutes // 60)
                        recent_departure_avg_minute = int(recent_departure_avg_minutes % 60)
                        recent_departure_avg = time(recent_departure_avg_hour, recent_departure_avg_minute)
                        
                        if recent_departure_avg and avg_departure_time:
                            if recent_departure_avg > avg_departure_time:
                                departure_trend = 'improving'
                            elif recent_departure_avg < avg_departure_time:
                                departure_trend = 'declining'
                            else:
                                departure_trend = 'stable'
                        else:
                            departure_trend = 'stable'
                    else:
                        departure_trend = 'stable'
                else:
                    departure_trend = 'insufficient_data'
            else:
                avg_departure_time = None
                departure_consistency = 0
                departure_trend = 'no_data'
            
            # Location patterns
            location_events = events.filter(location__isnull=False)
            if location_events.exists():
                location_counts = location_events.values('location__name').annotate(count=Count('id'))
                frequent_locations = [loc['location__name'] for loc in location_counts.order_by('-count')[:3]]
                movement_frequency = location_counts.count()
                location_preference = frequent_locations[0] if frequent_locations else 'unknown'
            else:
                frequent_locations = []
                movement_frequency = 0
                location_preference = 'unknown'
            
            # Calculate overall pattern score
            pattern_score = (consistency_score + departure_consistency) / 2 if departure_consistency > 0 else consistency_score
            
            pattern_data.append({
                'employee_name': f"{employee.given_name} {employee.surname}",
                'department': employee.department.name if employee.department else 'N/A',
                'avg_arrival_time': avg_arrival_time,
                'arrival_consistency': round(consistency_score, 1),
                'arrival_trend': arrival_trend,
                'avg_departure_time': avg_departure_time,
                'departure_consistency': round(departure_consistency, 1),
                'departure_trend': departure_trend,
                'frequent_locations': frequent_locations,
                'movement_frequency': movement_frequency,
                'location_preference': location_preference,
                'pattern_score': round(pattern_score, 1),
                'total_events': events.count(),
            })
    
    # Sort by pattern score (highest first)
    pattern_data.sort(key=lambda x: x['pattern_score'], reverse=True)
    
    # Calculate anomaly data
    anomaly_data = []
    for pattern in pattern_data:
        anomaly_score = 0
        anomaly_factors = []
        
        # Arrival anomalies
        if pattern['arrival_consistency'] < 70:
            anomaly_score += 0.3
            anomaly_factors.append('Inconsistent arrival times')
        
        if pattern['arrival_trend'] == 'declining':
            anomaly_score += 0.2
            anomaly_factors.append('Arrival times getting worse')
        
        # Departure anomalies
        if pattern['departure_consistency'] < 70:
            anomaly_score += 0.3
            anomaly_factors.append('Inconsistent departure times')
        
        if pattern['departure_trend'] == 'declining':
            anomaly_score += 0.2
            anomaly_factors.append('Departure times getting worse')
        
        # Location anomalies
        if pattern['movement_frequency'] > 10:
            anomaly_score += 0.1
            anomaly_factors.append('High location movement')
        
        if anomaly_score > 0.3:
            anomaly_data.append({
                'employee_name': pattern['employee_name'],
                'department': pattern['department'],
                'anomaly_score': round(anomaly_score, 2),
                'anomaly_factors': anomaly_factors,
                'severity': 'high' if anomaly_score > 0.7 else 'medium' if anomaly_score > 0.5 else 'low',
                'pattern_score': pattern['pattern_score']
            })
    
    # Sort anomalies by score (highest first)
    anomaly_data.sort(key=lambda x: x['anomaly_score'], reverse=True)
    
    # Calculate trend data
    if pattern_data:
        avg_attendance_rate = sum(p['pattern_score'] for p in pattern_data) / len(pattern_data)
        total_anomalies = len(anomaly_data)
    else:
        avg_attendance_rate = 0
        total_anomalies = 0
        
    trend_data = {
        'avg_attendance_rate': round(avg_attendance_rate, 1),
        'total_anomalies': total_anomalies,
        'high_risk_employees': len([a for a in anomaly_data if a['severity'] == 'high']),
        'medium_risk_employees': len([a for a in anomaly_data if a['severity'] == 'medium']),
    }
    
    context = {
        'page_title': 'Pattern Recognition Dashboard',
        'active_tab': 'pattern_recognition',
        'pattern_data': pattern_data,
        'anomaly_data': anomaly_data,
        'trend_data': trend_data,
    }
    return render(request, 'attendance/pattern_recognition_dashboard.html', context)


@reporting_required
@extend_schema(exclude=True)
def predictive_analytics_dashboard(request):
    """
    Predictive Analytics Dashboard for Phase 3 of the report enhancement roadmap.
    Provides attendance forecasting, capacity planning, and risk assessment.
    """
    from django.db.models import Count, Avg, Q
    from datetime import timedelta
    
    today = django_timezone.localtime(django_timezone.now()).date()
    last_30_days = today - timedelta(days=30)
    next_30_days = today + timedelta(days=30)
    
    # Get employee data
    employees = Employee.objects.filter(is_active=True).select_related('department')
    
    # Calculate current metrics
    current_metrics = {
        'total_employees': employees.count(),
        'active_employees': employees.filter(
            employee_events__timestamp__date=today
        ).distinct().count(),
        'avg_attendance_rate': 0,
        'predicted_attendance_rate': 0,
    }
    
    # Calculate attendance trends
    attendance_data = []
    for employee in employees:
        events = employee.employee_events.filter(
            timestamp__date__gte=last_30_days,
            timestamp__date__lte=today
        )
        
        if events.exists():
            clock_in_count = events.filter(event_type__name='Clock In').count()
            attendance_rate = (clock_in_count / 30) * 100 if 30 > 0 else 0
            
            attendance_data.append({
                'employee_name': f"{employee.given_name} {employee.surname}",
                'department': employee.department.name if employee.department else 'N/A',
                'current_attendance_rate': round(attendance_rate, 1),
                'predicted_attendance_rate': round(attendance_rate * 0.95, 1),  # Simple prediction
                'risk_level': 'high' if attendance_rate < 70 else 'medium' if attendance_rate < 85 else 'low',
            })
    
    # Calculate averages
    if attendance_data:
        current_metrics['avg_attendance_rate'] = round(
            sum(d['current_attendance_rate'] for d in attendance_data) / len(attendance_data), 1
        )
        current_metrics['predicted_attendance_rate'] = round(
            sum(d['predicted_attendance_rate'] for d in attendance_data) / len(attendance_data), 1
        )
    
    # Generate forecasts
    forecast_data = {
        'next_week_attendance': round(current_metrics['avg_attendance_rate'] * 0.98, 1),
        'next_month_attendance': round(current_metrics['avg_attendance_rate'] * 0.95, 1),
        'capacity_utilization': round((current_metrics['active_employees'] / current_metrics['total_employees']) * 100, 1),
        'predicted_capacity': round((current_metrics['active_employees'] / current_metrics['total_employees']) * 95, 1),
    }
    
    # Risk assessment
    risk_data = {
        'high_risk_employees': len([d for d in attendance_data if d['risk_level'] == 'high']),
        'medium_risk_employees': len([d for d in attendance_data if d['risk_level'] == 'medium']),
        'low_risk_employees': len([d for d in attendance_data if d['risk_level'] == 'low']),
        'total_risks': len([d for d in attendance_data if d['risk_level'] in ['high', 'medium']]),
    }
    
    context = {
        'page_title': 'Predictive Analytics Dashboard',
        'active_tab': 'predictive_analytics',
        'current_metrics': current_metrics,
        'forecast_data': forecast_data,
        'risk_data': risk_data,
        'attendance_data': attendance_data,
    }
    return render(request, 'attendance/predictive_analytics_dashboard.html', context)


@admin_required
@extend_schema(exclude=True)
def performance_monitoring_dashboard(request):
    """
    Advanced performance monitoring dashboard for system optimization.
    Provides comprehensive performance tracking, query monitoring,
    and optimization recommendations.
    """
    from ..utils import performance_monitor
    from django.core.cache import cache
    from datetime import timedelta
    from ..services.dashboard_analytics_service import DashboardAnalyticsService
    
    # Initialize analytics service
    analytics_service = DashboardAnalyticsService()
    
    # Get basic performance report from existing service
    basic_performance_report = performance_monitor.get_performance_report()
    
    # Get new dashboard analytics data
    attendance_trends = analytics_service.get_attendance_trends_data(days=90)
    department_heatmap = analytics_service.get_department_performance_heatmap_data(days=30)
    employee_distribution = analytics_service.get_employee_performance_distribution(days=30)
    real_time_status = analytics_service.get_real_time_attendance_status()
    system_metrics = analytics_service.get_system_performance_metrics(days=7)
    
    # Get system performance metrics
    from ..models import SystemPerformance
    
    today = django_timezone.localtime(django_timezone.now()).date()
    last_7_days = today - timedelta(days=7)
    
    legacy_system_metrics = SystemPerformance.objects.filter(
        date__gte=last_7_days
    ).order_by('-date')[:7]
    
    # Get cache statistics
    cache_stats = {
        'total_keys': len(cache._cache) if hasattr(cache, '_cache') else 'Unknown',
        'cache_hit_rate': cache.get('cache_hit_rate', 0),
        'total_requests': cache.get('total_cache_requests', 0),
        'cache_misses': cache.get('cache_misses', 0)
    }
    
    # Calculate cache hit rate if we have the data
    if cache_stats['total_requests'] > 0:
        cache_stats['calculated_hit_rate'] = round(
            ((cache_stats['total_requests'] - cache_stats['cache_misses']) / cache_stats['total_requests']) * 100, 1
        )
    else:
        cache_stats['calculated_hit_rate'] = 0
    
    # Generate performance recommendations based on available data
    performance_recommendations = []
    
    if basic_performance_report and 'views' in basic_performance_report:
        for view_name, metrics in basic_performance_report['views'].items():
            if metrics.get('avg_queries', 0) > 10:
                performance_recommendations.append({
                    'view': view_name,
                    'issue': 'High query count',
                    'suggestion': 'Implement select_related/prefetch_related'
                })
            
            if metrics.get('avg_time', 0) > 1.0:
                performance_recommendations.append({
                    'view': view_name,
                    'issue': 'Slow execution',
                    'suggestion': 'Add database indexes or optimize queries'
                })
    
    # Add attendance-based recommendations
    if attendance_trends['summary']['avg_attendance_rate'] < 80:
        performance_recommendations.append({
            'view': 'Attendance System',
            'issue': 'Low attendance rate',
            'suggestion': f"Current average: {attendance_trends['summary']['avg_attendance_rate']}%. Review attendance policies and employee engagement."
        })
    
    # Add department performance recommendations
    if department_heatmap['departments']:
        worst_dept = min(department_heatmap['departments'], 
                        key=lambda x: sum(d['performance_score'] for d in x['daily_performance']) / len(x['daily_performance']))
        avg_performance = sum(d['performance_score'] for d in worst_dept['daily_performance']) / len(worst_dept['daily_performance'])
        
        if avg_performance < 70:
            performance_recommendations.append({
                'view': f"Department: {worst_dept['department']}",
                'issue': 'Low department performance',
                'suggestion': f"Average performance: {avg_performance:.1f}%. Investigate attendance issues and provide support."
            })
    
    context = {
        'page_title': 'Advanced Performance Monitoring Dashboard',
        'active_tab': 'performance_monitoring',
        'basic_performance_report': basic_performance_report,
        'legacy_system_metrics': legacy_system_metrics,
        'cache_stats': cache_stats,
        'performance_recommendations': performance_recommendations,
        'last_updated': django_timezone.now(),
        
        # New dashboard data
        'attendance_trends': attendance_trends,
        'department_heatmap': department_heatmap,
        'employee_distribution': employee_distribution,
        'real_time_status': real_time_status,
        'enhanced_system_metrics': system_metrics,
        
        # Chart data as JSON for JavaScript
        'chart_data': {
            'attendance_trends_labels': json.dumps([d['date'] for d in attendance_trends['daily_data']]),
            'attendance_trends_data': json.dumps([d['attendance_rate'] for d in attendance_trends['daily_data']]),
            'department_comparison_labels': json.dumps([d['department_name'] for d in attendance_trends['department_comparison']]),
            'department_comparison_data': json.dumps([d['attendance_rate'] for d in attendance_trends['department_comparison']]),
            'performance_tiers': json.dumps([
                employee_distribution['statistics']['performance_tiers']['excellent'],
                employee_distribution['statistics']['performance_tiers']['good'],
                employee_distribution['statistics']['performance_tiers']['average'],
                employee_distribution['statistics']['performance_tiers']['below_average'],
                employee_distribution['statistics']['performance_tiers']['poor']
            ])
        }
    }
    
    return render(request, 'performance_monitoring_dashboard.html', context)